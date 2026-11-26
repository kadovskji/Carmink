"""Global bot administration: /admin (private chat only, ADMIN_ID users only).

Buttons: Update (announcement to all groups), Restart, Pull (git pull + pip), Log.
The command is intentionally absent from /start and from the command menu.
Messages are in Italian: the panel is for the bot owner only.
"""
import asyncio
import html
import io
import json
import logging
import os
import random
import sys

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import Forbidden, TelegramError
from telegram.ext import ContextTypes

import config
import logs
from db import Database
from engine import Engine, GameError
from game import Phase

LOG = logging.getLogger("carmink.admin")


class Admin:
    def __init__(self, db: Database, engine: Engine) -> None:
        self.db, self.engine = db, engine
        # user_id -> {"step": "en" | "it" | "confirm", "en": str, "it": str}
        self.pending: dict[int, dict] = {}

    @staticmethod
    def is_bot_admin(uid: int) -> bool:
        return uid in config.ADMIN_IDS

    def _menu(self) -> tuple[str, InlineKeyboardMarkup]:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Update", callback_data="ad:update"),
             InlineKeyboardButton("🔁 Restart", callback_data="ad:restart")],
            [InlineKeyboardButton("⬇️ Pull", callback_data="ad:pull"),
             InlineKeyboardButton("📜 Log", callback_data="ad:log")],
            [InlineKeyboardButton("🧪 Partita di test", callback_data="ad:test")],
        ])
        return f"🛠 Pannello admin\nPartite attive: {len(self.engine.games)}", kb

    @staticmethod
    def _back() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu", callback_data="ad:menu")]])

    async def admin(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        chat, user = update.effective_chat, update.effective_user
        if chat.type != "private" or not self.is_bot_admin(user.id):
            return                                  # silent: the command doesn't "exist"
        self.pending.pop(user.id, None)
        text, kb = self._menu()
        await update.message.reply_text(text, reply_markup=kb)

    # ---------------------------------------------------------------- test match: control panel
    SHAPES = ("triangolo", "cerchio", "quadrato", "stella", "rombo", "cuore", "croce")
    COLORS = ("giallo", "rosso", "arancione", "blu", "verde", "viola", "rosa")

    def _phrase(self) -> str:
        """A short made-up phrase for Broken Canva: three shapes or three colours."""
        return ", ".join(random.sample(random.choice((self.SHAPES, self.COLORS)), 3))

    @staticmethod
    def _quick_drawing() -> bytes:
        """A small random drawing (coloured shapes) for Broken Canva tests."""
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (400, 300), "white")
        d = ImageDraw.Draw(img)
        for _ in range(random.randint(2, 4)):
            x, y = random.randint(20, 280), random.randint(20, 200)
            w, h = random.randint(40, 110), random.randint(40, 90)
            col = tuple(random.randint(0, 255) for _ in range(3))
            random.choice((d.ellipse, d.rectangle))((x, y, x + w, y + h), fill=col, outline="black", width=3)
        out = io.BytesIO()
        img.save(out, "JPEG", quality=80)
        return out.getvalue()

    def _test_panel(self, uid: int) -> tuple[str, InlineKeyboardMarkup]:
        """Buttons to play the fake players of the running test match."""
        g = self.engine.games.get(uid)
        refresh = InlineKeyboardButton("🔄 Aggiorna", callback_data="ad:tc")
        end = InlineKeyboardButton("⏹ Termina test", callback_data="ad:testend")
        if not g or not g.test:
            return "🧪 Nessuna partita di test attiva.", InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Menu", callback_data="ad:menu")]])
        rows: list[list[InlineKeyboardButton]] = []
        name = lambda n: g.test_ids and f"Test {n}"        # noqa: E731
        text = f"🧪 Test {g.mode} · fase: {g.phase.name.lower()}"
        if g.mode == "broken":
            bk = g.broken
            if g.phase in (Phase.WRITING, Phase.STEP) and bk:
                todo = [n for n, u in enumerate(g.test_ids, 1)
                        if u in bk.order and u in g.players and u not in bk.inbox]
                if g.phase == Phase.WRITING or bk.kind == "text":
                    label, act = "🎲", "p"
                    text += "\nScrivere una frase" if g.phase == Phase.WRITING else "\nDescrivere il disegno"
                else:
                    label, act = "🖼", "d"
                    text += "\nDisegnare (oppure dalla Mini App)"
                if todo:
                    rows.append([InlineKeyboardButton(f"{label} Tutti ({len(todo)})",
                                                      callback_data=f"ad:tx:{act}all:0")])
                    rows += [[InlineKeyboardButton(f"{label} {name(n)}", callback_data=f"ad:tx:{act}:{n}")]
                             for n in todo]
                else:
                    text += "\n(tutti hanno consegnato)"
        elif g.turn and g.phase in (Phase.CHOOSING, Phase.STARTING, Phase.DRAWING):
            t = g.turn
            dn = g.test_ids.index(t.drawer) + 1 if t.drawer in g.test_ids else 0
            text += f" · disegna Test {dn}"
            if g.phase == Phase.CHOOSING:
                rows.append([InlineKeyboardButton("🎯 Test %d sceglie la prima parola" % dn,
                                                  callback_data="ad:tx:c:0")])
            elif g.phase == Phase.STARTING:
                rows.append([InlineKeyboardButton("▶️ Test %d inizia a disegnare" % dn,
                                                  callback_data="ad:tx:s:0")])
            else:
                for n, u in enumerate(g.test_ids, 1):
                    if u == t.drawer or u in t.guessed or u not in g.players:
                        continue
                    rows.append([InlineKeyboardButton(f"❌ Test {n} sbaglia", callback_data=f"ad:tx:w:{n}"),
                                 InlineKeyboardButton(f"✅ Test {n} indovina", callback_data=f"ad:tx:r:{n}")])
        else:
            text += "\nNessuna azione disponibile ora: premi Aggiorna."
        rows.append([refresh, end])
        return text, InlineKeyboardMarkup(rows)

    async def _test_action(self, uid: int, act: str, n: int) -> str:
        """Run a panel button; returns a short note for the toast."""
        g = self.engine.games.get(uid)
        if not g or not g.test:
            return "Nessun test attivo."
        try:
            if act == "c" and g.turn:
                self.engine.choose(uid, g.turn.drawer, 0)
            elif act == "s" and g.turn:
                await self.engine.start_drawing(uid, g.turn.drawer)
            elif act in ("w", "r") and g.turn:
                word = g.turn.word.word if act == "r" else f"qzx{random.randint(100, 999)}"
                return await self.engine.act_as(uid, n, word) or "ok"
            elif act == "p":
                return await self.engine.act_as(uid, n, self._phrase()) or "ok"
            elif act == "pall" and g.broken:
                for k, u in enumerate(g.test_ids, 1):
                    if u in g.broken.order and u not in g.broken.inbox and self.engine.games.get(uid) is g:
                        await self.engine.act_as(uid, k, self._phrase())
            elif act in ("d", "dall") and g.broken and g.broken.kind == "draw":
                for k, u in enumerate(g.test_ids, 1):
                    if (act == "d" and k != n) or u not in g.broken.order or u in g.broken.inbox:
                        continue
                    if self.engine.games.get(uid) is g and g.phase == Phase.STEP:
                        await self.engine.bk_submit(uid, u, self._quick_drawing())
        except GameError as e:
            return f"Errore: {e.code}"
        return "ok"

    async def _show_panel(self, q, uid: int) -> None:
        text, kb = self._test_panel(uid)
        try:
            await q.edit_message_text(text, reply_markup=kb)
        except TelegramError:                           # "message is not modified"
            pass

    async def test_panel(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """/c: a fresh control panel at the bottom of the chat."""
        chat, user = update.effective_chat, update.effective_user
        if chat.type != "private" or not self.is_bot_admin(user.id):
            return
        text, kb = self._test_panel(user.id)
        await update.message.reply_text(text, reply_markup=kb)

    async def test_say(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """/t <n> <text>: write as fake player n in the running test match."""
        chat, user = update.effective_chat, update.effective_user
        if chat.type != "private" or not self.is_bot_admin(user.id):
            return
        args = ctx.args or []
        if len(args) < 2 or not args[0].isdigit():
            await update.message.reply_text("Uso: /t <numero giocatore> <testo>")
            return
        note = await self.engine.act_as(user.id, int(args[0]), " ".join(args[1:]))
        if note:
            await update.message.reply_text(note)

    async def callback(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        q = update.callback_query
        uid = q.from_user.id
        if not self.is_bot_admin(uid):
            await q.answer()
            return
        action = q.data.split(":", 1)[1]
        await q.answer()

        if action == "menu":
            self.pending.pop(uid, None)
            text, kb = self._menu()
            await q.edit_message_text(text, reply_markup=kb)

        elif action == "update":
            self.pending[uid] = {"step": "en"}
            await q.edit_message_text(
                "📢 Invio un avviso a tutti i gruppi attivi.\n"
                "Scrivimi il testo in INGLESE (per i gruppi in inglese).", reply_markup=self._back())

        elif action == "send":
            data = self.pending.pop(uid, None)
            if not data or data.get("step") != "confirm":
                await q.edit_message_text("Nessun avviso in sospeso.", reply_markup=self._back())
                return
            await q.edit_message_text("Invio in corso…")
            sent, failed = await self._broadcast(ctx, data)
            LOG.info("announcement sent by %s: %d ok, %d failed", uid, sent, failed)
            await q.edit_message_text(f"✅ Avviso inviato a {sent} gruppi ({failed} errori).",
                                      reply_markup=self._back())

        elif action == "restart":
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Riavvia ora", callback_data="ad:restart_yes"),
                InlineKeyboardButton("⬅️ Annulla", callback_data="ad:menu")]])
            await q.edit_message_text(
                f"🔁 Riavviare il bot?\nPartite attive che andranno perse: {len(self.engine.games)}",
                reply_markup=kb)

        elif action == "restart_yes":
            await q.edit_message_text("🔁 Riavvio in corso…")
            await self.restart(update, ctx)

        elif action == "pull":
            await q.edit_message_text("⬇️ Eseguo git pull e aggiorno le dipendenze…")
            out = await self.pull()
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Riavvia", callback_data="ad:restart")],
                [InlineKeyboardButton("⬅️ Menu", callback_data="ad:menu")]])
            await q.edit_message_text(f"⬇️ Pull completato:\n\n{out}"[:4000], reply_markup=kb)

        elif action == "test":
            g = self.engine.games.get(uid)
            if g and g.test:
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⏹ Termina il test", callback_data="ad:testend")],
                    [InlineKeyboardButton("⬅️ Menu", callback_data="ad:menu")]])
                await q.edit_message_text(
                    f"🧪 Test in corso ({g.mode}, {len(g.test_ids)} giocatori finti).\n"
                    "Pulsanti: /c · testo: /t N testo · Mini App: barra gialla.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🎛 Pannello", callback_data="ad:tc")]] + list(kb.inline_keyboard)))
            else:
                rows = [[InlineKeyboardButton(f"{emoji} {name}", callback_data=f"ad:testmode:{mode}")]
                        for mode, emoji, name in (("speedrun", "⚡", "Speedrun"),
                                                  ("classic", "🎨", "Classica"),
                                                  ("broken", "📞", "Broken Canva"))]
                rows.append([InlineKeyboardButton("⬅️ Menu", callback_data="ad:menu")])
                await q.edit_message_text(
                    "🧪 Partita di test: tu interpreti tutti i giocatori.\nScegli la modalità.",
                    reply_markup=InlineKeyboardMarkup(rows))

        elif action.startswith("testmode:"):
            mode = action.split(":", 1)[1]
            if mode not in config.MODES_AVAILABLE:
                return
            lo = config.MIN_PLAYERS_BROKEN if mode == "broken" else config.MIN_PLAYERS
            row = [InlineKeyboardButton(str(n), callback_data=f"ad:testgo:{mode}:{n}")
                   for n in range(lo, 9)]
            await q.edit_message_text(
                "Quanti giocatori finti?",
                reply_markup=InlineKeyboardMarkup([row, [InlineKeyboardButton("⬅️ Indietro", callback_data="ad:test")]]))

        elif action.startswith("testgo:"):
            _, mode, n = action.split(":")
            if mode not in config.MODES_AVAILABLE or not n.isdigit():
                return
            if uid in self.engine.games:
                await q.edit_message_text("C'è già una partita di test in corso.",
                                          reply_markup=self._back())
                return
            await q.edit_message_text(
                "🧪 Partita di test avviata.\n/c = pannello con i pulsanti (indovina, frase, disegno…)\n"
                "/t N testo = scrive come Test N\nMini App: scegli il giocatore dalla barra gialla.",
                reply_markup=self._back())
            await self.engine.new_test_game(uid, "it", mode, int(n))
            text, kb = self._test_panel(uid)
            await ctx.bot.send_message(uid, text, reply_markup=kb)

        elif action == "tc":
            await self._show_panel(q, uid)

        elif action.startswith("tx:"):
            _, act, n = action.split(":")
            note = await self._test_action(uid, act, int(n) if n.isdigit() else 0)
            if note != "ok":
                await q.answer(note[:180])
            await self._show_panel(q, uid)

        elif action == "testend":
            await self.engine.end_test(uid)
            await q.edit_message_text("⏹ Test terminato.", reply_markup=self._back())

        elif action == "log":
            lines = logs.recent(minutes=60, limit=50)
            body = ("\n".join(lines) if lines else "(nessun evento nell'ultima ora)")[-3500:]
            await q.edit_message_text(
                f"📜 Log dell'ultima ora (max 50 righe):\n<pre>{html.escape(body)}</pre>",
                parse_mode="HTML", reply_markup=self._back())

    async def handle_text(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Private text from the admin while composing an announcement."""
        uid = update.effective_user.id
        data = self.pending.get(uid)
        if not data or not self.is_bot_admin(uid):
            return
        text = update.message.text.strip()
        if data["step"] == "en":
            data["en"], data["step"] = text, "it"
            await update.message.reply_text("Ora il testo in ITALIANO.")
        elif data["step"] == "it":
            data["it"], data["step"] = text, "confirm"
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("📤 Invia", callback_data="ad:send"),
                InlineKeyboardButton("⬅️ Annulla", callback_data="ad:menu")]])
            await update.message.reply_text(
                f"Anteprima\n\n🇬🇧 {data['en']}\n\n🇮🇹 {data['it']}\n\n"
                f"Gruppi in inglese: {len(self.db.chats_by_lang('en'))} · "
                f"in italiano: {len(self.db.chats_by_lang('it'))}", reply_markup=kb)

    async def _broadcast(self, ctx, data: dict) -> tuple[int, int]:
        sent = failed = 0
        for lang in ("en", "it"):
            for chat_id in self.db.chats_by_lang(lang):
                try:
                    await ctx.bot.send_message(chat_id, data[lang])
                    sent += 1
                except Forbidden:
                    self.db.set_chat_active(chat_id, False)     # the bot was removed
                    failed += 1
                except TelegramError:
                    failed += 1
                await asyncio.sleep(0.05)                       # stay well under Telegram's limits
        return sent, failed

    @staticmethod
    async def pull() -> str:
        """git pull --ff-only, then pip install -r requirements.txt."""
        out = []
        for cmd in (["git", "pull", "--ff-only"],
                    [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]):
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                    cwd=str(config.BASE_DIR))
                raw, _ = await asyncio.wait_for(proc.communicate(), timeout=180)
                tail = "\n".join(raw.decode("utf-8", "replace").strip().splitlines()[-8:])
                out.append(f"$ {' '.join(cmd[:3])}\n{tail}\n(codice {proc.returncode})")
            except (OSError, asyncio.TimeoutError) as e:
                out.append(f"$ {' '.join(cmd[:3])}\nerrore: {e}")
        return "\n\n".join(out)

    async def restart(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Replace the process with a fresh one (running matches are lost).

        The update that triggered the restart is acknowledged first, so Telegram doesn't
        deliver it again to the new process (which would restart it forever).
        """
        LOG.info("restart requested by %s", update.effective_user.id)
        msg = update.callback_query.message if update.callback_query else None
        if msg:
            try:
                with open(config.RESTART_FILE, "w", encoding="utf-8") as f:
                    json.dump({"chat_id": msg.chat_id, "message_id": msg.message_id}, f)
            except OSError as e:
                LOG.warning("could not save the restart marker: %s", e)
        try:
            await ctx.bot.get_updates(offset=update.update_id + 1, limit=1, timeout=0)
        except TelegramError as e:
            LOG.warning("could not acknowledge the update before restarting: %s", e)
        logging.shutdown()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    async def notify_restart(self, bot) -> None:
        """After a restart requested from /admin: turn the panel message into a confirmation."""
        try:
            with open(config.RESTART_FILE, encoding="utf-8") as f:
                info = json.load(f)
            os.remove(config.RESTART_FILE)
        except (OSError, ValueError):
            return
        text, kb = self._menu()
        try:
            await bot.edit_message_text("✅ Bot riavviato.\n\n" + text, chat_id=info["chat_id"],
                                        message_id=info["message_id"], reply_markup=kb)
        except (TelegramError, KeyError) as e:
            LOG.warning("could not confirm the restart: %s", e)
