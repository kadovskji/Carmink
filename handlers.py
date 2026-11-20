"""Telegram command handlers: thin wrappers around the Engine, the dictionary and the stats."""
import html
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

import config
import words
from db import ALLOWED_SETTINGS, Database
from engine import Engine
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
            code = (update.effective_user.language_code or "")[:2]
            await self._reply(update, T(code if code in LANGUAGES else lang, "start_private"))
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

    async def join(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._group(update):
            chat, user = update.effective_chat, update.effective_user
            await self.engine.join(chat.id, user.id, user.first_name, self._lang(chat.id))

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

    async def on_text(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Every group message may be a guess."""
        msg = update.effective_message
        if msg and msg.text and update.effective_user:
            await self.engine.on_message(update.effective_chat.id, update.effective_user.id,
                                         msg.text, msg.message_id)

    # ------------------------------------------------------------ group dictionary
    async def _can_edit_words(self, update, ctx) -> bool:
        chat, user = update.effective_chat, update.effective_user
        if self.db.get_settings(chat.id)["words"] == "everyone":
            return True
        if await self._is_admin(ctx, chat.id, user.id):
            return True
        await self._reply(update, T(self._lang(chat.id), "word_admin"))
        return False

    async def addword(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._group(update):
            return
        chat, user = update.effective_chat, update.effective_user
        lang = self._lang(chat.id)
        if not await self._can_edit_words(update, ctx):
            return
        args = list(ctx.args or [])
        diff = 2
        if len(args) > 1 and args[-1] in ("1", "2", "3"):
            diff = int(args.pop())
        if not args:
            return await self._reply(update, T(lang, "word_usage_add"))
        parsed = words.parse_custom(" ".join(args))
        if not parsed:
            return await self._reply(update, T(lang, "word_bad"))
        word, alts = parsed
        if self.db.count_custom(chat.id) >= config.CUSTOM_WORDS_MAX:
            return await self._reply(update, T(lang, "word_full", max=config.CUSTOM_WORDS_MAX))
        if self.db.add_word(chat.id, lang, word, diff, user.id, alts):
            extra = T(lang, "word_alts", alts=html.escape(", ".join(alts))) if alts else ""
            await self._reply(update, T(lang, "word_added", word=html.escape(word), diff=diff) + extra)
        else:
            await self._reply(update, T(lang, "word_dup", word=html.escape(word)))

    async def deleteword(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._group(update):
            return
        chat = update.effective_chat
        lang = self._lang(chat.id)
        if not await self._can_edit_words(update, ctx):
            return
        word = " ".join(ctx.args or []).strip()
        if not word:
            return await self._reply(update, T(lang, "word_usage_del"))
        key = html.escape(word)
        if self.db.delete_word(chat.id, lang, word):
            await self._reply(update, T(lang, "word_deleted", word=key))
        else:
            await self._reply(update, T(lang, "word_missing", word=key))

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
        if s["best_game"]:
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
        active = change.new_chat_member.status in ("member", "administrator")
        self.db.set_chat_active(change.chat.id, active, change.chat.title)
        if active:
            self._seen.add(change.chat.id)
        else:
            self._seen.discard(change.chat.id)
