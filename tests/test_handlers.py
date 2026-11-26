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


class FakeQuery:
    def __init__(self, data, user_id=1, name="Ada"):
        self.data, self.from_user = data, NS(id=user_id, first_name=name)
        self.answers: list[tuple] = []
        self.message = NS(chat_id=CHAT, chat=NS(title="Club"), delete=self._delete)
        self.deleted = False

    async def answer(self, text=None, show_alert=False):
        self.answers.append((text, show_alert))

    async def _delete(self):
        self.deleted = True


def pick_mode(env, h, mode="speedrun", lang="it", user_id=1, name="Ada"):
    q = FakeQuery(f"m:{mode}:{lang}:1", user_id, name)
    run(env, h.cb_mode(NS(callback_query=q), ctx()))
    return q


def test_group_commands_refuse_private_chats(env, h):
    u, m = upd(kind="private", chat=5)
    run(env, h.newgame(u, ctx()))
    assert "gruppo" in m.replies[0] and not env.engine.games


def test_newgame_language_argument_and_lobby_commands(env, h):
    u, _ = upd()
    run(env, h.newgame(u, ctx("en")))
    pick_mode(env, h, lang="en")
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
    pick_mode(env, h, lang="en")
    assert env.game.lang == "en"


def test_guesses_reach_the_engine(env, h):
    env.start_match(3, mode="speedrun")
    t = env.to_drawing()
    guesser = next(u for u in env.game.players if u != t.drawer)
    msg = NS(text=t.word.word, message_id=77)
    update = NS(effective_message=msg, effective_chat=NS(id=CHAT), effective_user=NS(id=guesser))
    run(env, h.on_text(update, ctx()))
    assert 77 in env.io.deleted and env.game.scores[guesser] > 0


def test_settings_menu_has_the_dictionary_button_and_no_word_commands(env, h):
    env.io.admins.add(1)
    u, m = upd()
    run(env, h.settings(u, ctx()))
    _, kb = h._menu(CHAT)
    rows = getattr(kb, "inline_keyboard", None) or kb.args[0]          # real markup, or the stand-in
    urls = [getattr(b, "url", None) or b.kw.get("url") for row in rows for b in row]
    urls = [u for u in urls if u]
    assert urls and urls[-1].endswith("?startapp=d1001")
    assert not hasattr(h, "addword") and not hasattr(h, "deleteword")


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
    assert "Dizionario" in m.replies[-1] and "/help" in m.replies[-1] and "/addword" not in m.replies[-1]


def test_newgame_offers_the_three_modes_and_only_the_creator_picks(env, h):
    u, m = upd()
    run(env, h.newgame(u, ctx()))
    assert env.game is None and "Speedrun" in m.replies[-1]
    # somebody else presses a button: refused, nothing opens
    q = pick_mode(env, h, user_id=2, name="Bob")
    assert q.answers[-1][1] is True and env.game is None
    # Broken Canva needs the creator to have opened the bot in private
    pick_mode(env, h, mode="broken")
    assert env.game is None and env.io.sent[-1]["buttons"][0][1].endswith(f"?start=j{abs(CHAT)}")
    q = pick_mode(env, h, mode="speedrun")
    assert env.game.mode == "speedrun" and q.deleted and env.game.creator == 1
    assert "Speedrun" in env.io.texts()[-1]


def test_newgame_refused_when_a_match_exists(env, h):
    env.start_match(3)
    u, m = upd()
    run(env, h.newgame(u, ctx()))
    assert "già una partita" in env.io.texts()[-1]


def test_late_join_can_be_turned_off_in_the_settings(env, h):
    env.start_match(3)
    run(env, h.join(upd(7, "Late")[0], ctx()))
    assert 7 in env.game.players and 7 in env.game.queue
    env.db.set_setting(CHAT, "latejoin", "off")
    run(env, h.join(upd(8, "Later")[0], ctx()))
    assert 8 not in env.game.players and "non si può entrare" in env.io.texts()[-1]


