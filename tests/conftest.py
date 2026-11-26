"""Shared fixtures: a fake Telegram/clock and an Engine wired to it."""
import asyncio
import random

import pytest

import config
from db import Database
from engine import Engine, GameError


class FakeIO:
    """Records what the bot would do and runs timers on a manual clock."""

    def __init__(self) -> None:
        self.t = 1_000.0
        self.sent: list[dict] = []
        self.photos: list[dict] = []
        self.edits: list[dict] = []
        self.deleted: list[int] = []
        self.admins: set[int] = set()
        self.members: set[int] = set()
        self.documents: list[dict] = []
        self.timers: dict[str, tuple[float, object]] = {}
        self._next_id = 100
        self.dms: list[dict] = []
        self.dm_photos: list[dict] = []
        self.animations: list[dict] = []
        self.text_edits: list[dict] = []
        self.dm_fail: set[int] = set()
        self.bot_can_delete = True

    def now(self) -> float:
        return self.t

    def _id(self) -> int:
        self._next_id += 1
        return self._next_id

    async def send(self, chat_id, text, buttons=None, reply_to=None):
        mid = self._id()
        self.sent.append({"id": mid, "chat": chat_id, "text": text, "buttons": buttons,
                          "reply_to": reply_to})
        return mid

    async def can_delete(self, chat_id):
        return self.bot_can_delete

    async def send_dm(self, user_id, text, buttons=None):
        if user_id in self.dm_fail:
            return False
        self.dms.append({"user": user_id, "text": text, "buttons": buttons})
        return True

    async def send_photo_dm(self, user_id, jpeg, caption):
        if user_id in self.dm_fail:
            return False
        self.dm_photos.append({"user": user_id, "jpeg": jpeg, "caption": caption})
        return True

    async def send_animation(self, chat_id, data, caption):
        mid = self._id()
        self.animations.append({"id": mid, "chat": chat_id, "data": data, "caption": caption})
        return mid

    async def edit_text(self, chat_id, message_id, text, buttons=None):
        self.text_edits.append({"id": message_id, "text": text, "buttons": buttons})

    async def send_photo(self, chat_id, jpeg, caption):
        mid = self._id()
        self.photos.append({"id": mid, "chat": chat_id, "jpeg": jpeg, "caption": caption})
        return mid

    async def edit_photo(self, chat_id, message_id, jpeg, caption):
        self.edits.append({"id": message_id, "jpeg": jpeg, "caption": caption})

    async def delete(self, chat_id, message_id):
        self.deleted.append(message_id)

    async def is_admin(self, chat_id, user_id):
        return user_id in self.admins

    async def is_member(self, chat_id, user_id):
        return user_id in self.admins or user_id in self.members

    async def send_document_dm(self, user_id, data, filename, caption):
        if user_id in self.dm_fail:
            return False
        self.documents.append({"user": user_id, "data": data, "filename": filename, "caption": caption})
        return True

    def schedule(self, name, delay, fn):
        self.timers[name] = (self.t + delay, fn)

    def cancel(self, prefix):
        for name in [n for n in self.timers if n.startswith(prefix)]:
            del self.timers[name]

    async def advance(self, seconds: float) -> None:
        target = self.t + seconds
        while True:
            due = [(d, n) for n, (d, _) in self.timers.items() if d <= target]
            if not due:
                break
            d, name = min(due)
            _, fn = self.timers.pop(name)
            self.t = max(self.t, d)
            await fn()
        self.t = target

    def texts(self) -> list[str]:
        return [m["text"] for m in self.sent]


class Env:
    CHAT = -1001

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.io = FakeIO()
        self.db = Database(":memory:")
        self.engine = Engine(self.io, self.db, random.Random(7))

    def run(self, coro):
        return self.loop.run_until_complete(coro)

    @property
    def game(self):
        return self.engine.games.get(self.CHAT)

    def start_match(self, n: int = 3, lang: str = "it", mode: str = "classic"):
        """Open a match with n players (ids 1..n) and start it."""
        e = self.engine
        self.run(e.new_game(self.CHAT, 1, "Ada", lang, mode))
        for uid in range(2, n + 1):
            self.run(e.join(self.CHAT, uid, f"P{uid}", lang))
        self.run(e.ready(self.CHAT, 1, lang))
        return self.game

    def to_choosing(self):
        self.run(self.io.advance(config.BREAK_SECONDS))
        return self.game.turn

    def to_drawing(self, pick: int = 0):
        t = self.to_choosing()
        self.engine.choose(self.CHAT, t.drawer, pick)
        self.run(self.engine.start_drawing(self.CHAT, t.drawer))
        return self.game.turn

    def chat(self, uid: int, text: str, mid: int = 5000):
        """A message written in the group chat."""
        self.run(self.engine.on_message(self.CHAT, uid, text, mid))

    def guess(self, uid: int, text: str, mid: int = 5000):
        """A guess: typed in the Mini App in classic mode, in the chat otherwise.
        Returns the Mini App result, or the error code."""
        g = self.game
        if g is not None and g.mode == "classic":
            try:
                return self.run(self.engine.web_guess(self.CHAT, uid, text))
            except GameError as e:
                return e.code
        self.chat(uid, text, mid)


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setattr(config, "GUESS_MIN_INTERVAL", 0.0)    # tests guess several times at the same instant
    e = Env()
    yield e
    e.loop.close()
