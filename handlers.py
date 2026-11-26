"""Telegram command handlers: thin wrappers around the Engine, the dictionary and the stats."""
import html
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

import config
from db import ALLOWED_SETTINGS, Database
from engine import Engine, admin_button
from i18n import LANGUAGES, T

LOG = logging.getLogger("carmink.bot")
SETTING_KEYS = tuple(ALLOWED_SETTINGS)


class Handlers:
    def __init__(self, engine: Engine, db: Database) -> None:
        self.engine, self.db = engine, db
        self._seen: set[int] = set()

    # ------------------------------------------------------------ helpers
    async def _reply(self, update: Update, text: str, **kw) -> None:
        await update.effective_message.reply_text(text, parse_mode="HTML", **kw)

    async def _group(self, update: Update) -> bool:
        """True in groups; in private chats it explains that the command is for groups."""
        chat = update.effective_chat
        if chat.type == "private":
            await self._reply(update, T(self.db.get_lang(chat.id), "group_only"))
            return False
        self.db.track_chat(chat.id, chat.title)
        return True

    async def _is_admin(self, ctx: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
        return await self.engine.io.is_admin(chat_id, user_id)

    def _lang(self, chat_id: int) -> str:
        g = self.engine.games.get(chat_id)
        return g.lang if g else self.db.get_lang(chat_id)

    # ------------------------------------------------------------ lobby
    async def start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        chat = update.effective_chat
        lang = self.db.get_lang(chat.id)
        if chat.type == "private":
            user = update.effective_user
            self.db.add_dm(user.id)                 # from now on the bot may write to this user
            code = (user.language_code or "")[:2]
            lang = code if code in LANGUAGES else lang
            arg = ctx.args[0] if ctx.args else ""
            if arg[:1] == "j" and arg[1:].isdigit():   # "Start" button of a Broken Canva sign-up
                chat_id = -int(arg[1:])
                g = self.engine.games.get(chat_id)
                if g and g.mode == "broken" and g.phase.name == "LOBBY":
                    await self.engine.join(chat_id, user.id, user.first_name, g.lang)
                return await self._reply(update, T(g.lang if g else lang, "bk_start_ok"))
            await self._reply(update, T(lang, "start_private"))
        else:
            await self._reply(update, T(lang, "start_group"))

    async def help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        chat = update.effective_chat
        if chat.type != "private":
            self.db.track_chat(chat.id, chat.title)
        await self._reply(update, T(self._lang(chat.id), "help"))

    async def newgame(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._group(update):
            return
        chat, user = update.effective_chat, update.effective_user
        lang = self.db.get_lang(chat.id)
        if ctx.args and ctx.args[0].lower() in LANGUAGES:      # /newgame en: this match only
            lang = ctx.args[0].lower()
        if not await self.engine.can_open(chat.id, user.id, lang):
            return
        rows = [[InlineKeyboardButton(T(lang, f"mode_{m}"), callback_data=f"m:{m}:{lang}:{user.id}")]
                for m in config.MODES]
        await self._reply(update, T(lang, "mode_pick", name=html.escape(user.first_name)),
                          reply_markup=InlineKeyboardMarkup(rows))

    async def cb_mode(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """The creator picked a mode: open the match."""
        q = update.callback_query
        chat_id = q.message.chat_id
        try:
            _, mode, lang, owner = q.data.split(":")
            owner = int(owner)
        except ValueError:
            return await q.answer()
        lang = lang if lang in LANGUAGES else self.db.get_lang(chat_id)
        if q.from_user.id != owner:
            return await q.answer(T(lang, "mode_only_creator"), show_alert=True)
        if mode not in config.MODES:
            return await q.answer()
        if mode not in config.MODES_AVAILABLE:
            return await q.answer(T(lang, "mode_soon"), show_alert=True)
        await q.answer()
        try:
            await q.message.delete()
        except TelegramError:
            pass
        self.db.track_chat(chat_id, getattr(q.message.chat, "title", None))
        await self.engine.new_game(chat_id, owner, q.from_user.first_name, lang, mode)

    async def cb_party(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Buttons of Carmeleon and Code Stroke (votes, grid, pass)."""
        q = update.callback_query
        try:
            note = await self.engine.on_callback(q.message.chat_id, q.from_user.id, q.data or "",
                                                 q.from_user.first_name)
        except Exception:                           # a button must never leave the player waiting
            LOG.exception("party callback %s failed", q.data)
            note = None
        await q.answer(note or None)

    async def join(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._group(update):
            chat, user = update.effective_chat, update.effective_user
            await self.engine.join(chat.id, user.id, user.first_name, self._lang(chat.id))

    async def nextgame(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._group(update):
            chat, user = update.effective_chat, update.effective_user
            await self.engine.nextgame(chat.id, user.id, user.first_name, self._lang(chat.id))

    async def ready(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._group(update):
            chat, user = update.effective_chat, update.effective_user
            await self.engine.ready(chat.id, user.id, self._lang(chat.id))

    async def wait(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._group(update):
            chat, user = update.effective_chat, update.effective_user
            arg = ctx.args[0] if ctx.args else ""
            await self.engine.wait(chat.id, user.id, arg, self._lang(chat.id))

    async def stop(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._group(update):
            chat, user = update.effective_chat, update.effective_user
            await self.engine.stop(chat.id, user.id, self._lang(chat.id))

    async def quit(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._group(update):
            chat, user = update.effective_chat, update.effective_user
            await self.engine.quit(chat.id, user.id, self._lang(chat.id))

    async def on_private_text(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """A private message may be a Broken Canva phrase."""
        msg = update.effective_message
        if msg and msg.text and update.effective_user:
            self.db.add_dm(update.effective_user.id)
            await self.engine.on_private(update.effective_user.id, msg.text)

    async def on_text(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Every group message may be a guess."""
        msg = update.effective_message
        if msg and msg.text and update.effective_user:
            await self.engine.on_message(update.effective_chat.id, update.effective_user.id,
                                         msg.text, msg.message_id)

    # ------------------------------------------------------------ statistics
    async def stats(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._group(update):
            return
        chat = update.effective_chat
        lang = self.db.get_lang(chat.id)
        s = self.db.group_stats(chat.id)
        if not s["games"]:
            return await self._reply(update, T(lang, "stats_none"))

        def block(key: str, rows) -> str:
            lines = [f"{i}. {html.escape(n)} — {v}" for i, (n, v) in enumerate(rows, 1) if v]
            return T(lang, key) + "\n" + "\n".join(lines) if lines else ""
        parts = [T(lang, "stats_title", games=s["games"]), block("stats_wins", s["wins"]),
                 block("stats_points", s["points"]), block("stats_guessed", s["guessed"])]
        if s["best_game"] and s["best_game"][1]:
            parts.append(T(lang, "stats_best", name=html.escape(s["best_game"][0]),
                           pts=s["best_game"][1]))
        await self._reply(update, "\n\n".join(p for p in parts if p))

    async def mystats(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        chat, user = update.effective_chat, update.effective_user
        lang = self.db.get_lang(chat.id)
        row = self.db.user_stats(user.id, None if chat.type == "private" else chat.id)
        if not row:
            return await self._reply(update, T(lang, "mystats_none"))
        await self._reply(update, T(lang, "mystats", name=html.escape(user.first_name), **row))

    # ------------------------------------------------------------ settings (group admins)
    def _menu(self, chat_id: int) -> tuple[str, InlineKeyboardMarkup]:
        cfg = self.db.get_settings(chat_id)
        lang = cfg["lang"]
        rows = [[InlineKeyboardButton(
            f"{T(lang, 'set_' + k)}: {T(lang, f'set_{k}_{cfg[k]}')}", callback_data=f"s:{k}")]
            for k in SETTING_KEYS]
        rows.append([InlineKeyboardButton(T(lang, "btn_dict"), url=self.engine.dict_link(chat_id))])
        return T(lang, "settings_title"), InlineKeyboardMarkup(rows)

    def _submenu(self, chat_id: int, key: str) -> tuple[str, InlineKeyboardMarkup]:
        cfg = self.db.get_settings(chat_id)
        lang = cfg["lang"]
        rows = [[InlineKeyboardButton(("✅ " if v == cfg[key] else "") + T(lang, f"set_{key}_{v}"),
                                      callback_data=f"s:{key}:{v}")] for v in ALLOWED_SETTINGS[key]]
        rows.append([InlineKeyboardButton(T(lang, "btn_back"), callback_data="s:menu")])
        return f"{T(lang, 'set_' + key)}\n\n{T(lang, 'settings_sub_' + key)}", InlineKeyboardMarkup(rows)

    async def settings(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._group(update):
            return
        chat, user = update.effective_chat, update.effective_user
        if not await self._is_admin(ctx, chat.id, user.id):
            return await self._reply(update, T(self.db.get_lang(chat.id), "settings_admin"))
        text, kb = self._menu(chat.id)
        await self._reply(update, text, reply_markup=kb)

    async def cb_settings(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        q = update.callback_query
        chat_id = q.message.chat_id
        if not await self._is_admin(ctx, chat_id, q.from_user.id):
            return await q.answer(T(self.db.get_lang(chat_id), "settings_admin"), show_alert=True)
        parts = q.data.split(":")
        if len(parts) == 3 and parts[1] in SETTING_KEYS:
            if self.db.set_setting(chat_id, parts[1], parts[2]):
                await q.answer(T(self.db.get_lang(chat_id), "settings_saved"))
            text, kb = self._submenu(chat_id, parts[1])
        elif len(parts) == 2 and parts[1] in SETTING_KEYS:
            await q.answer()
            text, kb = self._submenu(chat_id, parts[1])
        else:
            await q.answer()
            text, kb = self._menu(chat_id)
        try:
            await q.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except TelegramError:
            pass                                    # message not modified

    # ------------------------------------------------------------ group tracking
    async def track_group(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Remember every group where the bot sees activity (for /admin announcements)."""
        chat = update.effective_chat
        if chat and chat.id not in self._seen:
            self._seen.add(chat.id)
            self.db.track_chat(chat.id, chat.title)

    async def my_chat_member(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """The bot was added to / removed from a group."""
        change = update.my_chat_member
        if change.chat.type == "private":
            return
        new, old = change.new_chat_member, change.old_chat_member
        active = new.status in ("member", "administrator")
        self.db.set_chat_active(change.chat.id, active, change.chat.title)
        if not active:
            self._seen.discard(change.chat.id)
            return
        self._seen.add(change.chat.id)
        chat_id, lang = change.chat.id, self.db.get_lang(change.chat.id)
        can_delete = new.status == "administrator" and bool(getattr(new, "can_delete_messages", False))
        was_in = old.status in ("member", "administrator")
        if not was_in:                      # just added: say hello and ask for the rights it needs
            await self.engine.io.send(chat_id, T(lang, "welcome_group"),
                                      None if can_delete else [admin_button(lang)])
        elif can_delete and not (old.status == "administrator" and getattr(old, "can_delete_messages", False)):
            await self.engine.io.send(chat_id, T(lang, "admin_ok"))
        elif new.status == "administrator" and not can_delete:
            await self.engine.io.send(chat_id, T(lang, "admin_missing"), [admin_button(lang)])
