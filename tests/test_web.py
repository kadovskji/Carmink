"""initData validation and the Mini App HTTP API."""
import json
import time
from urllib.parse import urlencode

import pytest
from starlette.testclient import TestClient

import auth
import config
from game import Phase
from webserver import create_app

TOKEN = "123456:TEST-TOKEN"
JPEG = b"\xff\xd8\xff\xe0" + b"x" * 80


def init_data(user_id=1, name="Ada", chat=-1001, token=TOKEN, age=0, **extra) -> str:
    fields = {"auth_date": str(int(time.time()) - age),
              "user": json.dumps({"id": user_id, "first_name": name}, separators=(",", ":")),
              "query_id": "AAH"}
    if chat is not None:
        fields["start_param"] = f"c{abs(chat)}"
    fields.update(extra)
    fields["hash"] = auth.sign(fields, token)
    return urlencode(fields)


def hdr(**kw) -> dict:
    return {"Authorization": "tma " + init_data(**kw)}


# ---------------------------------------------------------------- auth
def test_valid_init_data_is_accepted():
    a = auth.validate(init_data(user_id=42, name="Zoe"), TOKEN)
    assert a and a.user_id == 42 and a.name == "Zoe" and a.start_param == "c1001"


@pytest.mark.parametrize("make", [
    lambda: init_data(token="999:OTHER"),                                  # signed with another token
    lambda: init_data(age=auth.MAX_AGE + 60),                              # too old
    lambda: init_data().replace("Ada", "Eve"),                             # tampered
    lambda: "garbage",
    lambda: "",
    lambda: "auth_date=1&user=%7B%7D",                                     # no hash
])
def test_bad_init_data_is_rejected(make):
    assert auth.validate(make(), TOKEN) is None


def test_empty_token_never_validates():
    assert auth.validate(init_data(token=""), "") is None


# ---------------------------------------------------------------- API
@pytest.fixture
def client(env):
    return TestClient(create_app(env.engine, TOKEN))


def test_requests_need_valid_credentials(client):
    assert client.get("/api/state").status_code == 401
    assert client.get("/api/state", headers={"Authorization": "tma nope"}).status_code == 401
    assert client.get("/api/state", headers=hdr(chat=None)).status_code == 400
    assert client.get("/api/health").json()["ok"] is True


def test_static_files_and_cache_headers(client):
    r = client.get("/")
    assert r.status_code == 200 and "Carmink" in r.text and r.headers["cache-control"] == "no-cache"
    for name in ("app.js", "fill.js", "board.js", "style.css"):
        assert client.get("/" + name).status_code == 200
    assert client.get("/api/state", headers=hdr()).headers["cache-control"] == "no-store"


def test_no_game(client):
    assert client.get("/api/state", headers=hdr()).json()["phase"] == "none"


def test_drawer_flow_over_http(env, client):
    g = env.start_match(3)
    t = env.to_choosing()
    d = t.drawer
    other = next(u for u in g.players if u != d)

    s = client.get("/api/state", headers=hdr(user_id=d)).json()
    assert s["role"] == "drawer" and len(s["choices"]) == 3 and s["phase"] == "choosing"
    s = client.get("/api/state", headers=hdr(user_id=other)).json()
    assert s["role"] == "viewer" and "choices" not in s

    assert client.post("/api/choose", json={"index": 0}, headers=hdr(user_id=other)).status_code == 409
    assert client.post("/api/choose", json={"index": "x"}, headers=hdr(user_id=d)).status_code == 400
    assert client.post("/api/choose", json={"index": 9}, headers=hdr(user_id=d)).json() == {"error": "bad_choice"}
    assert client.post("/api/choose", json={"index": 1}, headers=hdr(user_id=d)).json() == {"ok": True}
    assert g.phase == Phase.STARTING

    assert client.post("/api/start", headers=hdr(user_id=d)).json() == {"ok": True}
    assert g.phase == Phase.DRAWING
    assert client.get("/api/snapshot.jpg", headers=hdr(user_id=other)).status_code == 204

    r = client.post("/api/snapshot", content=JPEG, headers=hdr(user_id=d))
    assert r.json() == {"ok": True}
    r = client.get("/api/snapshot.jpg", headers=hdr(user_id=other))
    assert r.status_code == 200 and r.content == JPEG and r.headers["content-type"] == "image/jpeg"
    assert client.post("/api/snapshot", content=b"nope", headers=hdr(user_id=d)).status_code == 409

    h = client.post("/api/hint", headers=hdr(user_id=d)).json()
    assert h["ok"] and "_" in h["mask"]
    assert client.post("/api/hint", headers=hdr(user_id=other)).status_code == 409

    assert client.post("/api/skip", headers=hdr(user_id=d)).json() == {"ok": True}
    assert g.turn_no == 2


def test_oversized_snapshot_is_refused(env, client):
    env.start_match(3)
    t = env.to_drawing()
    big = JPEG + b"0" * config.SNAPSHOT_MAX_BYTES
    assert client.post("/api/snapshot", content=big, headers=hdr(user_id=t.drawer)).status_code == 413


@pytest.mark.parametrize("name", ["fill.test.js", "board.test.js"])
def test_node_tests_pass(name):
    import shutil
    import subprocess
    from pathlib import Path
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not installed")
    script = Path(__file__).with_name(name)
    res = subprocess.run([node, str(script)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


def test_classic_guesses_and_live_events_over_http(env, client):
    g = env.start_match(3)                                  # classic
    t = env.to_drawing()
    d = t.drawer
    a = next(u for u in g.players if u != d)
    ev = [{"e": "begin", "op": {"k": "s", "c": "#000000", "w": 7, "p": [[5, 5]]}}, {"e": "end"}]
    assert client.post("/api/events", json={"from": 0, "events": ev}, headers=hdr(user_id=d)).json() == {"ok": True, "n": 2}
    assert client.post("/api/events", json={"from": 0, "events": ev}, headers=hdr(user_id=a)).status_code == 409
    assert client.post("/api/events", json={"events": ev}, headers=hdr(user_id=d)).status_code == 400
    assert client.post("/api/events", json={"from": 7, "events": ev}, headers=hdr(user_id=d)).json() == {"error": "gap"}

    r = client.get(f"/api/live?turn={g.turn_no}&since=0&att=0", headers=hdr(user_id=a)).json()
    assert r["turn"] == g.turn_no and len(r["events"]) == 2 and r["attempts"] == []
    assert client.get("/api/live?turn=zzz", headers=hdr(user_id=a)).json()["ev"] == 0

    assert client.post("/api/guess", json={"text": "boh"}, headers=hdr(user_id=a, name="Bea")).json()["result"] == "wrong"
    assert client.post("/api/guess", json={}, headers=hdr(user_id=a)).status_code == 400
    assert client.post("/api/guess", json={"text": "x"}, headers=hdr(user_id=d)).json() == {"error": "is_drawer"}
    r = client.post("/api/guess", json={"text": t.word.word}, headers=hdr(user_id=a))
    assert r.json()["result"] == "right"
    s = client.get("/api/state", headers=hdr(user_id=a)).json()
    assert s["mode"] == "classic" and s["me_guessed"] > 0 and "word" not in s
    live = client.get(f"/api/live?turn={g.turn_no}&since=2&att=0", headers=hdr(user_id=d)).json()
    assert live["events"] == [] and [x["r"] for x in live["attempts"]] == [False, True]
