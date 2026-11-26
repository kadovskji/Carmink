"""The match engine: lobby, turns, timers, guesses, hints and scoring.

It knows nothing about Telegram or HTTP: everything goes through the `IO` object, so it can
be driven by the bot handlers, by the Mini App backend and by tests with a fake clock.
All state changes happen *before* the first `await` of each step, so the single event loop
never sees a half-updated game.
"""
import html
import logging
import math
import random
from typing import Awaitable, Callable, Protocol

import config
import strokes
import words
from broken import BrokenMixin
from db import Database
from errors import GameError
from game import (Game, Phase, Turn, drawer_points, guess_points, laps, ranking,
                  speedrun_drawer_points)
from i18n import T, dur

LOG = logging.getLogger("carmink.game")

Button = tuple[str, str]        # (label, url)


class IO(Protocol):
    def now(self) -> float: ...
    async def send(self, chat_id: int, text: str, buttons: list[Button] | None = None,
                   reply_to: int | None = None) -> int | None: ...
    async def send_photo(self, chat_id: int, jpeg: bytes, caption: str) -> int | None: ...
    async def edit_photo(self, chat_id: int, message_id: int, jpeg: bytes | None,
                         caption: str) -> None: ...
    async def delete(self, chat_id: int, message_id: int) -> None: ...
    async def is_admin(self, chat_id: int, user_id: int) -> bool: ...
    async def can_delete(self, chat_id: int) -> bool: ...          # may the bot delete messages here?
    def schedule(self, name: str, delay: float, fn: Callable[[], Awaitable[None]]) -> None: ...
    def cancel(self, prefix: str) -> None: ...
    # Broken Canva
    async def send_dm(self, user_id: int, text: str, buttons: list[Button] | None = None) -> bool: ...
    async def send_photo_dm(self, user_id: int, jpeg: bytes, caption: str) -> bool: ...
    async def send_animation(self, chat_id: int, data: bytes, caption: str) -> int | None: ...
    async def edit_text(self, chat_id: int, message_id: int, text: str,
                        buttons: list[Button] | None = None) -> None: ...


def esc(name: str) -> str:
    return html.escape(name, quote=False)


