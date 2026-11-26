"""Code Stroke (beta): two teams, a 5x5 grid of words, and spy masters who give clues by drawing.

Blue starts (9 words), red follows (8); 7 words are neutral and 1 is the assassin. Each spy master (the only
one who sees the key, in the Mini App) draws a clue and chooses a number; the team taps words, in the chat or
in the Mini App, up to number + 1 of them. A wrong word ends the turn, the assassin ends the match.
Mixed into `Engine`, which provides io, db, games, user_game, rng, timers and `words_for`."""
import html
import logging

import config
import words
from errors import GameError
from game import CodeStrokeState, Game, Phase
from i18n import T

LOG = logging.getLogger("carmink.codestroke")
EMOJI = {"B": "🟦", "R": "🟥", "N": "🟨", "K": "⬛"}
TEAM_ICON = {"B": "🔵", "R": "🔴"}


def _esc(s: str) -> str:
    return html.escape(s, quote=False)


def other(team: str) -> str:
    return "R" if team == "B" else "B"


class CodeStrokeMixin:
    # ================================================================ start
    async def _cs_begin(self, g: Game) -> None:
        g.pool = words.load(g.lang) if g.test else self.words_for(g.chat_id, g.lang)
        unique, seen = [], set()
        for e in g.pool:
            if words.compact(e.word) not in seen:
                seen.add(words.compact(e.word))
                unique.append(e)
        if len(unique) < 25:
            self._close(g)
            return await self._say(g.chat_id, g.lang, "cm_no_words")
        grid = self.rng.sample(unique, 25)
        key = ["B"] * config.CODESTROKE_BLUE + ["R"] * config.CODESTROKE_RED + ["N"] * config.CODESTROKE_NEUTRAL + ["K"]
        self.rng.shuffle(key)
        order = list(g.players)
        self.rng.shuffle(order)
        half = len(order) // 2                      # blue starts with one more word: red gets the odd player
        teams = {u: ("B" if i < half else "R") for i, u in enumerate(order)}
        spies = {t: next(u for u in order if teams[u] == t) for t in "BR"}
        g.scores = {u: 0 for u in order}
        g.started_at = self.io.now()
        g.cs = CodeStrokeState(grid=grid, key=key, teams=teams, spies=spies)
        LOG.info("code stroke in %s: %d players", g.chat_id, len(order))
        names = lambda t: ", ".join(_esc(g.name(u)) + (" 🕵️" if u == spies[t] else "") for u in order if teams[u] == t)
        await self.io.send(g.chat_id, T(g.lang, "cs_start", blue=names("B"), red=names("R"),
                                        nb=config.CODESTROKE_BLUE, nr=config.CODESTROKE_RED),
                           [(T(g.lang, "btn_open"), self.link(g.chat_id))])
        await self._cs_clue_turn(g)

    # ================================================================ the grid in the chat
    def _cs_keyboard(self, g: Game, final: bool = False) -> list:
        cs = g.cs
        rows = []
        for r in range(5):
            row = []
            for c in range(5):
                i = r * 5 + c
                label = f"{EMOJI[cs.key[i]]} {cs.grid[i].word}" if cs.revealed[i] or final else cs.grid[i].word
                row.append((label, f"cb:cs:g:{i}"))
            rows.append(row)
        if not final:
            rows.append([(T(g.lang, "cs_btn_pass"), "cb:cs:pass"), (T(g.lang, "btn_open"), self.link(g.chat_id))])
        return rows

    def _cs_status(self, g: Game) -> str:
        cs = g.cs
        head = f"{TEAM_ICON[cs.team]} <b>{_esc(g.name(cs.spies[cs.team]))}</b> 🕵️"
        score = f"🔵 {cs.left('B')} · 🔴 {cs.left('R')}"
        if cs.stage == "clue":
            return T(g.lang, "cs_status_clue", head=head, score=score, secs=g.draw_seconds)
        return T(g.lang, "cs_status_guess", head=head, score=score, n=cs.number, left=cs.guesses_left)

    async def _cs_post_grid(self, g: Game) -> None:
        cs = g.cs
        await self._cs_close_grid(g)
        cs.grid_msg = await self.io.send(g.chat_id, self._cs_status(g), self._cs_keyboard(g))

    async def _cs_close_grid(self, g: Game) -> None:
        cs = g.cs
        if cs.grid_msg:
            await self.io.edit_text(g.chat_id, cs.grid_msg, T(g.lang, "cs_turn_over", score=f"🔵 {cs.left('B')} · 🔴 {cs.left('R')}"),
                                    self._cs_keyboard(g))
            cs.grid_msg = None

    async def _cs_update_grid(self, g: Game) -> None:
        cs = g.cs
        if cs.grid_msg:
            await self.io.edit_text(g.chat_id, cs.grid_msg, self._cs_status(g), self._cs_keyboard(g))

    # ================================================================ turns
    async def _cs_clue_turn(self, g: Game) -> None:
        cs = g.cs
        cs.stage, cs.draft, cs.number, cs.guessed_now = "clue", None, 0, 0
        cs.turn_no += 1
        g.go(Phase.STEP, g.draw_seconds, self.io.now())
        self._timer(g, "cs", g.draw_seconds + config.BROKEN_GRACE_SECONDS, self._cs_clue_timeout)
        await self._cs_post_grid(g)
        await self._tnotify(g)

    async def _cs_clue_timeout(self, g: Game) -> None:
        cs = g.cs
        if cs and cs.stage == "clue":
            await self._say(g.chat_id, g.lang, "cs_no_clue", name=_esc(g.name(cs.spies[cs.team])))
            await self._cs_next_team(g)

    def cs_draft(self, g: Game, uid: int, data: bytes) -> None:
        cs = self._cs_spy(g, uid)
        now = self.io.now()
        if now - cs.last_draft < config.SNAPSHOT_MIN_INTERVAL:
            raise GameError("too_fast")
        cs.last_draft, cs.draft = now, self._cs_jpeg(data)

    async def cs_submit(self, g: Game, uid: int, data: bytes, number: int) -> None:
        cs = self._cs_spy(g, uid)
        if not 1 <= number <= 9:
            raise GameError("bad_number")
        jpeg = self._cs_jpeg(data)
        cs.stage, cs.number = "guess", number
        cs.guesses_left = number + 1
        cs.clue_no += 1
        g.go(Phase.STEP, config.CODESTROKE_GUESS_SECONDS, self.io.now())
        self._timer(g, "cs", config.CODESTROKE_GUESS_SECONDS, self._cs_guess_timeout)
        await self.io.send_photo(g.chat_id, jpeg, T(g.lang, "cs_clue", icon=TEAM_ICON[cs.team],
                                                    name=_esc(g.name(uid)), n=number))
        await self._cs_update_grid(g)

    @staticmethod
    def _cs_jpeg(data: bytes) -> bytes:
        if len(data) > config.BROKEN_JPEG_MAX or data[:3] != b"\xff\xd8\xff":
            raise GameError("bad_image")
        return data

    @staticmethod
    def _cs_spy(g: Game, uid: int) -> CodeStrokeState:
        cs = g.cs
        if not cs or g.phase != Phase.STEP or cs.stage != "clue":
            raise GameError("wrong_phase")
        if cs.spies.get(cs.team) != uid or uid not in g.players:
            raise GameError("not_player")
        return cs

    async def _cs_guess_timeout(self, g: Game) -> None:
        cs = g.cs
        if cs and cs.stage == "guess":
            await self._say(g.chat_id, g.lang, "cs_time_up", icon=TEAM_ICON[cs.team])
            await self._cs_next_team(g)

    async def _cs_next_team(self, g: Game) -> None:
        g.cs.team = other(g.cs.team)
        await self._cs_clue_turn(g)

    # ================================================================ guesses
    def _cs_can_pick(self, g: Game, uid: int) -> str | None:
        """None if `uid` may pick words now, otherwise the reason (shown to the player)."""
        cs = g.cs
        if not cs or uid not in g.players:
            return T(g.lang, "only_players")
        if cs.stage != "guess":
            return T(g.lang, "cs_wait_clue")
        if cs.teams.get(uid) != cs.team:
            return T(g.lang, "cs_not_your_turn")
        if cs.spies[cs.team] == uid:
            return T(g.lang, "cs_spy_no_pick")
        return None

    async def cs_pick(self, g: Game, uid: int, index: int) -> str | None:
        why = self._cs_can_pick(g, uid)
        if why:
            return why
        cs = g.cs
        if not 0 <= index < 25 or cs.revealed[index]:
            return T(g.lang, "cs_taken")
        cs.revealed[index] = True
        kind = cs.key[index]
        word = _esc(cs.grid[index].word)
        who = _esc(g.name(uid))
        if kind == "K":
            await self.io.send(g.chat_id, T(g.lang, "cs_assassin", name=who, word=word))
            await self._cs_end(g, other(cs.team), "assassin")
            return None
        if cs.left("B") == 0 or cs.left("R") == 0:
            await self.io.send(g.chat_id, f"{EMOJI[kind]} {who}: {word}")
            await self._cs_end(g, "B" if cs.left("B") == 0 else "R", "words")
            return None
        cs.guessed_now += 1
        cs.guesses_left -= 1
        await self.io.send(g.chat_id, f"{EMOJI[kind]} {who}: <b>{word}</b>")
        if kind != cs.team or cs.guesses_left <= 0:
            await self.io.send(g.chat_id, T(g.lang, "cs_wrong_word" if kind != cs.team else "cs_no_more"))
            await self._cs_next_team(g)
        else:
            await self._cs_update_grid(g)
        return None

    async def cs_pass(self, g: Game, uid: int) -> str | None:
        why = self._cs_can_pick(g, uid)
        if why:
            return why
        if g.cs.guessed_now < 1:
            return T(g.lang, "cs_pick_one")
        await self.io.send(g.chat_id, T(g.lang, "cs_passed", icon=TEAM_ICON[g.cs.team], name=_esc(g.name(uid))))
        await self._cs_next_team(g)
        return None

    # ================================================================ end
    async def _cs_end(self, g: Game, winner: str, how: str) -> None:
        cs = g.cs
        cs.winner, cs.ended_by, cs.stage = winner, how, "over"
        g.go(Phase.BREAK)
        winners = [u for u, t in cs.teams.items() if t == winner and u in g.players]
        for u in winners:
            g.scores[u] = 1
        grid = "\n".join("".join(EMOJI[cs.key[r * 5 + c]] for c in range(5)) for r in range(5))
        text = T(g.lang, "cs_over", icon=TEAM_ICON[winner],
                 names=", ".join(_esc(g.name(u)) for u in winners)) + "\n\n" + grid
        if cs.grid_msg:
            await self.io.edit_text(g.chat_id, cs.grid_msg, T(g.lang, "cs_turn_over", score=f"🔵 {cs.left('B')} · 🔴 {cs.left('R')}"),
                                    self._cs_keyboard(g, final=True))
        if not g.test:
            from game import ranking
            rows = ranking(g.scores, g.players)
            self.db.save_game(g.chat_id, g.lang, cs.clue_no, int(self.io.now() - (g.started_at or self.io.now())),
                              [(r, u, n, p, int(u in winners), 0, 0) for r, u, n, p in rows])
        self._close(g)
        await self.io.send(g.chat_id, text)

    async def cs_callback(self, g: Game, uid: int, data: str) -> str | None:
        parts = data.split(":")[1:]
        if parts[0] == "g" and len(parts) == 2 and parts[1].isdigit():
            return await self.cs_pick(g, uid, int(parts[1]))
        if parts[0] == "pass":
            return await self.cs_pass(g, uid)
        return None

    async def cs_left(self, g: Game, uid: int) -> None:
        cs = g.cs
        team = cs.teams.get(uid)
        mates = [u for u in g.players if cs.teams.get(u) == team]
        if len(g.players) < config.MIN_PLAYERS_CODESTROKE - 1 or len(mates) < 1 or uid == cs.spies.get(team):
            self._close(g)
            return await self._say(g.chat_id, g.lang, "cs_aborted")

    # ================================================================ Mini App state
    def _cs_web_state(self, g: Game, uid: int, out: dict) -> dict:
        cs = g.cs
        if not cs:
            return out
        me_in = uid in g.players
        mine = cs.teams.get(uid) if me_in else None
        spy = me_in and cs.spies.get(mine) == uid
        over = cs.stage == "over"
        cells = []
        for i, e in enumerate(cs.grid):
            seen = cs.revealed[i] or spy or over
            cells.append({"w": e.word, "k": cs.key[i] if seen else None, "r": cs.revealed[i]})
        out["cs"] = {"stage": cs.stage, "team": cs.team, "me": mine, "spy": spy, "grid": cells,
                     "number": cs.number, "left": cs.guesses_left, "blue": cs.left("B"), "red": cs.left("R"),
                     "spies": {t: g.name(u) for t, u in cs.spies.items()},
                     "can_pick": me_in and self._cs_can_pick(g, uid) is None,
                     "teams": {str(u): t for u, t in cs.teams.items()} if over else None}
        out.update(turn=cs.turn_no, turns=0)
        if me_in and spy and cs.stage == "clue" and cs.team == mine and g.phase == Phase.STEP:
            out["bk"] = {"kind": "draw", "active": True, "done": False, "number": True,
                         "prompt": T(g.lang, "cs_prompt", icon=TEAM_ICON[mine]), "raw": True}
        return out
