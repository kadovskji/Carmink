"""Command handlers with fake Telegram objects (python-telegram-bot is stubbed when not installed)."""
import sys
import types
from types import SimpleNamespace as NS

try:                                                    # use the real library when it is there
    import telegram  # noqa: F401
    import telegram.ext  # noqa: F401
except ImportError:                                     # minimal stand-ins: handlers only touch attributes
    tg = types.ModuleType("telegram")
    err = types.ModuleType("telegram.error")
    ext = types.ModuleType("telegram.ext")

    class TelegramError(Exception):
        pass

    class _Box:
        def __init__(self, *a, **kw):
            self.args, self.kw = a, kw

    tg.InlineKeyboardButton = type("InlineKeyboardButton", (_Box,), {})
    tg.InlineKeyboardMarkup = type("InlineKeyboardMarkup", (_Box,), {})
    tg.Update = type("Update", (), {})
    err.TelegramError = TelegramError
    ext.ContextTypes = NS(DEFAULT_TYPE=object)
    sys.modules.update({"telegram": tg, "telegram.error": err, "telegram.ext": ext})

import pytest  # noqa: E402

import config  # noqa: E402
from handlers import Handlers  # noqa: E402

CHAT = -1001


class FakeMessage:
    def __init__(self):
        self.replies: list[str] = []

    async def reply_text(self, text, **kw):
        self.replies.append(text)


def upd(user_id=1, name="Ada", chat=CHAT, kind="supergroup"):
    msg = FakeMessage()
    return NS(effective_chat=NS(id=chat, type=kind, title="Club"), effective_user=NS(
        id=user_id, first_name=name, language_code="it"), effective_message=msg, message=msg), msg


def ctx(*args):
    return NS(args=list(args))


@pytest.fixture
def h(env):
    return Handlers(env.engine, env.db)


def run(env, coro):
    return env.run(coro)


def test_start_in_private_and_group(env, h):
    u, m = upd(kind="private", chat=5)
    run(env, h.start(u, ctx()))
    assert "Carmink" in m.replies[0] and "/newgame" in m.replies[0]
    u, m = upd()
    run(env, h.start(u, ctx()))
    assert "/newgame" in m.replies[0]


def test_group_commands_refuse_private_chats(env, h):
    u, m = upd(kind="private", chat=5)
    run(env, h.newgame(u, ctx()))
    assert "gruppo" in m.replies[0] and not env.engine.games


def test_newgame_language_argument_and_lobby_commands(env, h):
    u, _ = upd()
    run(env, h.newgame(u, ctx("en")))
    assert env.game.lang == "en"
    for uid in (2, 3):
        run(env, h.join(upd(uid, f"P{uid}")[0], ctx()))
    run(env, h.wait(upd()[0], ctx("2")))
    run(env, h.ready(upd()[0], ctx()))
    assert env.game.phase.name == "BREAK"
    run(env, h.quit(upd(3, "P3")[0], ctx()))
    assert 3 not in env.game.players


def test_newgame_uses_the_group_language_by_default(env, h):
    env.db.set_setting(CHAT, "lang", "en")
    run(env, h.newgame(upd()[0], ctx()))
    assert env.game.lang == "en"


def test_guesses_reach_the_engine(env, h):
    env.start_match(3)
    t = env.to_drawing()
    guesser = next(u for u in env.game.players if u != t.drawer)
    msg = NS(text=t.word.word, message_id=77)
    update = NS(effective_message=msg, effective_chat=NS(id=CHAT), effective_user=NS(id=guesser))
    run(env, h.on_text(update, ctx()))
    assert 77 in env.io.deleted and env.game.scores[guesser] > 0


