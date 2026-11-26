"""Admin test matches: fake players, everything lands in the admin's chat, nothing is saved."""
import json
import time
from urllib.parse import urlencode

import pytest
from starlette.testclient import TestClient

import auth
import config
from conftest import Env
from game import Phase
from test_broken import jpeg
from webserver import create_app

ADMIN = 777
TOKEN = "123456:TEST-TOKEN"


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_IDS", {ADMIN})
    monkeypatch.setattr(config, "BROKEN_GIF_GAP", 0.0)
    monkeypatch.setattr(config, "SNAPSHOT_MIN_INTERVAL", 0.0)


def start(env: Env, mode: str, n: int):
    return env.run(env.engine.new_test_game(ADMIN, "it", mode, n))


def init(uid=ADMIN, param=f"t{ADMIN}") -> dict:
    f = {"auth_date": str(int(time.time())), "query_id": "x", "start_param": param,
         "user": json.dumps({"id": uid, "first_name": "A"}, separators=(",", ":"))}
    f["hash"] = auth.sign(f, TOKEN)
    return {"Authorization": "tma " + urlencode(f)}


def test_broken_test_game_runs_alone_and_saves_nothing(monkeypatch):
    env = Env()
    saved = []
    monkeypatch.setattr(env.db, "save_game", lambda *a, **k: saved.append(a))
    g = start(env, "broken", 4)
    assert g.test and len(g.test_ids) == 4 and g.phase == Phase.WRITING
    assert not env.io.dms                                   # DMs were rerouted to the admin chat
    assert sum("📩" in x for x in env.io.texts()) == 4
    for n in range(1, 5):
        assert env.run(env.engine.act_as(ADMIN, n, f"frase {n}")) is None
    assert g.phase == Phase.STEP and g.broken.step == 1
    for _ in range(g.broken.steps):
        for u in g.test_ids:
            env.run(env.engine.bk_submit(ADMIN, u, jpeg()) if g.broken.kind == "draw"
                    else env.engine.on_private(u, "descrizione"))
    assert ADMIN not in env.engine.games
    assert not env.io.dms
    assert not saved
    assert not env.engine.user_game


def test_speedrun_guess_with_t_command():
    env = Env()
    g = start(env, "speedrun", 3)
    env.run(env.io.advance(config.BREAK_SECONDS))
    t = g.turn
    env.engine.choose(ADMIN, t.drawer, 0)
    env.run(env.engine.start_drawing(ADMIN, t.drawer))
    n = next(i for i, u in enumerate(g.test_ids, 1) if u != t.drawer)
    env.run(env.engine.act_as(ADMIN, n, t.word.word))
    assert not env.io.deleted
    assert g.scores[g.test_ids[n - 1]] > 0


def test_classic_guess_via_act_as_reports_result():
    env = Env()
    g = start(env, "classic", 3)
    env.run(env.io.advance(config.BREAK_SECONDS))
    t = g.turn
    env.engine.choose(ADMIN, t.drawer, 0)
    env.run(env.engine.start_drawing(ADMIN, t.drawer))
    n = next(i for i, u in enumerate(g.test_ids, 1) if u != t.drawer)
    assert "wrong" in env.run(env.engine.act_as(ADMIN, n, "zzzqqq"))
    assert "Test 9" not in (env.run(env.engine.act_as(ADMIN, 9, "x")) or "")


def test_no_second_test_and_end_test():
    env = Env()
    assert start(env, "speedrun", 3)
    assert start(env, "speedrun", 3) is None
    assert env.run(env.engine.end_test(ADMIN))
    assert ADMIN not in env.engine.games and not env.engine.user_game


def test_link_uses_the_test_parameter():
    env = Env()
    start(env, "broken", 4)
    assert f"startapp=t{ADMIN}" in env.engine.link(ADMIN)


