"""Broken Canva: a telephone game of phrases and drawings. Nobody wins.

Everybody privately sends the bot a phrase; then, pass after pass, each player receives the last
item of somebody else's chain and answers it: a drawing (Mini App) after a phrase, a phrase (private
message) after a drawing. Every chain ends with a drawing; the bot then posts one GIF per chain.
Mixed into `Engine`, which provides io, db, games, user_game, rng and the timers.
"""
import asyncio
import html
import logging

import config
import gifmaker
from errors import GameError
from game import BrokenState, Game, Phase, broken_steps
from i18n import T, dur

LOG = logging.getLogger("carmink.broken")


def _esc(s: str) -> str:
    return html.escape(s, quote=False)


def clean_phrase(text: str) -> str:
    """One line, single spaces, no control characters."""
    return " ".join("".join(c for c in str(text) if c.isprintable() or c.isspace()).split())


def trim_chain(chain: list[dict]) -> list[dict]:
    """A chain always ends with a drawing: drop a trailing phrase (an interrupted game)."""
    items = list(chain)
    while items and items[-1]["kind"] == "text" and len(items) > 1:
        items.pop()
    return items


class BrokenMixin:
    # ================================================================ helpers
    def _bot_url(self, start: str = "") -> str:
        return f"https://t.me/{config.BOT_USERNAME}" + (f"?start={start}" if start else "")

    def _start_button(self, g: Game) -> list[tuple[str, str]]:
        return [(T(g.lang, "btn_start_bot"), self._bot_url(f"j{abs(g.chat_id)}"))]

    async def _need_dm(self, chat_id: int, lang: str) -> None:
        await self.io.send(chat_id, T(lang, "bk_need_dm"),
                           [(T(lang, "btn_start_bot"), self._bot_url(f"j{abs(chat_id)}"))])

    @staticmethod
    def _bk_active(g: Game) -> list[int]:
        return [u for u in g.broken.order if u in g.players]

    def _bk_fallback(self, g: Game, uid: int, kind: str) -> dict:
        """What a player who handed nothing in gets: their last draft or a blank canvas, or "…"."""
        bk = g.broken
        if kind == "draw":
            return {"kind": "draw", "author": uid, "name": g.name(uid),
                    "jpeg": bk.drafts.get(uid) or gifmaker.BLANK_JPEG}
        return {"kind": "text", "author": uid, "name": g.name(uid), "text": "…"}

    def _bk_status(self, g: Game) -> tuple[str, list[tuple[str, str]]]:
        bk = g.broken
        active = self._bk_active(g)
        done = sum(1 for u in active if u in bk.inbox)
        rows = " ".join(f"{'✅' if u in bk.inbox else '⏳'} {_esc(g.name(u))}" for u in active)
        if g.phase == Phase.WRITING:
            text = T(g.lang, "bk_status_write", n=done, total=len(active), rows=rows,
                     secs=config.BROKEN_PHRASE_SECONDS)
            return text, [(T(g.lang, "btn_open_bot"), self._bot_url())]
        key = "bk_status_draw" if bk.kind == "draw" else "bk_status_describe"
        text = T(g.lang, key, step=bk.step, steps=bk.steps, n=done, total=len(active), rows=rows)
        if bk.kind == "draw":
            return text, [(T(g.lang, "btn_open"), self.link(g.chat_id))]
        return text, [(T(g.lang, "btn_open_bot"), self._bot_url())]

    async def _bk_post_status(self, g: Game) -> None:
        text, buttons = self._bk_status(g)
        gen = g.gen
        mid = await self.io.send(g.chat_id, text, buttons)
        if self.games.get(g.chat_id) is g and g.gen == gen:
            g.broken.status_msg = mid
        # (if the pass closed in the meantime the message is simply left as it is)

    async def _dm(self, g: Game, uid: int, text: str, buttons=None, hint: bool = False) -> bool:
        """A private message to a player; in a test match it lands in the admin's chat instead."""
        if g.test:
            n = g.test_ids.index(uid) + 1 if uid in g.test_ids else 0
            tail = f"\n↪ /t {n} …" if hint else ""
            await self.io.send(g.chat_id, f"📩 {g.name(uid)}\n{text}{tail}", buttons)
            return True
        return await self.io.send_dm(uid, text, buttons)

    async def _dm_photo(self, g: Game, uid: int, jpeg: bytes, caption: str) -> bool:
        if g.test:
            n = g.test_ids.index(uid) + 1 if uid in g.test_ids else 0
            await self.io.send_photo(g.chat_id, jpeg, f"📩 {g.name(uid)}\n{caption}\n↪ /t {n} …")
            return True
        return await self.io.send_photo_dm(uid, jpeg, caption)

    async def _bk_update_status(self, g: Game) -> None:
        bk = g.broken
        if bk and bk.status_msg:
            text, buttons = self._bk_status(g)
            await self.io.edit_text(g.chat_id, bk.status_msg, text, buttons)

    # ================================================================ start
    async def _bk_begin(self, g: Game) -> None:
        g.go(Phase.BREAK)                       # kills the lobby timer; texts are ignored for now
        order = list(g.players)
        self.rng.shuffle(order)
        g.started_at = self.io.now()
        results = await asyncio.gather(*(
            self._dm(g, u, T(g.lang, "bk_write_dm", max=config.BROKEN_TEXT_MAX,
                             time=f"{config.BROKEN_PHRASE_SECONDS // 60} min"),
                     hint=True) for u in order))
        failed = [u for u, ok in zip(order, results) if not ok]
        if failed:
            for u in failed:
                g.players.pop(u, None)
                self.user_game.pop(u, None)
            order = [u for u in order if u not in failed]
            await self._say(g.chat_id, g.lang, "bk_dm_failed",
                            names=", ".join(_esc(g.name(u)) for u in failed))
        if len(order) < config.MIN_PLAYERS_BROKEN:
            for u in order:
                await self._dm(g, u, T(g.lang, "bk_aborted"))
            self._close(g)
            return await self._say(g.chat_id, g.lang, "bk_aborted")
        g.broken = BrokenState(order=order, steps=broken_steps(len(order)))
        g.scores = {u: 0 for u in order}
        g.go(Phase.WRITING, config.BROKEN_PHRASE_SECONDS, self.io.now())
        self._timer(g, "bk", config.BROKEN_PHRASE_SECONDS, self._bk_timeout)
        LOG.info("broken game in %s starts: %d players, %d passes", g.chat_id, len(order),
                 g.broken.steps)
        await self._bk_post_status(g)

    # ================================================================ private messages
    async def on_private(self, uid: int, text: str) -> bool:
        """A private message: a phrase or a description if the player is expected to write one."""
        g = self.games.get(self.user_game.get(uid, 0))
        if not g or g.mode != "broken" or not g.broken or g.phase not in (Phase.WRITING, Phase.STEP):
            return False
        bk = g.broken
        if uid not in bk.order or uid not in g.players:
            return False
        if bk.kind != "text":
            await self._dm(g, uid, T(g.lang, "bk_use_app"))
            return True
        phrase = clean_phrase(text)
        if not phrase:
            return True
        if len(phrase) > config.BROKEN_TEXT_MAX:
            await self._dm(g, uid, T(g.lang, "bk_too_long", max=config.BROKEN_TEXT_MAX))
            return True
        again = uid in bk.inbox
        bk.inbox[uid] = {"kind": "text", "author": uid, "name": g.name(uid), "text": phrase}
        await self._dm(g, uid, T(g.lang, "bk_replaced" if again else "bk_saved"))
        await self._bk_update_status(g)
        await self._bk_check_done(g)
        return True

    # ================================================================ drawings (Mini App)
    def _bk_draw_ctx(self, chat_id: int, uid: int) -> tuple[Game, BrokenState]:
        g = self.games.get(chat_id)
        if not g or g.mode != "broken" or not g.broken:
            raise GameError("no_game")
        bk = g.broken
        if g.phase != Phase.STEP or bk.kind != "draw":
            raise GameError("wrong_phase")
        if uid not in bk.order or uid not in g.players:
            raise GameError("not_player")
        return g, bk

    @staticmethod
    def _bk_jpeg(data: bytes) -> bytes:
        if len(data) > config.BROKEN_JPEG_MAX or data[:3] != b"\xff\xd8\xff":
            raise GameError("bad_image")
        return data

    def bk_draft(self, chat_id: int, uid: int, data: bytes) -> None:
        """The Mini App saves the drawing now and then: it's used if the time runs out."""
        g, bk = self._bk_draw_ctx(chat_id, uid)
        data = self._bk_jpeg(data)
        now = self.io.now()
        if now - bk.last_draft.get(uid, -1e9) < config.SNAPSHOT_MIN_INTERVAL:
            raise GameError("too_fast")
        bk.last_draft[uid] = now
        bk.drafts[uid] = data

    async def bk_submit(self, chat_id: int, uid: int, data: bytes) -> None:
        g, bk = self._bk_draw_ctx(chat_id, uid)
        data = self._bk_jpeg(data)
        if uid in bk.inbox:
            raise GameError("already_done")
        bk.inbox[uid] = {"kind": "draw", "author": uid, "name": g.name(uid), "jpeg": data}
        await self._bk_update_status(g)
        await self._bk_check_done(g)

    def _bk_web_state(self, g: Game, uid: int, out: dict) -> dict:
        bk = g.broken
        if not bk or g.phase not in (Phase.WRITING, Phase.STEP):
            return out
        mine = uid in bk.order and uid in g.players
        info = {"step": bk.step, "steps": bk.steps, "kind": bk.kind, "active": mine,
                "done": uid in bk.inbox}
        if mine and g.phase == Phase.STEP and bk.kind == "draw" and uid in bk.given:
            info["prompt"] = bk.given[uid].get("text", "")
        out.update(turn=bk.step, turns=bk.steps, bk=info)
        return out

    # ================================================================ passes
    async def _bk_check_done(self, g: Game) -> None:
        if g.phase in (Phase.WRITING, Phase.STEP) and g.broken:
            active = self._bk_active(g)
            if active and all(u in g.broken.inbox for u in active):
                await self._bk_close_step(g)

    async def _bk_timeout(self, g: Game) -> None:
        if g.phase in (Phase.WRITING, Phase.STEP):
            await self._bk_close_step(g)

    async def _bk_close_step(self, g: Game) -> None:
        bk = g.broken
        step, n = bk.step, len(bk.order)
        g.go(Phase.BREAK)                       # nothing more is accepted for this pass
        if step == 0:
            silent = [u for u in bk.order if u in g.players and u not in bk.inbox]
            keep = [u for u in bk.order if u in g.players and u in bk.inbox]
            if silent:                          # whoever sent no phrase is out
                for u in silent:
                    g.players.pop(u, None)
                    self.user_game.pop(u, None)
                await self._say(g.chat_id, g.lang, "bk_dropped",
                                names=", ".join(_esc(g.name(u)) for u in silent))
            if len(keep) < config.MIN_PLAYERS_BROKEN:
                for u in keep:
                    await self._dm(g, u, T(g.lang, "bk_aborted"))
                self._close(g)
                return await self._say(g.chat_id, g.lang, "bk_aborted")
            bk.order = keep
            bk.steps = broken_steps(len(keep))
            bk.chains = [[bk.inbox[u]] for u in keep]
        else:
            for p, u in enumerate(bk.order):
                item = bk.inbox.get(u) or self._bk_fallback(g, u, bk.kind)
                bk.chains[(p - step) % n].append(item)
        bk.step += 1
        if bk.step > bk.steps:
            return await self._finish(g, "")
        await self._bk_start_step(g)

    async def _bk_start_step(self, g: Game) -> None:
        bk = g.broken
        bk.inbox, bk.given, bk.drafts, bk.last_draft, bk.status_msg = {}, {}, {}, {}, None
        draw = bk.kind == "draw"
        secs = g.draw_seconds if draw else config.BROKEN_DESCRIBE_SECONDS
        g.go(Phase.STEP, secs, self.io.now())
        self._timer(g, "bk", secs + (config.BROKEN_GRACE_SECONDS if draw else 0), self._bk_timeout)
        n = len(bk.order)
        jobs = []
        for p, u in enumerate(bk.order):
            if u not in g.players:
                continue
            src = bk.chains[(p - bk.step) % n][-1]
            bk.given[u] = src
            jobs.append(self._bk_deliver(g, u, src, secs))
        await asyncio.gather(*jobs)
        await self._bk_post_status(g)
        await self._bk_check_done(g)

    async def _bk_deliver(self, g: Game, uid: int, src: dict, secs: int) -> None:
        """Send a player what to draw / describe; a player we can't reach hands in an empty answer."""
        bk, step = g.broken, g.broken.step
        if bk.kind == "draw":
            ok = await self._dm(g, 
                uid, T(g.lang, "bk_draw_dm", step=step, steps=bk.steps, secs=dur(g.lang, secs),
                       text=_esc(src.get("text") or "…")),
                [(T(g.lang, "btn_draw"), self.link(g.chat_id))])
        else:
            ok = await self._dm_photo(
                g, uid, src.get("jpeg") or gifmaker.BLANK_JPEG,
                T(g.lang, "bk_describe_dm", step=step, steps=bk.steps, secs=dur(g.lang, secs)))
            if not ok and g.broken is bk and bk.step == step:
                bk.inbox.setdefault(uid, self._bk_fallback(g, uid, "text"))

    # ================================================================ the end
    async def _bk_finish(self, g: Game, header: str) -> None:
        bk = g.broken
        chains = [trim_chain(c) for c in bk.chains] if bk else []
        chains = [c for c in chains if len(c) > 1]
        rows = [(1, u, n, 0, 0, 0, 0) for u, n in
                ((u, g.name(u)) for u in (bk.order if bk else g.players))]
        duration = int(self.io.now() - (g.started_at or self.io.now()))
        if rows and not g.test:
            self.db.save_game(g.chat_id, g.lang, bk.step if bk else 0, duration, rows)
        chat_id, lang = g.chat_id, g.lang
        LOG.info("broken game in %s over: %d chains", chat_id, len(chains))
        self._close(g)
        await self.io.send(chat_id, header + T(lang, "bk_over"))
        labels = {"start": T(lang, "bk_gif_start"), "draw": T(lang, "bk_gif_draw"),
                  "describe": T(lang, "bk_gif_describe")}
        for i, chain in enumerate(chains):
            if i:
                await asyncio.sleep(config.BROKEN_GIF_GAP)
            caption = T(lang, "bk_chain_caption", name=_esc(chain[0]["name"]))
            gif = None
            if gifmaker.available():
                try:
                    gif = await asyncio.to_thread(gifmaker.make_gif, chain, labels)
                except Exception:               # a broken picture must not lose the whole recap
                    LOG.exception("could not build the GIF of a chain")
            if gif:
                await self.io.send_animation(chat_id, gif, caption)
            else:
                await self.io.send(chat_id, caption + "\n" + self._bk_recap(lang, chain))

    @staticmethod
    def _bk_recap(lang: str, chain: list[dict]) -> str:
        lines = []
        for it in chain:
            if it["kind"] == "text":
                lines.append(f"✍️ <b>{_esc(it['name'])}</b>: {_esc(it['text'])}")
            else:
                lines.append(f"🎨 <b>{_esc(it['name'])}</b>: {T(lang, 'bk_drawing')}")
        return "\n".join(lines)
