"""Carmeleon (beta): everybody knows the key word of the table except the chameleon.

The group draws something linked to the key, in turn (Mini App); the drawings are posted in the chat.
Then the players decide by vote whether to go for another lap (once) and vote for the chameleon with the
buttons under each drawing. If the chameleon is unmasked, it can still win by naming the key word.
Mixed into `Engine`, which provides io, db, games, user_game, rng, timers and `words_for`."""
import html
import io
import logging

import config
import gifmaker
import words
from errors import GameError
from game import CarmeleonState, Game, Phase, ranking
from i18n import T

LOG = logging.getLogger("carmink.carmeleon")


def _esc(s: str) -> str:
    return html.escape(s, quote=False)


def _side_by_side(first: bytes, second: bytes) -> bytes:
    """Two drawings of the same player in one picture (the second lap)."""
    from PIL import Image
    a, b = (Image.open(io.BytesIO(x)).convert("RGB") for x in (first, second))
    h = min(a.height, b.height)
    a, b = a.resize((int(a.width * h / a.height), h)), b.resize((int(b.width * h / b.height), h))
    out = Image.new("RGB", (a.width + b.width + 6, h), "white")
    out.paste(a, (0, 0))
    out.paste(b, (a.width + 6, 0))
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=80)
    return buf.getvalue()


