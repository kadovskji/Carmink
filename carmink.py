"""Carmink - a Telegram drawing and guessing party game bot.

One process runs both the bot (long polling) and the Mini App backend (uvicorn on
127.0.0.1:WEB_PORT, behind nginx).

Run:  BOT_TOKEN=xxxx python carmink.py
"""
import asyncio
import logging

import logs

logs.setup()

import uvicorn                                                          # noqa: E402
from telegram import BotCommand                                         # noqa: E402
from telegram.ext import (Application, CallbackQueryHandler, ChatMemberHandler,  # noqa: E402
                          CommandHandler, ContextTypes, MessageHandler, filters)

import config                                                           # noqa: E402
from admin import Admin                                                 # noqa: E402
from db import Database                                                 # noqa: E402
from engine import Engine                                               # noqa: E402
from handlers import Handlers                                           # noqa: E402
from tg_io import TelegramIO                                            # noqa: E402
from webserver import create_app                                        # noqa: E402

LOG = logging.getLogger("carmink")

# (command, English description, Italian description). /admin is deliberately not listed.
COMMANDS = [
    ("newgame", "Open a new match", "Apri una nuova partita"),
    ("join", "Join the match", "Unisciti alla partita"),
    ("ready", "Start the match now", "Avvia subito la partita"),
    ("wait", "Extend sign-ups: /wait <minutes>", "Prolunga le iscrizioni: /wait <minuti>"),
    ("quit", "Leave the match", "Lascia la partita"),
    ("stop", "Cancel the match", "Annulla la partita"),
    ("addword", "Add a word: /addword <word> [1-3]", "Aggiungi una parola: /addword <parola> [1-3]"),
    ("deleteword", "Remove a word you added", "Togli una parola che hai aggiunto"),
    ("stats", "Group statistics", "Statistiche del gruppo"),
    ("mystats", "Your statistics", "Le tue statistiche"),
    ("settings", "Group settings (admins)", "Impostazioni del gruppo (admin)"),
]


class ExplicitCommand(filters.MessageFilter):
    """Accept a command only if written as /command@BotName (in groups)."""

    def filter(self, message) -> bool:
        if message.chat.type == "private":
            return True
        for e in message.entities or []:
            if e.type == "bot_command" and e.offset == 0:
                return "@" in message.parse_entity(e)
        return False


def register(app: Application, h: Handlers, admin: Admin) -> None:
    explicit = ExplicitCommand()

    def command(name: str, handler) -> None:
        app.add_handler(CommandHandler(
            name, handler, filters=explicit if name in config.REQUIRE_TAG else None))

    for name, handler in (("start", h.start), ("newgame", h.newgame), ("join", h.join),
                          ("ready", h.ready), ("wait", h.wait), ("quit", h.quit),
                          ("stop", h.stop), ("addword", h.addword),
                          ("deleteword", h.deleteword), ("stats", h.stats),
                          ("mystats", h.mystats), ("settings", h.settings)):
        command(name, handler)
    app.add_handler(CommandHandler("admin", admin.admin, filters=filters.ChatType.PRIVATE))

    app.add_handler(CallbackQueryHandler(h.cb_settings, pattern=r"^s:"))
    app.add_handler(CallbackQueryHandler(admin.callback, pattern=r"^ad:"))

    app.add_handler(MessageHandler(filters.ChatType.GROUPS, h.track_group), group=-2)
    app.add_handler(ChatMemberHandler(h.my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, admin.handle_text))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, h.on_text))

    async def on_error(update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        LOG.error("unhandled error", exc_info=ctx.error)
    app.add_error_handler(on_error)


async def run() -> None:
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN is not set")
    db = Database(config.DB_FILE)

    async def post_init(app: Application) -> None:
        await admin.notify_restart(app.bot)
        await app.bot.set_my_commands([BotCommand(c, en) for c, en, _ in COMMANDS])
        await app.bot.set_my_commands([BotCommand(c, it) for c, _, it in COMMANDS],
                                      language_code="it")

    app = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()
    engine = Engine(TelegramIO(app), db)
    admin = Admin(db, engine)
    register(app, Handlers(engine, db), admin)

    server = uvicorn.Server(uvicorn.Config(
        create_app(engine, config.BOT_TOKEN), host=config.WEB_HOST, port=config.WEB_PORT,
        log_level="warning"))
    LOG.info("Carmink starting: web on %s:%s, admins: %d", config.WEB_HOST, config.WEB_PORT,
             len(config.ADMIN_IDS))
    async with app:
        await app.start()
        await app.updater.start_polling(
            allowed_updates=["message", "callback_query", "my_chat_member"])
        try:
            await server.serve()            # returns on SIGINT / SIGTERM
        finally:
            await app.updater.stop()
            await app.stop()


if __name__ == "__main__":
    asyncio.run(run())