def fmt_duration(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    m, s = divmod(seconds, 60)
    return f"{m}m {s:02d}s" if m else f"{s}s"


def admin_button(lang: str) -> tuple[str, str]:
    """A link that asks to promote the bot, already with the rights it needs."""
    return (T(lang, "btn_make_admin"),
            f"https://t.me/{config.BOT_USERNAME}?startgroup=true&admin=delete_messages")


def chat_from_param(param: str | None) -> int | None:
    """Mini App start parameter 'c1001234567' -> chat id -1001234567 ('t<id>': admin test match)."""
    if param and param[0] == "c" and param[1:].isdigit():
        return -int(param[1:])
    if param and param[0] == "t" and param[1:].isdigit():
        return int(param[1:])
    return None


TEST_BASE = 9_000_000_000_000           # fake test players have ids far above any real Telegram user


MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


class Engine(BrokenMixin):
    def __init__(self, io: IO, db: Database, rng: random.Random | None = None) -> None:
        self.io = io
        self.db = db
        self.rng = rng or random.Random()
        self.games: dict[int, Game] = {}
        self.user_game: dict[int, int] = {}

    # ================================================================ helpers
    def link(self, chat_id: int, compact: bool = False) -> str:
        g = self.games.get(chat_id)
        param = f"t{chat_id}" if g and g.test else f"c{abs(chat_id)}"
        url = (f"https://t.me/{config.BOT_USERNAME}/{config.MINIAPP_SHORTNAME}"
               f"?startapp={param}")
        return url + "&mode=compact" if compact else url

    async def _del(self, g: Game, chat_id: int, message_id: int) -> None:
        if not g.test and message_id:           # test messages come from /t: nothing to delete
            await self.io.delete(chat_id, message_id)

    # ================================================================ admin test matches
    async def new_test_game(self, admin: int, lang: str, mode: str, n: int) -> Game | None:
        """A match in the admin's private chat with `n` fake players he plays by himself."""
        if admin in self.games:
            return None
        n = max(3 if mode != "broken" else config.MIN_PLAYERS_BROKEN, min(n, 8))
        base = TEST_BASE + (admin % 10**7) * 100
        ids = [base + i for i in range(1, n + 1)]
        names = {u: f"Test {i}" for i, u in enumerate(ids, 1)}
        chosen = self.db.get_settings(admin)["drawtime"]
        g = Game(chat_id=admin, lang=lang, creator=ids[0], mode=mode, players=dict(names),
                 names=dict(names), lobby_end=self.io.now(), test=True, test_ids=ids,
                 draw_seconds=config.DRAW_DEFAULTS[mode] if chosen == "auto" else int(chosen))
        self.games[admin] = g
        for u in ids:
            self.user_game[u] = admin
        LOG.info("test game (%s, %d players) by admin %s", mode, n, admin)
        await self._begin(g)
        return g

    async def end_test(self, admin: int) -> bool:
        g = self.games.get(admin)
        if not g or not g.test:
            return False
        self._close(g)
        return True

    async def act_as(self, admin: int, n: int, text: str) -> str | None:
        """`/t <n> <text>`: type `text` as fake player n. Returns a note for the admin, if any."""
        g = self.games.get(admin)
        if not g or not g.test:
            return "Nessuna partita di test attiva."
        if not 1 <= n <= len(g.test_ids):
            return f"Giocatore {n} inesistente (1-{len(g.test_ids)})."
        uid = g.test_ids[n - 1]
        try:
            if g.mode == "broken":
                if not await self.on_private(uid, text):
                    return f"Test {n}: ora non deve scrivere nulla."
            elif g.mode == "classic":
                res = await self.web_guess(admin, uid, text)
                return f"Test {n}: {res['result']}"
            else:
                await self.on_message(admin, uid, text, 0)
        except GameError as e:
            return f"Test {n}: {e.code}"
        return None

    def _timer(self, g: Game, kind: str, delay: float, fn) -> None:
        """Run `fn(g)` later, unless the match moved on in the meantime."""
        gen = g.gen

        async def run() -> None:
            if self.games.get(g.chat_id) is g and g.gen == gen:
                await fn(g)
        self.io.schedule(f"{g.chat_id}:{kind}", delay, run)

    async def _say(self, chat_id: int, lang: str, key: str, **kw) -> None:
        await self.io.send(chat_id, T(lang, key, **kw))

    def _board(self, g: Game) -> str:
        rows = ranking(g.scores, g.players)
        lines = [f"{MEDALS.get(r, f'{r}.')} {esc(n)} — {p}" for r, _, n, p in rows[:10]]
        return T(g.lang, "board_title") + "\n" + "\n".join(lines)

    def _close(self, g: Game) -> None:
        self.io.cancel(f"{g.chat_id}:")
        g.go(Phase.DONE)
        if self.games.get(g.chat_id) is g:
            del self.games[g.chat_id]
        for uid in list(self.user_game):
            if self.user_game[uid] == g.chat_id:
                del self.user_game[uid]

    def words_for(self, chat_id: int, lang: str) -> list[words.Entry]:
        return words.load(lang) + self.db.custom_entries(chat_id, lang)

    def _caption(self, g: Game) -> str:
        t = g.turn
        text = f"🎨 <b>{esc(g.name(t.drawer))}</b> {words.CATEGORY_ICON.get(t.word.cat, '')}"
        if t.hints:
            text += f"\n🔤 <code>{words.make_mask(t.word.word, t.revealed())}</code>"
        return text

    # ================================================================ lobby commands
    async def can_open(self, chat_id: int, uid: int, lang: str) -> bool:
        """True if `uid` may open a match here; otherwise says why in the chat."""
        if chat_id in self.games:
            await self._say(chat_id, lang, "game_exists")
        elif uid in self.user_game:
            await self._say(chat_id, lang, "already_in_game")
        else:
            return True
        return False

    async def new_game(self, chat_id: int, uid: int, name: str, lang: str,
                       mode: str = config.DEFAULT_MODE) -> None:
        if not await self.can_open(chat_id, uid, lang):
            return
        if mode == "broken" and not self.db.has_dm(uid):
            return await self._need_dm(chat_id, lang)
        chosen = self.db.get_settings(chat_id)["drawtime"]
        g = Game(chat_id=chat_id, lang=lang, creator=uid, mode=mode, players={uid: name},
                 names={uid: name}, lobby_end=self.io.now() + config.LOBBY_SECONDS,
                 draw_seconds=config.DRAW_DEFAULTS[mode] if chosen == "auto" else int(chosen))
        self.games[chat_id] = g
        self.user_game[uid] = chat_id
        self._timer(g, "lobby", config.LOBBY_SECONDS, self._lobby_expired)
        LOG.info("new game in %s (%s, %s) by %s", chat_id, mode, lang, uid)
        text = T(lang, "lobby_open", name=esc(name), min=g.min_players, mode=T(lang, f"mode_{mode}"),
                 time=fmt_duration(config.LOBBY_SECONDS))
        if mode == "broken":
            text += "\n\n" + T(lang, "bk_lobby_note")
        await self.io.send(chat_id, text, self._start_button(g) if mode == "broken" else None)
        if mode != "broken" and not await self.io.can_delete(chat_id):
            await self.io.send(chat_id, T(lang, "need_admin_note"), [admin_button(lang)])
        await self._notify_nextgame(g)

    async def _notify_nextgame(self, g: Game) -> None:
        """The lobby is open: tell in private who asked with /nextgame (they still have to /join)."""
        for uid, _name in self.db.nextgame_take(g.chat_id, config.NEXTGAME_HOURS * 3600):
            if uid not in g.players:
                await self.io.send_dm(uid, T(g.lang, "nextgame_dm", chat=esc(self.db.chat_title(g.chat_id)),
                                             mode=T(g.lang, f"mode_{g.mode}"),
                                             minutes=config.LOBBY_SECONDS // 60))

    async def nextgame(self, chat_id: int, uid: int, name: str, lang: str) -> None:
        """/nextgame: a private notice when the next match opens here (again: cancel)."""
        g = self.games.get(chat_id)
        if g and g.phase == Phase.LOBBY:
            return await self._say(chat_id, g.lang, "nextgame_lobby_open")
        if not self.db.has_dm(uid):
            return await self.io.send(chat_id, T(lang, "nextgame_need_dm"),
                                      [(T(lang, "btn_start_bot"), self._bot_url(f"j{abs(chat_id)}"))])
        if self.db.nextgame_toggle(chat_id, uid, name):
            await self._say(chat_id, lang, "nextgame_on", name=esc(name), hours=config.NEXTGAME_HOURS)
        else:
            await self._say(chat_id, lang, "nextgame_off", name=esc(name))

    async def join(self, chat_id: int, uid: int, name: str, lang: str) -> None:
        g = self.games.get(chat_id)
        if not g:
            return await self._say(chat_id, lang, "no_game")
        if uid in g.players:
            return await self._say(chat_id, g.lang, "join_already")
        if uid in self.user_game:
            return await self._say(chat_id, g.lang, "join_other")
        if g.mode == "broken":
            if g.phase != Phase.LOBBY:
                return await self._say(chat_id, g.lang, "join_closed_broken")
            if not self.db.has_dm(uid):
                return await self._need_dm(chat_id, g.lang)
        elif g.phase != Phase.LOBBY and self.db.get_settings(chat_id)["latejoin"] == "off":
            return await self._say(chat_id, g.lang, "join_closed")
        g.players[uid] = g.names[uid] = name
        self.user_game[uid] = chat_id
        if g.phase == Phase.LOBBY:
            return await self._say(chat_id, g.lang, "joined", name=esc(name), n=len(g.players))
        g.queue.append(uid)         # joined late: guesses at once, draws at the end
        g.scores.setdefault(uid, 0)
        await self._say(chat_id, g.lang, "joined_late", name=esc(name))

    async def ready(self, chat_id: int, uid: int, lang: str) -> None:
        g = self.games.get(chat_id)
        if not g or g.phase != Phase.LOBBY:
            return await self._say(chat_id, lang, "no_lobby")
        if uid not in g.players:
            return await self._say(chat_id, g.lang, "only_players")
        if len(g.players) < g.min_players:
            return await self._say(chat_id, g.lang, "ready_need", min=g.min_players,
                                   n=len(g.players))
        await self._begin(g)

    async def wait(self, chat_id: int, uid: int, arg: str, lang: str) -> None:
        g = self.games.get(chat_id)
        if not g or g.phase != Phase.LOBBY:
            return await self._say(chat_id, lang, "no_lobby")
        if uid not in g.players:
            return await self._say(chat_id, g.lang, "only_players")
        try:
            minutes = float(arg.replace(",", "."))
        except ValueError:
            minutes = math.nan
        if not math.isfinite(minutes) or minutes <= 0:
            return await self._say(chat_id, g.lang, "wait_usage")
        if minutes > config.WAIT_MAX_MINUTES:
            return await self._say(chat_id, g.lang, "wait_max", max=config.WAIT_MAX_MINUTES)
        g.lobby_end += minutes * 60
        left = g.lobby_end - self.io.now()
        self._timer(g, "lobby", left, self._lobby_expired)
        await self._say(chat_id, g.lang, "wait_ok", added=fmt_duration(minutes * 60),
                        left=fmt_duration(left))

    async def stop(self, chat_id: int, uid: int, lang: str) -> None:
        g = self.games.get(chat_id)
        if not g:
            return
        if uid != g.creator and not await self.io.is_admin(chat_id, uid):
            return await self._say(chat_id, g.lang, "stop_denied")
        self._close(g)
        LOG.info("game in %s stopped by %s", chat_id, uid)
        await self._say(chat_id, g.lang, "stopped")

    async def quit(self, chat_id: int, uid: int, lang: str) -> None:
        g = self.games.get(chat_id)
        if not g or uid not in g.players:
            return await self._say(chat_id, lang, "not_in_game")
        name = g.players.pop(uid)
        self.user_game.pop(uid, None)
        g.queue = [u for u in g.queue if u != uid]
        await self._say(chat_id, g.lang, "quit_ok", name=esc(name))
        if g.phase == Phase.LOBBY:
            if not g.players:
                self._close(g)
            elif uid == g.creator:
                g.creator = next(iter(g.players))
            return
        if len(g.players) < config.MIN_PLAYERS_TO_CONTINUE:
            return await self._finish(g, T(g.lang, "too_few") + "\n\n")
        if g.mode == "broken":
            return await self._bk_check_done(g)
        t = g.turn
        if t and t.drawer == uid and g.phase == Phase.DRAWING:
            await self._end_turn(g, "left")
        elif t and t.drawer == uid and g.phase in (Phase.CHOOSING, Phase.STARTING):
            await self._skip(g, "skip_left", name)
        elif g.phase == Phase.DRAWING and self._everyone_guessed(g):
            await self._end_turn(g, "all")

    async def _lobby_expired(self, g: Game) -> None:
        if len(g.players) >= g.min_players:
            return await self._begin(g)
        self._close(g)
        await self._say(g.chat_id, g.lang, "not_enough", min=g.min_players)

    # ================================================================ turns
    async def _begin(self, g: Game) -> None:
        if g.mode == "broken":
            return await self._bk_begin(g)
        g.pool = self.words_for(g.chat_id, g.lang)
        order = list(g.players)
        self.rng.shuffle(order)
        g.queue = order * laps(len(order))
        g.scores = {u: 0 for u in order}
        g.started_at = self.io.now()
        g.go(Phase.BREAK)           # kills the lobby timer
        LOG.info("game in %s starts: %d players, %d turns", g.chat_id, len(order), len(g.queue))
        await self._say(g.chat_id, g.lang, "game_start", n=len(order), turns=len(g.queue))
        await self._next_turn(g, "")

    async def _next_turn(self, g: Game, header: str) -> None:
        """Announce the next drawer (10 seconds break), or end the match."""
        while g.queue and g.queue[0] not in g.players:
            g.queue.pop(0)
        if not g.queue or len(g.players) < config.MIN_PLAYERS_TO_CONTINUE:
            return await self._finish(g, header)
        drawer = g.queue.pop(0)
        g.turn_no += 1
        g.turn = Turn(drawer=drawer, choices=words.pick_choices(g.pool, g.used, self.rng))
        g.snapshot, g.snap_ver = None, 0
        g.go(Phase.BREAK, config.BREAK_SECONDS, self.io.now())
        self._timer(g, "break", config.BREAK_SECONDS, self._open_choice)
        text = header + T(g.lang, "next_drawer", name=esc(g.players[drawer]), n=g.turn_no,
                          total=g.total_turns, secs=config.BREAK_SECONDS)
        label = "btn_play" if g.mode == "classic" else "btn_open"
        await self.io.send(g.chat_id, text, [(T(g.lang, label), self.link(g.chat_id))])

    async def _open_choice(self, g: Game) -> None:
        if g.turn.drawer not in g.players:
            return await self._next_turn(g, "")
        g.go(Phase.CHOOSING, config.CHOOSE_SECONDS, self.io.now())
        self._timer(g, "choose", config.CHOOSE_SECONDS, self._choice_timeout)

    async def _choice_timeout(self, g: Game) -> None:
        await self._skip(g, "skip_no_choice", g.players.get(g.turn.drawer, "?"))

    async def _start_timeout(self, g: Game) -> None:
        await self._skip(g, "skip_no_start", g.players.get(g.turn.drawer, "?"))

    async def _skip(self, g: Game, key: str, name: str) -> None:
        """The drawer's turn is lost (nothing drawn, no points)."""
        g.go(Phase.BREAK)
        await self._next_turn(g, T(g.lang, key, name=esc(name)) + "\n\n")

    async def _time_up(self, g: Game) -> None:
        await self._end_turn(g, "time")

    def _everyone_guessed(self, g: Game) -> bool:
        t = g.turn
        guessers = [u for u in g.players if u != t.drawer]
        return bool(guessers) and all(u in t.guessed for u in guessers)

    async def _end_turn(self, g: Game, reason: str) -> None:
        """Reveal the word, give the drawer's points, show the scores, move on."""
        t = g.turn
        g.go(Phase.BREAK)
        n = len(t.guessed)
        if g.mode == "speedrun":
            d_pts = speedrun_drawer_points(t.win_remaining, t.hints, g.draw_seconds) if n else 0
        else:
            d_pts = drawer_points(n, t.word.diff, t.hints)
        if d_pts and t.drawer in g.players:
            g.scores[t.drawer] = g.scores.get(t.drawer, 0) + d_pts
        key = {"all": "result_all", "time": "result_time", "skip": "result_skip",
               "left": "result_left", "win": "result_win"}[reason]
        header = T(g.lang, key, word=esc(t.word.word))
        if n:
            gained = [f"✅ {esc(g.name(u))} +{p}" for u, p in t.guessed.items()]
            if d_pts:
                gained.append(f"🎨 {esc(g.name(t.drawer))} +{d_pts}")
            header += "\n" + " · ".join(gained)
        else:
            header += "\n" + T(g.lang, "nobody_guessed")
        t.header = header + "\n\n" + self._board(g) + "\n\n"
        if reason != "left" and t.drawer in g.players and (t.events or g.snapshot):
            # the picture in the chat must be the finished drawing: the drawer's Mini App, which
            # sees the round is over, sends the final canvas (or we use the last one after a moment)
            t.final_open = True
            self._timer(g, "final", config.FINAL_SNAPSHOT_WAIT, self._final_timeout)
            return
        await self._show_final(g)

    async def _final_timeout(self, g: Game) -> None:
        if g.turn and g.turn.final_open:
            await self._show_final(g)

    async def _show_final(self, g: Game) -> None:
        """Post (or complete) the picture of the round in the chat, then go on."""
        t = g.turn
        t.final_open = False
        if g.snapshot:
            cap = f"{words.CATEGORY_ICON.get(t.word.cat, '')} <b>{esc(t.word.word)}</b>"
            if t.photo_msg:
                await self.io.edit_photo(g.chat_id, t.photo_msg, g.snapshot, cap)
            else:
                t.photo_msg = await self.io.send_photo(g.chat_id, g.snapshot, cap)
        await self._next_turn(g, t.header)

    async def _finish(self, g: Game, header: str) -> None:
        if g.mode == "broken":
            return await self._bk_finish(g, header)
        rows = ranking(g.scores, g.players)
        top = rows[0][3] if rows else 0
        lines = [f"{MEDALS.get(r, f'{r}.')} {esc(n)} — {p}" for r, _, n, p in rows]
        text = header + T(g.lang, "game_over") + "\n" + "\n".join(lines)
        winners = [esc(n) for r, _, n, p in rows if r == 1 and p > 0]
        if winners:
            text += "\n\n" + T(g.lang, "winner", names=", ".join(winners))
        duration = int(self.io.now() - (g.started_at or self.io.now()))
        if not g.test:
            self.db.save_game(
                g.chat_id, g.lang, g.turn_no, duration,
                [(r, u, n, p, int(r == 1 and top > 0), g.guesses.get(u, 0), g.drawings.get(u, 0))
                 for r, u, n, p in rows])
        LOG.info("game in %s over after %d turns", g.chat_id, g.turn_no)
        self._close(g)
        await self.io.send(g.chat_id, text)

    # ================================================================ guesses (group chat)
    def _award(self, g: Game, uid: int) -> int:
        """Score a correct guess (any channel) and return the points."""
        t = g.turn
        remaining = t.started_at + g.draw_seconds - self.io.now()
        pts = guess_points(remaining, t.word.diff, t.hints, g.draw_seconds)
        t.guessed[uid] = pts
        g.scores[uid] = g.scores.get(uid, 0) + pts
        g.guesses[uid] = g.guesses.get(uid, 0) + 1
        t.win_remaining = remaining
        return pts

    async def on_message(self, chat_id: int, uid: int, text: str, message_id: int) -> None:
        g = self.games.get(chat_id)
        if not g or g.phase != Phase.DRAWING or uid not in g.players:
            return
        t = g.turn
        word = t.word
        if uid == t.drawer or uid in t.guessed:
            if words.contains_answer(word, text):       # don't let the answer leak
                await self._del(g, chat_id, message_id)
            return
        if g.mode == "classic":                         # guesses are typed in the Mini App
            if words.is_correct(word, text) or words.contains_answer(word, text):
                await self._del(g, chat_id, message_id)
                if uid not in t.chat_warned:
                    t.chat_warned.add(uid)
                    await self._say(chat_id, g.lang, "classic_chat_notice", name=esc(g.players[uid]))
            return
        if words.is_correct(word, text):
            pts = self._award(g, uid)
            if g.mode == "speedrun":                    # the first correct guess wins the round
                await self._del(g, chat_id, message_id)
                return await self._end_turn(g, "win")
            done = self._everyone_guessed(g)
            await self._del(g, chat_id, message_id)
            await self._say(chat_id, g.lang, "guessed", name=esc(g.players[uid]), pts=pts)
            if done and g.phase == Phase.DRAWING:
                await self._end_turn(g, "all")
        elif words.is_close(word, text) and \
                t.close_notices.get(uid, 0) < config.CLOSE_NOTICES_PER_TURN:
            t.close_notices[uid] = t.close_notices.get(uid, 0) + 1
            await self.io.send(chat_id, T(g.lang, "close"), reply_to=message_id or None)

    # ================================================================ classic mode: guesses and live drawing
    async def web_guess(self, chat_id: int, uid: int, text: str) -> dict:
        """A guess typed in the Mini App (classic mode)."""
        g = self.games.get(chat_id)
        if not g or not g.turn:
            raise GameError("no_game")
        if g.mode != "classic":
            raise GameError("wrong_mode")
        t = g.turn
        if g.phase != Phase.DRAWING:
            raise GameError("wrong_phase")
        if uid not in g.players:
            raise GameError("not_player")
        if uid == t.drawer:
            raise GameError("is_drawer")
        if uid in t.guessed:
            raise GameError("already_guessed")
        text = " ".join(str(text).split())[:config.ATTEMPT_MAX_LEN]
        if not text:
            raise GameError("bad_request")
        now = self.io.now()
        if now - t.last_attempt.get(uid, -1e9) < config.GUESS_MIN_INTERVAL:
            raise GameError("too_fast")
        t.last_attempt[uid] = now
        attempt_id = len(t.attempts)
        name = g.players[uid]
        if words.is_correct(t.word, text):
            pts = self._award(g, uid)
            t.attempts.append({"u": name, "t": None, "r": True})     # the word itself is never shown
            done = self._everyone_guessed(g)
            await self._say(chat_id, g.lang, "guessed", name=esc(name), pts=pts)
            if done and g.phase == Phase.DRAWING:
                await self._end_turn(g, "all")
            return {"result": "right", "pts": pts, "id": attempt_id}
        shown = "🙈" if words.contains_answer(t.word, text) else text    # a sentence with the answer in it
        t.attempts.append({"u": name, "t": shown, "r": False})
        return {"result": "close" if words.is_close(t.word, text) else "wrong", "id": attempt_id}

    def post_events(self, chat_id: int, uid: int, frm, events) -> int:
        """The drawer streams its strokes; `frm` is the index of the first event of the batch,
        so a batch sent twice is stored once."""
        g, t = self._turn_of(chat_id, uid, Phase.STARTING, Phase.DRAWING)
        try:
            clean = strokes.clean_events(events)
        except ValueError:
            raise GameError("bad_request")
        if isinstance(frm, bool) or not isinstance(frm, int) or not 0 <= frm <= len(t.events):
            raise GameError("gap", have=len(t.events))
        new = clean[len(t.events) - frm:]
        if len(t.events) + len(new) > config.EVENTS_MAX:
            raise GameError("too_many")
        t.events.extend(new)
        return len(t.events)

    def live(self, chat_id: int, turn, since, att, with_events: bool = True) -> dict:
        """New drawing events and guesses since the client's cursors (it restarts from 0 on a new turn)."""
        g = self.games.get(chat_id)
        if not g or not g.turn:
            return {"turn": None}
        t = g.turn
        same = turn == g.turn_no
        ev = since if same and isinstance(since, int) and 0 <= since <= len(t.events) else 0
        at = att if same and isinstance(att, int) and 0 <= att <= len(t.attempts) else 0
        return {"turn": g.turn_no, "ev": ev, "events": t.events[ev:ev + 4000] if with_events else [],
                "att": at, "attempts": t.attempts[at:]}

    # ================================================================ Mini App requests
    def _turn_of(self, chat_id: int, uid: int, *phases: Phase) -> tuple[Game, Turn]:
        g = self.games.get(chat_id)
        if not g or not g.turn:
            raise GameError("no_game")
        if g.turn.drawer != uid:
            raise GameError("not_drawer")
        if g.phase not in phases:
            raise GameError("wrong_phase")
        return g, g.turn

    def web_state(self, chat_id: int, uid: int) -> dict:
        g = self.games.get(chat_id)
        if not g:
            return {"phase": "none", "lang": self.db.get_lang(chat_id)}
        out: dict = {"phase": g.phase.name.lower(), "lang": g.lang, "snap": g.snap_ver,
                     "mode": g.mode,
                     "scores": [[n, p] for _, _, n, p in ranking(g.scores, g.players)],
                     "players": list(g.players.values()), "role": "viewer",
                     "in_game": uid in g.players}
        if g.test:
            out["test"] = {"players": [{"id": u, "name": g.names.get(u, "?")} for u in g.test_ids]}
        if g.deadline:
            out["ends_in"] = max(0.0, g.deadline - self.io.now())
        if g.mode == "broken":
            return self._bk_web_state(g, uid, out)
        t = g.turn
        if not t or g.phase == Phase.LOBBY:
            return out
        out.update(drawer=g.players.get(t.drawer, "?"), turn=g.turn_no, turns=g.total_turns)
        if t.word and g.phase in (Phase.STARTING, Phase.DRAWING):
            out["cat"] = t.word.cat
            out["hints"] = t.hints
            out["hints_max"] = words.max_hints(t.word.word)
            if t.hints:
                out["mask"] = words.make_mask(t.word.word, t.revealed())
        if uid in t.guessed:
            out["me_guessed"] = t.guessed[uid]
        if t.drawer == uid:
            out["role"] = "drawer"
            if t.final_open:
                out["final"] = True             # send the finished canvas now
            if g.phase == Phase.CHOOSING:
                out["choices"] = [{"i": i, "word": e.word, "diff": e.diff, "cat": e.cat}
                                  for i, e in enumerate(t.choices)]
            if t.word and g.phase in (Phase.STARTING, Phase.DRAWING):
                out["word"] = t.word.word
                out["penalty"] = int(config.HINT_PENALTY * 100)
        return out

    def choose(self, chat_id: int, uid: int, index: int) -> None:
        g, t = self._turn_of(chat_id, uid, Phase.CHOOSING)
        if not 0 <= index < len(t.choices):
            raise GameError("bad_choice")
        t.word = t.choices[index]
        positions = words.letter_positions(t.word.word)
        self.rng.shuffle(positions)
        t.reveal_order = positions
        g.used.add(words.compact(t.word.word))
        g.go(Phase.STARTING, config.START_SECONDS, self.io.now())
        self._timer(g, "start", config.START_SECONDS, self._start_timeout)

    async def start_drawing(self, chat_id: int, uid: int) -> None:
        """First stroke: the clock starts."""
        g, t = self._turn_of(chat_id, uid, Phase.STARTING)
        t.started_at = self.io.now()
        g.drawings[uid] = g.drawings.get(uid, 0) + 1
        g.go(Phase.DRAWING, g.draw_seconds, t.started_at)
        self._timer(g, "end", g.draw_seconds, self._time_up)
        self._timer(g, "snap", config.SNAPSHOT_FIRST_SECONDS, self._snap_tick)
        classic = g.mode == "classic"
        await self.io.send(
            g.chat_id,
            T(g.lang, "drawing_started_classic" if classic else "drawing_started",
              name=esc(g.players[uid]), secs=dur(g.lang, g.draw_seconds),
              icon=words.CATEGORY_ICON.get(t.word.cat, "")),
            [(T(g.lang, "btn_play" if classic else "btn_watch"),
              self.link(g.chat_id, compact=not classic))])

    async def final_snapshot(self, chat_id: int, uid: int, data: bytes) -> None:
        """The finished canvas, sent by the drawer once the round is over."""
        g, t = self._turn_of(chat_id, uid, Phase.BREAK)
        if not t.final_open:
            raise GameError("wrong_phase")
        if len(data) > config.SNAPSHOT_MAX_BYTES or data[:3] != b"\xff\xd8\xff":
            raise GameError("bad_image")
        g.snapshot = data
        g.snap_ver += 1
        await self._show_final(g)

    def snapshot(self, chat_id: int, uid: int, data: bytes) -> None:
        g, _ = self._turn_of(chat_id, uid, Phase.DRAWING)
        if len(data) > config.SNAPSHOT_MAX_BYTES or data[:3] != b"\xff\xd8\xff":
            raise GameError("bad_image")
        now = self.io.now()
        if now - g.last_snap_at < config.SNAPSHOT_MIN_INTERVAL:
            raise GameError("too_fast")
        g.last_snap_at = now
        g.snapshot = data
        g.snap_ver += 1

    async def _snap_tick(self, g: Game) -> None:
        """Show the canvas in the chat: one photo, then refreshed in place."""
        t, gen = g.turn, g.gen
        ver, hints = g.snap_ver, t.hints
        if g.snapshot and t.photo_msg is None:
            t.posted_ver, t.posted_hints = ver, hints
            t.photo_msg = await self.io.send_photo(g.chat_id, g.snapshot, self._caption(g))
        elif t.photo_msg and (ver != t.posted_ver or hints != t.posted_hints):
            t.posted_ver, t.posted_hints = ver, hints
            await self.io.edit_photo(g.chat_id, t.photo_msg, g.snapshot, self._caption(g))
        if self.games.get(g.chat_id) is g and g.gen == gen:
            self._timer(g, "snap", config.SNAPSHOT_EDIT_SECONDS, self._snap_tick)

    async def hint(self, chat_id: int, uid: int) -> str:
        g, t = self._turn_of(chat_id, uid, Phase.DRAWING)
        if t.hints >= words.max_hints(t.word.word):
            raise GameError("no_more_hints")
        t.hints += 1
        mask = words.make_mask(t.word.word, t.revealed())
        await self._say(g.chat_id, g.lang, "hint_given", mask=mask,
                        pct=int(config.HINT_PENALTY * 100 * t.hints))
        return mask

    async def skip(self, chat_id: int, uid: int) -> None:
        g, t = self._turn_of(chat_id, uid, Phase.CHOOSING, Phase.STARTING, Phase.DRAWING)
        if g.phase == Phase.DRAWING:
            await self._end_turn(g, "skip")
        else:
            await self._skip(g, "skip_by_drawer", g.players.get(uid, "?"))