def test_start_in_private_registers_the_user_and_joins_a_broken_lobby(env, h):
    env.db.add_dm(1)
    run(env, env.engine.new_game(CHAT, 1, "Ada", "it", "broken"))
    assert not env.db.has_dm(2)
    u, m = upd(2, "Bea", chat=2, kind="private")
    run(env, h.start(u, ctx(f"j{abs(CHAT)}")))           # the "Avvia il bot" button of the group
    assert env.db.has_dm(2) and 2 in env.game.players and "Perfetto" in m.replies[-1]
    u, m = upd(3, "Cleo", chat=3, kind="private")
    run(env, h.start(u, ctx("j999")))                     # no such match: just registered
    assert env.db.has_dm(3) and 3 not in env.game.players


def test_private_text_reaches_the_broken_game(env, h):
    for uid in range(1, 5):
        env.db.add_dm(uid)
    g = env.start_match(4, "it", "broken")
    u, _ = upd(2, "P2", chat=2, kind="private")
    u.effective_message.text = "un'anatra con gli stivali"
    run(env, h.on_private_text(u, ctx()))
    assert g.broken.inbox[2]["text"] == "un'anatra con gli stivali"


# ---------------------------------------------------------------- the bot is added to a group
def member_update(old, new, chat=CHAT):
    def m(status, delete=False):
        return NS(status=status, can_delete_messages=delete)
    return NS(my_chat_member=NS(chat=NS(id=chat, type="supergroup", title="Club"),
                                old_chat_member=m(*old), new_chat_member=m(*new)))


def test_adding_the_bot_asks_for_admin_rights(env, h):
    run(env, h.my_chat_member(member_update(("left",), ("member",)), ctx()))
    msg = env.io.sent[-1]
    assert "amministratore" in msg["text"] and "eliminare i messaggi" in msg["text"]
    assert "startgroup=true&admin=delete_messages" in msg["buttons"][0][1]
    assert env.db.query("SELECT active FROM known_chats WHERE chat_id = ?", (CHAT,)) == [(1,)]


def test_added_directly_as_admin_with_rights_gets_no_button(env, h):
    run(env, h.my_chat_member(member_update(("left",), ("administrator", True)), ctx()))
    assert env.io.sent[-1]["buttons"] is None


def test_promotion_is_acknowledged_and_missing_rights_are_flagged(env, h):
    run(env, h.my_chat_member(member_update(("member",), ("administrator", True)), ctx()))
    assert "Perfetto" in env.io.sent[-1]["text"]
    run(env, h.my_chat_member(member_update(("member",), ("administrator", False)), ctx()))
    assert "mi manca" in env.io.sent[-1]["text"] and env.io.sent[-1]["buttons"]
    n = len(env.io.sent)
    run(env, h.my_chat_member(member_update(("administrator", True), ("member",)), ctx()))
    assert len(env.io.sent) == n                                 # demoted: no message


def test_removed_bot_is_marked_inactive(env, h):
    run(env, h.my_chat_member(member_update(("member",), ("kicked",)), ctx()))
    assert env.db.query("SELECT active FROM known_chats WHERE chat_id = ?", (CHAT,)) == [(0,)]


def test_drawing_time_appears_in_the_settings_menu(env, h):
    text, kb = h._menu(CHAT)
    labels = [b.kw.get("text", b.args[0] if b.args else "") if hasattr(b, "kw") else b.text
              for row in kb.inline_keyboard for b in row] if hasattr(kb, "inline_keyboard") else \
             [b.args[0] for row in kb.args[0] for b in row]
    assert any("Tempo per disegno" in l for l in labels)
    text, kb = h._submenu(CHAT, "drawtime")
    rows = kb.inline_keyboard if hasattr(kb, "inline_keyboard") else kb.args[0]
    flat = [b for row in rows for b in row]
    assert len(flat) == 8                                        # auto + six durations + back