def test_mini_app_impersonation_only_for_admin():
    env = Env()
    g = start(env, "classic", 3)
    c = TestClient(create_app(env.engine, TOKEN))
    st = c.get("/api/state", headers=init()).json()
    assert st["test"]["players"][0]["name"] == "Test 1"
    drawer = g.test_ids[0]
    as_hdr = {**init(), "X-Test-As": str(drawer)}
    assert c.get("/api/state", headers=as_hdr).json()["in_game"] is True
    assert c.get("/api/state", headers=init()).json()["in_game"] is False
    # a non-admin can't open a test match, nor impersonate
    assert c.get("/api/state", headers=init(uid=5, param=f"t{ADMIN}")).status_code == 403
    # unknown fake id is ignored
    bad = {**init(), "X-Test-As": "42"}
    assert c.get("/api/state", headers=bad).json()["in_game"] is False


# ---------------------------------------------------------------- control panel (buttons)
def make_admin(env):
    import sys
    import test_handlers  # noqa: F401  (installs the telegram stand-in when the library is missing)
    tg, err = sys.modules["telegram"], sys.modules["telegram.error"]
    if not getattr(tg, "__file__", None):               # stand-in: give it what admin.py needs
        class Button:
            def __init__(self, text, callback_data=None, url=None):
                self.text, self.callback_data, self.url = text, callback_data, url

        class Markup:
            def __init__(self, rows):
                self.inline_keyboard = rows

        tg.InlineKeyboardButton, tg.InlineKeyboardMarkup = Button, Markup
        err.Forbidden = err.TelegramError
    from admin import Admin
    return Admin(env.db, env.engine)


def test_panel_buttons_play_speedrun_round():
    env = Env()
    a = make_admin(env)
    g = start(env, "speedrun", 3)
    env.run(env.io.advance(config.BREAK_SECONDS))
    assert "sceglie" in a._test_panel(ADMIN)[1].inline_keyboard[0][0].text
    env.run(a._test_action(ADMIN, "c", 0))
    env.run(a._test_action(ADMIN, "s", 0))
    assert g.phase == Phase.DRAWING
    n = next(i for i, u in enumerate(g.test_ids, 1) if u != g.turn.drawer)
    env.run(a._test_action(ADMIN, "w", n))
    assert g.phase == Phase.DRAWING
    env.run(a._test_action(ADMIN, "r", n))
    assert g.scores[g.test_ids[n - 1]] > 0


def test_panel_buttons_play_classic_round():
    env = Env()
    a = make_admin(env)
    g = start(env, "classic", 3)
    env.run(env.io.advance(config.BREAK_SECONDS))
    env.run(a._test_action(ADMIN, "c", 0))
    env.run(a._test_action(ADMIN, "s", 0))
    n = next(i for i, u in enumerate(g.test_ids, 1) if u != g.turn.drawer)
    env.run(a._test_action(ADMIN, "r", n))
    assert g.test_ids[n - 1] in g.turn.guessed
    rows = a._test_panel(ADMIN)[1].inline_keyboard
    assert all(f"Test {n} " not in b.text for r in rows for b in r)      # already guessed


def test_panel_buttons_play_a_whole_broken_game(monkeypatch):
    env = Env()
    a = make_admin(env)
    g = start(env, "broken", 4)
    env.run(a._test_action(ADMIN, "pall", 0))
    assert g.broken.step == 1 and g.broken.kind == "draw"
    for _ in range(g.broken.steps):
        act = "dall" if g.broken.kind == "draw" else "pall"
        env.run(a._test_action(ADMIN, act, 0))
    assert ADMIN not in env.engine.games
    assert any("triangolo" in x or "giallo" in x or "cerchio" in x or "rosso" in x
               or "quadrato" in x or "arancione" in x or "stella" in x or "blu" in x
               or "rombo" in x or "verde" in x or "cuore" in x or "viola" in x
               or "croce" in x or "rosa" in x for x in env.io.texts()) or env.io.animations