def test_addword_permissions_validation_and_dictionary(env, h):
    run(env, h.newgame(upd()[0], ctx()))            # lang it
    u, m = upd(2, "Bob")
    run(env, h.addword(u, ctx("zattera")))
    assert "admin" in m.replies[-1]
    env.io.admins.add(2)
    run(env, h.addword(u, ctx("orso", "polare", "3")))
    assert "orso polare" in m.replies[-1] and "difficoltà 3" in m.replies[-1]
    run(env, h.addword(u, ctx("Orso", "Polare")))
    assert "già nel dizionario" in m.replies[-1]
    run(env, h.addword(u, ctx("12345")))
    assert "non valida" in m.replies[-1]
    run(env, h.addword(u, ctx()))
    assert "Uso:" in m.replies[-1]
    assert [e.word for e in env.db.custom_entries(CHAT, "it")] == ["orso polare"]
    run(env, h.deleteword(u, ctx("ORSO", "polare")))
    assert "tolta" in m.replies[-1] and not env.db.custom_entries(CHAT, "it")
    run(env, h.deleteword(u, ctx("cane")))
    assert "non è nel dizionario" in m.replies[-1]


def test_addword_with_synonyms(env, h):
    run(env, h.newgame(upd()[0], ctx()))
    env.io.admins.add(2)
    u, m = upd(2, "Bob")
    run(env, h.addword(u, ctx("monopattino", "|", "scooter", "|", "Kick", "scooter", "|", "monopattino", "3")))
    assert "Sinonimi accettati: scooter, Kick scooter" in m.replies[-1] and "difficoltà 3" in m.replies[-1]
    (e,) = env.db.custom_entries(CHAT, "it")
    assert e.word == "monopattino" and e.alts == ("scooter", "Kick scooter") and e.diff == 3
    from words import is_correct
    assert is_correct(e, "SCOOTER") and is_correct(e, "kickscooter")
    # a synonym that already exists elsewhere in the dictionary is accepted
    run(env, h.addword(u, ctx("seggiolone", "|", "sedia")))
    assert "aggiunta" in m.replies[-1]
    run(env, h.addword(u, ctx("|", "xx")))
    assert "non valida" in m.replies[-1]
    run(env, h.addword(u, ctx("cane", "|", "12")))
    assert "non valida" in m.replies[-1]


def test_dictionary_open_to_everyone_when_the_group_chooses_so(env, h):
    env.db.set_setting(CHAT, "words", "everyone")
    u, m = upd(9, "Zed")
    run(env, h.addword(u, ctx("zattera")))
    assert "aggiunta" in m.replies[-1]


def test_custom_dictionary_limit(env, h, monkeypatch):
    monkeypatch.setattr(config, "CUSTOM_WORDS_MAX", 1)
    env.db.set_setting(CHAT, "words", "everyone")
    u, m = upd()
    run(env, h.addword(u, ctx("uno")))
    run(env, h.addword(u, ctx("due")))
    assert "pieno" in m.replies[-1]


def test_stats_after_a_finished_match(env, h):
    u, m = upd()
    run(env, h.stats(u, ctx()))
    assert "Nessuna partita finita" in m.replies[-1]
    g = env.start_match(3)
    while env.game:
        t = env.to_drawing()
        for uid in list(g.players):
            if uid != t.drawer:
                env.guess(uid, t.word.word)
    run(env, h.stats(u, ctx()))
    text = m.replies[-1]
    assert "1 partite" in text and "Più punti totali" in text and "Miglior partita" in text
    run(env, h.mystats(u, ctx()))
    assert "Partite: 1" in m.replies[-1] and "Turni disegnati: 2" in m.replies[-1]
    u2, m2 = upd(99, "Nobody")
    run(env, h.mystats(u2, ctx()))
    assert "Non hai ancora finito" in m2.replies[-1]


def test_settings_menu_text(env, h):
    env.io.admins.add(1)
    u, m = upd()
    run(env, h.settings(u, ctx()))
    assert "Impostazioni" in m.replies[-1]
    u2, m2 = upd(2, "Bob")
    run(env, h.settings(u2, ctx()))
    assert "Solo gli admin" in m2.replies[-1]
    text, _ = h._submenu(CHAT, "lang")
    assert "Lingua" in text


def test_help_in_group_and_private(env, h):
    u, m = upd()
    run(env, h.help(u, ctx()))
    assert "/addword" in m.replies[-1] and "/help" in m.replies[-1]