class CarmeleonMixin:
    # ================================================================ start
    def _cm_pick_table(self, g: Game, n: int) -> list[words.Entry] | None:
        """n words from three different categories (n // 3 each); None if the dictionary is too small."""
        pool = g.pool
        per = n // 3
        by_cat: dict[str, list[words.Entry]] = {}
        for e in pool:
            if e.cat != "other":
                by_cat.setdefault(e.cat, []).append(e)
        cats = [c for c, es in by_cat.items() if len(es) >= per]
        if len(cats) < 3:
            return None
        self.rng.shuffle(cats)
        table, seen = [], set()
        for c in cats[:3]:
            es = list(by_cat[c])
            self.rng.shuffle(es)
            got = 0
            for e in es:
                if words.compact(e.word) not in seen and got < per:
                    seen.add(words.compact(e.word))
                    table.append(e)
                    got += 1
        return table if len(table) == n else None

    async def _cm_begin(self, g: Game) -> None:
        g.pool = words.load(g.lang) if g.test else self.words_for(g.chat_id, g.lang)
        table = self._cm_pick_table(g, g.cm_words)
        if not table:
            self._close(g)
            return await self._say(g.chat_id, g.lang, "cm_no_words")
        order = list(g.players)
        self.rng.shuffle(order)
        g.scores = {u: 0 for u in order}
        g.started_at = self.io.now()
        g.cm = CarmeleonState(table=table, key=self.rng.randrange(len(table)), chameleon=self.rng.choice(order),
                              order=order, started_at=g.started_at)
        LOG.info("carmeleon in %s: %d players, %d words", g.chat_id, len(order), len(table))
        await self.io.send(g.chat_id, T(g.lang, "cm_start", n=len(order), table=self._cm_table_text(g)),
                           [(T(g.lang, "btn_open"), self.link(g.chat_id))])
        await self._cm_turn(g)

    def _cm_table_text(self, g: Game) -> str:
        cm, lines = g.cm, []
        cats = list(dict.fromkeys(e.cat for e in cm.table))
        for c in cats:
            lines.append(f"{words.CATEGORY_ICON.get(c, '')} " + ", ".join(_esc(e.word) for e in cm.table if e.cat == c))
        return "\n".join(lines)

    # ================================================================ drawing turns
    async def _cm_turn(self, g: Game) -> None:
        cm = g.cm
        while cm.current not in g.players:                  # somebody left
            cm.pos += 1
            if cm.pos >= len(cm.order):
                return await self._cm_laps_done(g)
        cm.stage, cm.draft = "draw", None
        g.go(Phase.STEP, g.draw_seconds, self.io.now())
        self._timer(g, "cm", g.draw_seconds + config.BROKEN_GRACE_SECONDS, self._cm_draw_timeout)
        await self.io.send(g.chat_id, T(g.lang, "cm_turn", name=_esc(g.name(cm.current)), lap=cm.lap,
                                        n=cm.pos + 1, total=len(cm.order), secs=g.draw_seconds),
                           [(T(g.lang, "btn_open"), self.link(g.chat_id))])
        await self._tnotify(g)

    async def _cm_draw_timeout(self, g: Game) -> None:
        cm = g.cm
        if cm and cm.stage == "draw":
            await self._cm_hand_in(g, cm.draft or gifmaker.BLANK_JPEG)

    def cm_draft(self, g: Game, uid: int, data: bytes) -> None:
        cm = self._cm_drawer(g, uid)
        now = self.io.now()
        if now - cm.last_draft < config.SNAPSHOT_MIN_INTERVAL:
            raise GameError("too_fast")
        cm.last_draft, cm.draft = now, self._cm_jpeg(data)

    async def cm_submit(self, g: Game, uid: int, data: bytes) -> None:
        self._cm_drawer(g, uid)
        await self._cm_hand_in(g, self._cm_jpeg(data))

    @staticmethod
    def _cm_jpeg(data: bytes) -> bytes:
        if len(data) > config.BROKEN_JPEG_MAX or data[:3] != b"\xff\xd8\xff":
            raise GameError("bad_image")
        return data

    @staticmethod
    def _cm_drawer(g: Game, uid: int) -> CarmeleonState:
        cm = g.cm
        if not cm or g.phase != Phase.STEP or cm.stage != "draw":
            raise GameError("wrong_phase")
        if cm.current != uid or uid not in g.players:
            raise GameError("not_player")
        return cm

    async def _cm_hand_in(self, g: Game, jpeg: bytes) -> None:
        cm = g.cm
        uid = cm.current
        cm.drawings.append({"uid": uid, "lap": cm.lap, "jpeg": jpeg})
        cm.stage = "wait"                                   # nothing else is accepted until the next turn
        g.go(Phase.BREAK)
        await self.io.send_photo(g.chat_id, jpeg, T(g.lang, "cm_drawn", name=_esc(g.name(uid)), lap=cm.lap))
        cm.pos += 1
        if cm.pos < len(cm.order):
            return await self._cm_turn(g)
        await self._cm_laps_done(g)

    async def _cm_laps_done(self, g: Game) -> None:
        cm = g.cm
        if cm.lap >= 2:
            return await self._cm_open_vote(g)
        cm.stage = "decide"
        cm.more = {}
        g.go(Phase.STEP, config.CARMELEON_DECIDE_SECONDS, self.io.now())
        self._timer(g, "cm", config.CARMELEON_DECIDE_SECONDS, self._cm_decide_timeout)
        await self.io.send(g.chat_id, T(g.lang, "cm_decide", secs=config.CARMELEON_DECIDE_SECONDS),
                           [[(T(g.lang, "cm_btn_more"), "cb:cm:more"), (T(g.lang, "cm_btn_vote"), "cb:cm:vote")]])

    async def _cm_decide_timeout(self, g: Game) -> None:
        if g.cm and g.cm.stage == "decide":
            await self._cm_decide(g)

    async def _cm_decide(self, g: Game) -> None:
        cm = g.cm
        more = sum(1 for u, v in cm.more.items() if v and u in g.players)
        if more * 2 > len(g.players):                       # a majority wants another lap
            cm.lap, cm.pos = 2, 0
            await self._say(g.chat_id, g.lang, "cm_lap2")
            return await self._cm_turn(g)
        await self._cm_open_vote(g)

    # ================================================================ vote
    def _cm_picture(self, g: Game, uid: int) -> bytes:
        mine = [d["jpeg"] for d in g.cm.drawings if d["uid"] == uid]
        if not mine:
            return gifmaker.BLANK_JPEG
        return _side_by_side(mine[0], mine[-1]) if len(mine) > 1 else mine[0]

    async def _cm_open_vote(self, g: Game) -> None:
        cm = g.cm
        cm.stage, cm.votes = "vote", {}
        g.go(Phase.STEP, config.CARMELEON_VOTE_SECONDS, self.io.now())
        self._timer(g, "cm", config.CARMELEON_VOTE_SECONDS, self._cm_vote_timeout)
        await self.io.send(g.chat_id, T(g.lang, "cm_vote", secs=config.CARMELEON_VOTE_SECONDS,
                                        table=self._cm_table_text(g)))
        for uid in cm.order:
            if uid in g.players:
                cm.vote_msgs[uid] = await self.io.send_photo(
                    g.chat_id, self._cm_picture(g, uid), f"🖌 {_esc(g.name(uid))}",
                    [(T(g.lang, "cm_btn_suspect", name=g.name(uid)), f"cb:cm:v:{uid}")])

    async def _cm_vote_timeout(self, g: Game) -> None:
        if g.cm and g.cm.stage == "vote":
            await self._cm_tally(g)

    async def _cm_tally(self, g: Game) -> None:
        cm = g.cm
        cm.stage = "wait"
        g.go(Phase.BREAK)
        counts: dict[int, int] = {}
        for voter, target in cm.votes.items():
            if voter in g.players and target in g.players:
                counts[target] = counts.get(target, 0) + 1
        top = max(counts.values(), default=0)
        leaders = [u for u, n in counts.items() if n == top]
        caught = top > 0 and leaders == [cm.chameleon]
        lines = [f"🗳 {_esc(g.name(u))} — {n}" for u, n in sorted(counts.items(), key=lambda x: -x[1])] \
            or [T(g.lang, "cm_no_votes")]
        text = "\n".join(lines)
        if not caught:
            reason = T(g.lang, "cm_tie") if len(leaders) > 1 or not counts else T(g.lang, "cm_wrong_suspect",
                                                                                  name=_esc(g.name(leaders[0])))
            g.scores[cm.chameleon] += config.CARMELEON_POINTS["hidden"]
            return await self._cm_finish(g, f"{text}\n\n{reason}\n" + T(
                g.lang, "cm_chameleon_wins", name=_esc(g.name(cm.chameleon))), [cm.chameleon])
        cm.stage = "guess"
        g.go(Phase.STEP, config.CARMELEON_GUESS_SECONDS, self.io.now())
        self._timer(g, "cm", config.CARMELEON_GUESS_SECONDS, self._cm_guess_timeout)
        rows = [[(e.word, f"cb:cm:g:{i}") for i, e in list(enumerate(cm.table))[k:k + 3]]
                for k in range(0, len(cm.table), 3)]
        await self.io.send(g.chat_id, T(g.lang, "cm_caught", votes=text, name=_esc(g.name(cm.chameleon)),
                                        secs=config.CARMELEON_GUESS_SECONDS), rows)

    async def _cm_guess_timeout(self, g: Game) -> None:
        if g.cm and g.cm.stage == "guess":
            await self._cm_guess_result(g, None)

    async def _cm_guess_result(self, g: Game, pick: int | None) -> None:
        cm = g.cm
        cm.stage = "wait"
        g.go(Phase.BREAK)
        key = _esc(cm.table[cm.key].word)
        if pick == cm.key:
            g.scores[cm.chameleon] += config.CARMELEON_POINTS["guessed"]
            return await self._cm_finish(g, T(g.lang, "cm_guessed", name=_esc(g.name(cm.chameleon)), word=key),
                                         [cm.chameleon])
        winners = [u for u in cm.order if u in g.players and u != cm.chameleon]
        for u in winners:
            g.scores[u] += config.CARMELEON_POINTS["caught"]
        wrong = T(g.lang, "cm_missed", name=_esc(g.name(cm.chameleon)), word=key)
        await self._cm_finish(g, wrong, winners)

    async def _cm_finish(self, g: Game, header: str, winners: list[int]) -> None:
        cm = g.cm
        key = _esc(cm.table[cm.key].word)
        rows = ranking(g.scores, g.players)
        lines = [f"{'🏆' if u in winners else '▫️'} {_esc(n)} — {p}" for _, u, n, p in rows]
        text = f"{header}\n\n" + T(g.lang, "cm_reveal", word=key, name=_esc(g.name(cm.chameleon))) \
            + "\n\n" + T(g.lang, "game_over") + "\n" + "\n".join(lines)
        if not g.test:
            duration = int(self.io.now() - (g.started_at or self.io.now()))
            self.db.save_game(g.chat_id, g.lang, len(cm.drawings), duration,
                              [(r, u, n, p, int(u in winners), 0, sum(1 for d in cm.drawings if d["uid"] == u))
                               for r, u, n, p in rows])
        self._close(g)
        await self.io.send(g.chat_id, text)

    # ================================================================ buttons in the chat
    async def cm_callback(self, g: Game, uid: int, data: str) -> str | None:
        """cm:more | cm:vote | cm:v:<uid> | cm:g:<index>. Returns the text to show the player, if any."""
        cm = g.cm
        if not cm or uid not in g.players:
            return T(g.lang, "only_players")
        parts = data.split(":")[1:]
        if parts[0] in ("more", "vote") and cm.stage == "decide":
            cm.more[uid] = parts[0] == "more"
            if len(cm.more) >= len(g.players):
                await self._cm_decide(g)
            return T(g.lang, "cm_noted")
        if parts[0] == "v" and cm.stage == "vote" and len(parts) == 2 and parts[1].lstrip("-").isdigit():
            target = int(parts[1])
            if target == uid:
                return T(g.lang, "cm_self_vote")
            if target not in g.players:
                return None
            cm.votes[uid] = target
            note = T(g.lang, "cm_voted", name=g.name(target))
            if len([u for u in cm.votes if u in g.players]) >= len(g.players):
                await self._cm_tally(g)
            return note
        if parts[0] == "g" and cm.stage == "guess" and len(parts) == 2 and parts[1].isdigit():
            if uid != cm.chameleon:
                return T(g.lang, "cm_only_chameleon")
            i = int(parts[1])
            if i < len(cm.table):
                await self._cm_guess_result(g, i)
            return None
        return None

    # ================================================================ players leaving, Mini App state
    async def cm_left(self, g: Game, uid: int) -> None:
        cm = g.cm
        if len(g.players) < config.MIN_PLAYERS_CARMELEON - 1 or uid == cm.chameleon:
            winners = [u for u in cm.order if u in g.players and u != cm.chameleon]
            cm.stage = "wait"
            g.go(Phase.BREAK)
            if uid == cm.chameleon:
                for u in winners:
                    g.scores[u] += config.CARMELEON_POINTS["caught"]
                return await self._cm_finish(g, T(g.lang, "cm_chameleon_left", name=_esc(g.name(uid))), winners)
            self._close(g)
            return await self._say(g.chat_id, g.lang, "cm_aborted")
        if cm.stage == "draw" and cm.current == uid:
            await self._cm_hand_in(g, cm.draft or gifmaker.BLANK_JPEG)
        elif cm.stage == "decide" and len(cm.more) >= len(g.players):
            await self._cm_decide(g)
        elif cm.stage == "vote" and len([u for u in cm.votes if u in g.players]) >= len(g.players):
            await self._cm_tally(g)

    def _cm_web_state(self, g: Game, uid: int, out: dict) -> dict:
        cm = g.cm
        if not cm:
            return out
        me_in = uid in g.players
        chameleon = me_in and uid == cm.chameleon
        out["cm"] = {"stage": cm.stage, "lap": cm.lap, "me": "chameleon" if chameleon else ("knows" if me_in else "viewer"),
                     "table": [{"w": e.word, "cat": e.cat} for e in cm.table],
                     "key": cm.key if me_in and not chameleon else None,
                     "current": g.name(cm.current) if cm.pos < len(cm.order) else "",
                     "me_turn": cm.stage == "draw" and cm.current == uid}
        out.update(turn=len(cm.drawings) + 1, turns=len(cm.order) * cm.lap)
        if cm.stage == "draw" and cm.current == uid and me_in:
            prompt = T(g.lang, "cm_prompt_chameleon") if chameleon else T(g.lang, "cm_prompt_key",
                                                                         word=cm.table[cm.key].word)
            out["bk"] = {"kind": "draw", "active": True, "done": False, "prompt": prompt, "raw": True}
        return out
