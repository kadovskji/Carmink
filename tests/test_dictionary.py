"""The group dictionary: copy of the built-in one, adaptive levels, the drawer's own word, the Mini App page."""
import json

import pytest
from starlette.testclient import TestClient

import config
import dictio
import words
from errors import GameError
from test_web import TOKEN, hdr
from webserver import create_app

CHAT = -1001


def stroke(env, t):
    """Something drawn: rounds without a drawing don't count for the statistics."""
    env.engine.snapshot(env.CHAT, t.drawer, b"\xff\xd8\xff\xe0" + b"x" * 40)


def play_round(env, t, solvers):
    for u in solvers:
        env.guess(u, t.word.word)
    if env.game and env.game.turn is t:
        env.run(env.io.advance(config.DRAW_DEFAULTS["classic"] + 1))     # time up


# ---------------------------------------------------------------- the dictionary becomes the group's
def test_first_match_copies_the_built_in_dictionary_into_the_group(env):
    assert env.db.count_custom(CHAT) == 0
    g = env.start_match(3)
    base = words.load("it")
    assert len(g.pool) == len(base) and env.db.count_custom(CHAT, "it") == len(base)
    assert {e.word for e in g.pool} == {e.word for e in base}
    assert {(e.word, e.diff, e.cat) for e in g.pool} == {(e.word, e.diff, e.cat) for e in base}


def test_the_copy_happens_once_and_keeps_edits(env):
    env.start_match(3)
    env.db.delete_word(CHAT, "it", "cane")
    env.run(env.engine.stop(CHAT, 1, True)) if hasattr(env.engine, "stop") else None
    env.engine.words_for(CHAT, "it")
    assert env.db.query("SELECT 1 FROM custom_words WHERE chat_id = ? AND word = 'cane'", (CHAT,)) == []


def test_words_added_before_the_copy_win_over_built_in_ones(env):
    env.db.add_word(CHAT, "it", "Cane", 3, 1, ("bau",))
    env.engine.words_for(CHAT, "it")
    cane = [e for e in env.db.custom_entries(CHAT, "it") if words.compact(e.word) == "cane"]
    assert len(cane) == 1 and cane[0].diff == 3 and cane[0].alts == ("bau",)


def test_each_language_is_copied_on_its_own_and_groups_are_independent(env):
    env.engine.words_for(CHAT, "it")
    assert env.db.count_custom(CHAT, "en") == 0 and env.db.count_custom(-2002) == 0
    env.engine.words_for(CHAT, "en")
    assert env.db.count_custom(CHAT, "en") == len(words.load("en"))


def test_test_matches_use_the_built_in_words_and_touch_nothing(env):
    env.db.add_dm(1)
    g = env.run(env.engine.new_test_game(1, "it", "classic", 3))
    env.run(env.io.advance(config.BREAK_SECONDS))
    assert len(g.pool) == len(words.load("it")) and env.db.count_custom(1) == 0


# ---------------------------------------------------------------- adaptive levels
def pick_word(env, entry_word):
    """Make the next drawer's first choice a given word of the group's dictionary."""
    t = env.to_choosing()
    entry = next(e for e in env.game.pool if e.word == entry_word)
    t.choices[0] = entry
    return t


def test_a_word_nobody_guesses_gets_harder_after_several_rounds(env):
    env.start_match(7)                                  # 6 guessers: every round has full weight
    word = next(e for e in env.game.pool if e.diff == 2).word
    levels = []
    for _ in range(7):
        t = pick_word(env, word)
        env.engine.choose(env.CHAT, t.drawer, 0)
        env.run(env.engine.start_drawing(env.CHAT, t.drawer))
        stroke(env, env.game.turn)
        env.run(env.io.advance(config.DRAW_DEFAULTS["classic"] + 1))
        env.run(env.io.advance(config.FINAL_SNAPSHOT_WAIT + 0.1))
        levels.append(env.db.query("SELECT diff FROM custom_words WHERE chat_id = ? AND word = ?", (CHAT, word))[0][0])
        if env.game is None:
            break
    assert levels[0] == 2 and levels[-1] == 3


def test_rounds_without_a_drawing_or_with_one_guesser_do_not_count(env):
    env.start_match(3)
    t = env.to_drawing()
    word = t.word.word
    env.run(env.io.advance(config.DRAW_DEFAULTS["classic"] + 1))      # nothing drawn: ignored
    assert env.db.query("SELECT shown FROM custom_words WHERE chat_id = ? AND word = ?", (CHAT, word))[0][0] == 0


def test_a_level_set_by_hand_is_not_adapted(env):
    env.start_match(5)
    word = next(e for e in env.game.pool if e.diff == 1).word
    assert env.db.update_word(CHAT, "it", word, diff=1, locked=True) == "ok"
    for _ in range(8):
        env.db.record_appearance(CHAT, "it", word, 0.0, 1.0)
    assert env.db.query("SELECT diff, shown FROM custom_words WHERE chat_id = ? AND word = ?", (CHAT, word))[0] == (1, 8)
    env.db.update_word(CHAT, "it", word, locked=False)
    for _ in range(8):
        env.db.record_appearance(CHAT, "it", word, 0.0, 1.0)
    assert env.db.query("SELECT diff FROM custom_words WHERE chat_id = ? AND word = ?", (CHAT, word))[0][0] > 1


def test_changing_the_level_by_hand_restarts_the_statistics(env):
    env.engine.words_for(CHAT, "it")
    for _ in range(5):
        env.db.record_appearance(CHAT, "it", "cane", 1.0, 1.0)
    env.db.update_word(CHAT, "it", "cane", diff=3, locked=False)
    assert env.db.query("SELECT diff, shown, ea, eb, base FROM custom_words WHERE chat_id = ? AND word = 'cane'",
                        (CHAT,))[0] == (3, 0, 0, 0, 3)


# ---------------------------------------------------------------- the drawer's own word
def test_the_drawer_can_write_his_own_word_and_gets_more_time(env):
    env.start_match(3)
    t = env.to_choosing()
    assert env.engine.web_state(CHAT, t.drawer)["own_word"] == {"extended": False, "max": config.WORD_MAX_LEN}
    env.engine.choose_more(CHAT, t.drawer)
    assert env.engine.web_state(CHAT, t.drawer)["ends_in"] > config.CHOOSE_SECONDS
    env.run(env.io.advance(config.CHOOSE_SECONDS + 5))                  # still choosing: no skip
    assert env.game.phase.name == "CHOOSING"
    env.engine.choose_custom(CHAT, t.drawer, "polpo gigante | Kraken")
    assert t.word.word == "polpo gigante" and t.word.alts == ("Kraken",) and t.word.diff == 2 and t.custom
    assert env.game.phase.name == "STARTING"


def test_a_bad_word_is_refused_and_only_the_drawer_in_the_choice_phase_may_write_it(env):
    env.start_match(3)
    t = env.to_choosing()
    for bad in ("", "a", "123", "uno due tre quattro cinque sei sette", "x" * 50):
        with pytest.raises(GameError) as e:
            env.engine.choose_custom(CHAT, t.drawer, bad)
        assert e.value.code == "bad_word"
    other = next(u for u in env.game.players if u != t.drawer)
    with pytest.raises(GameError):
        env.engine.choose_custom(CHAT, other, "polpo")


def test_the_extra_time_is_given_once(env):
    env.start_match(3)
    t = env.to_choosing()
    env.engine.choose_more(CHAT, t.drawer)
    first = env.game.deadline
    env.io.t += 10
    env.engine.choose_more(CHAT, t.drawer)
    assert env.game.deadline == first


def test_a_word_the_dictionary_already_has_is_used_as_it_is(env):
    env.start_match(3)
    t = env.to_choosing()
    known = next(e for e in env.game.pool if e.diff == 3)
    env.engine.choose_custom(CHAT, t.drawer, known.word.upper())
    assert t.word == known and not t.custom


def own_round(env, solvers, word="polpo gigante", n=5):
    g = env.start_match(n)
    t = env.to_choosing()
    env.engine.choose_custom(CHAT, t.drawer, word)
    env.run(env.engine.start_drawing(CHAT, t.drawer))
    stroke(env, g.turn)
    for u in [u for u in g.players if u != t.drawer][:solvers]:
        env.guess(u, word)
    if env.game and env.game.phase.name == "DRAWING":
        env.run(env.io.advance(config.DRAW_DEFAULTS["classic"] + 1))
    return g


def row(env, word):
    r = env.db.query("SELECT diff, cat, shown FROM custom_words WHERE chat_id = ? AND word = ?", (CHAT, word))
    return r[0] if r else None


def test_an_own_word_is_kept_if_somebody_guesses_it_with_the_level_from_how_many_did(env):
    own_round(env, solvers=4)                      # 4 of 4 guessers
    assert row(env, "polpo gigante") == (1, "custom", 1)


def test_an_own_word_that_few_guess_is_saved_as_hard(env):
    own_round(env, solvers=1)                      # 1 of 4
    assert row(env, "polpo gigante")[0] == 3


def test_an_own_word_nobody_guesses_is_not_kept(env):
    own_round(env, solvers=0)
    assert row(env, "polpo gigante") is None


def test_an_own_word_counts_as_medium_for_the_points(env):
    from game import guess_points
    g = env.start_match(3)
    t = env.to_choosing()
    env.engine.choose_custom(CHAT, t.drawer, "polpo gigante")
    env.run(env.engine.start_drawing(CHAT, t.drawer))
    guesser = next(u for u in g.players if u != t.drawer)
    env.guess(guesser, "polpo gigante")
    assert g.scores[guesser] == guess_points(g.draw_seconds, 2, 0, g.draw_seconds)


def test_speedrun_own_word(env):
    g = env.start_match(4, mode="speedrun")
    t = env.to_choosing()
    env.engine.choose_custom(CHAT, t.drawer, "polpo gigante")
    env.run(env.engine.start_drawing(CHAT, t.drawer))
    stroke(env, g.turn)
    env.run(env.io.advance(5))
    env.chat(next(u for u in g.players if u != t.drawer), "polpo gigante")
    assert row(env, "polpo gigante")[0] in (1, 2)


# ---------------------------------------------------------------- export / import
def test_a_text_list_is_parsed_with_synonyms_and_levels():
    items, bad = dictio.parse("polpo gigante | scooter | 3\nzattera\n12345\n\ncane | 1", "it")
    assert bad == 1 and [(i["w"], i["alts"], i["d"]) for i in items["it"]] == [
        ("polpo gigante", ["scooter"], 3), ("zattera", [], 2), ("cane", [], 1)]


def test_a_file_round_trips_with_what_the_group_learned(env):
    env.engine.words_for(CHAT, "it")
    for _ in range(3):
        env.db.record_appearance(CHAT, "it", "cane", 1.0, 1.0)
    env.db.update_word(CHAT, "it", "gatto", diff=3, locked=True)
    raw = dictio.dump(env.db.export_rows(CHAT))
    items, bad = dictio.parse(raw, "it")
    assert bad == 0 and len(items["it"]) == len(words.load("it"))
    other = -777
    res = dictio.merge(env.db, other, items, 5, dry=False)          # the other group has the base words already
    assert res["new"] == 0 and res["existing"] == len(words.load("it")) and res["changed"] == 2
    assert env.db.query("SELECT shown FROM custom_words WHERE chat_id = ? AND word = 'cane'", (other,)) == [(0,)]
    res = dictio.merge(env.db, other, items, 5, dry=True, update=True)
    assert env.db.query("SELECT shown FROM custom_words WHERE chat_id = ? AND word = 'cane'", (other,)) == [(0,)]
    dictio.merge(env.db, other, items, 5, dry=False, update=True)
    cane = env.db.query("SELECT diff, shown, locked FROM custom_words WHERE chat_id = ? AND word = 'cane'", (other,))[0]
    gatto = env.db.query("SELECT diff, locked FROM custom_words WHERE chat_id = ? AND word = 'gatto'", (other,))[0]
    assert cane[1] == 3 and gatto == (3, 1)


def test_importing_never_touches_what_the_group_already_has(env):
    env.db.add_word(CHAT, "it", "zattera", 3, 1)
    res = dictio.merge(env.db, CHAT, {"it": [{"w": "Zattera", "alts": [], "d": 1, "c": "custom", "b": 1,
                                              "ea": 0, "eb": 0, "n": 0, "l": False},
                                             {"w": "barca", "alts": [], "d": 1, "c": "custom", "b": 1,
                                              "ea": 0, "eb": 0, "n": 0, "l": False}]}, 1, dry=False)
    assert res == {"new": 1, "existing": 1, "changed": 1, "full": 0}
    assert row(env, "zattera")[0] == 3


def test_dry_run_changes_nothing_and_the_limit_is_respected(env, monkeypatch):
    monkeypatch.setattr(config, "CUSTOM_WORDS_MAX", 2)
    items, _ = dictio.parse("uno\ndue\ntre", "it")
    env.db.con.execute("INSERT INTO dict_ready VALUES (?, 'it')", (CHAT,))       # skip the copy of the base words
    assert dictio.merge(env.db, CHAT, items, 1, dry=True) == {"new": 2, "existing": 0, "changed": 0, "full": 1}
    assert env.db.count_custom(CHAT) == 0
    assert dictio.merge(env.db, CHAT, items, 1, dry=False)["new"] == 2 and env.db.count_custom(CHAT) == 2


@pytest.mark.parametrize("raw", ["{not json", '{"words": 3}', '{"carmink": 1}'])
def test_unreadable_files_are_refused(raw):
    with pytest.raises(ValueError):
        dictio.parse(raw, "it")


def test_a_hostile_file_cannot_smuggle_bad_values_in():
    raw = json.dumps({"carmink": 1, "words": {"it": [{"w": "ok", "d": 99, "ea": -5, "eb": "x", "c": "evil", "l": 1,
                                                       "alts": ["<b>", "fine"]}, {"w": 5}, "str"], "xx": [{"w": "no"}]}})
    items, bad = dictio.parse(raw, "it")
    (it,) = items["it"]
    assert it["d"] == 3 and it["c"] == "custom" and it["ea"] == 0 and it["eb"] == 0 and it["alts"] == ["fine"] and bad == 3


def test_codes_have_the_expected_shape():
    for _ in range(20):
        c = dictio.new_code()
        assert dictio.clean_code(c.lower().replace("-", " ")) == c and len(c) == 9
    assert dictio.clean_code("abc") == ""


# ---------------------------------------------------------------- the Mini App page (HTTP)
@pytest.fixture
def client(env):
    return TestClient(create_app(env.engine, TOKEN))


def dh(uid=1, chat=1001):
    return hdr(user_id=uid, start_param=f"d{chat}")


def test_only_admins_open_the_dictionary_unless_the_group_says_everyone(env, client):
    assert client.get("/api/dict", headers=dh(2)).status_code == 409
    env.io.admins.add(2)
    r = client.get("/api/dict", headers=dh(2))
    assert r.status_code == 200 and r.json()["lang"] == "it" and len(r.json()["words"]) == len(words.load("it"))
    env.db.set_setting(CHAT, "words", "everyone")
    assert client.get("/api/dict", headers=dh(3)).status_code == 409           # not a member
    env.io.members.add(3)
    assert client.get("/api/dict", headers=dh(3)).status_code == 200


def test_the_bot_owner_may_always_open_it(env, client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_IDS", {9})
    assert client.get("/api/dict", headers=dh(9)).status_code == 200


def test_test_chats_have_no_dictionary(env, client):
    r = client.get("/api/dict", headers=hdr(user_id=1, start_param="t1"))
    assert r.status_code in (403, 409)


def test_add_edit_delete_words(env, client):
    env.io.admins.add(1)
    h = dh()
    post = lambda action, **b: client.post(f"/api/dict/{action}", headers=h, json=b)
    assert post("add", text="polpo gigante | scooter | Kick scooter", diff=3).status_code == 200
    assert post("add", text="MONOPATTINO", diff=1).json()["error"] == "word_dup"
    assert post("add", text="12345").json()["error"] == "bad_word"
    w = next(x for x in client.get("/api/dict", headers=h).json()["words"] if x["w"] == "polpo gigante")
    assert w["alts"] == ["scooter", "Kick scooter"] and w["d"] == 3 and not w["lock"]
    assert post("edit", word="polpo gigante", new="polpo gigante elettrico", alts=["scooter"], diff=2, lock=True).status_code == 200
    w = next(x for x in client.get("/api/dict", headers=h).json()["words"] if x["w"] == "polpo gigante elettrico")
    assert w["alts"] == ["scooter"] and w["d"] == 2 and w["lock"]
    assert post("edit", word="polpo gigante elettrico", new="cane", alts=[], diff=2, lock=False).json()["error"] == "word_dup"
    assert post("edit", word="nonesiste", new="x y", alts=[], diff=2, lock=False).json()["error"] == "word_missing"
    assert post("delete", word="polpo gigante elettrico").status_code == 200
    assert post("delete", word="polpo gigante elettrico").json()["error"] == "word_missing"


def test_a_group_cannot_delete_its_dictionary_empty(env, client, monkeypatch):
    env.io.admins.add(1)
    monkeypatch.setattr(config, "DICT_MIN_WORDS", len(words.load("it")))
    r = client.post("/api/dict/delete", headers=dh(), json={"word": "cane"})
    assert r.json()["error"] == "dict_min" and r.json()["min"] == len(words.load("it"))


def test_export_sends_the_file_in_private(env, client):
    env.io.admins.add(1)
    r = client.post("/api/dict/export", headers=dh(), json={})
    assert r.status_code == 200
    (doc,) = env.io.documents
    assert doc["user"] == 1 and doc["filename"].endswith(".json")
    assert len(json.loads(doc["data"])["words"]["it"]) == len(words.load("it"))
    env.io.dm_fail.add(1)
    assert client.post("/api/dict/export", headers=dh(), json={}).json()["error"] == "need_dm"


def test_import_a_pasted_list_with_preview_then_for_real(env, client):
    env.io.admins.add(1)
    h = dh()
    body = {"text": "polpo gigante | kraken | 3\nzattera\ncane\n???", "dry": True}
    r = client.post("/api/dict/import", headers=h, json=body).json()
    assert (r["new"], r["existing"], r["invalid"]) == (2, 1, 1)
    assert env.db.count_custom(CHAT, "it") == len(words.load("it"))
    client.post("/api/dict/import", headers=h, json={**body, "dry": False})
    assert row(env, "polpo gigante")[0] == 3 and row(env, "zattera")[0] == 2
    assert client.post("/api/dict/import", headers=h, json={"text": "!!!", "dry": False}).json()["error"] == "bad_file"
    big = {"text": "a" * (config.DICT_IMPORT_MAX_BYTES + 10)}
    assert client.post("/api/dict/import", headers=h, json=big).status_code in (409, 413, 400)


def test_a_code_carries_a_dictionary_from_one_group_to_another(env, client, monkeypatch):
    env.io.admins.add(1)
    env.db.add_word(CHAT, "it", "polpo gigante", 3, 1, ("kraken",))
    code = client.post("/api/dict/code", headers=dh(), json={}).json()["code"]
    other = -2002
    r = client.post("/api/dict/import", headers=dh(chat=2002), json={"code": code.lower(), "dry": False})
    assert r.status_code == 200 and r.json()["new"] >= 1
    got = env.db.query("SELECT diff, alts FROM custom_words WHERE chat_id = ? AND word = 'polpo gigante'", (other,))
    assert got == [(3, "kraken")]
    assert client.post("/api/dict/import", headers=dh(chat=2002), json={"code": "ZZZZ-ZZZZ"}).json()["error"] == "bad_code"
    env.io.t += config.DICT_CODE_HOURS * 3600 + 5
    assert client.post("/api/dict/import", headers=dh(chat=2002), json={"code": code}).json()["error"] == "bad_code"


def test_choosing_an_own_word_through_the_api(env, client):
    g = env.start_match(3)
    t = env.to_choosing()
    h = hdr(user_id=t.drawer)
    assert client.post("/api/choose_more", headers=h, json={}).status_code == 200
    assert client.post("/api/choose_custom", headers=h, json={"text": "123"}).json()["error"] == "bad_word"
    assert client.post("/api/choose_custom", headers=h, json={"text": "polpo gigante"}).status_code == 200
    assert g.turn.word.word == "polpo gigante"


def test_a_database_from_before_the_adaptive_dictionary_is_upgraded(tmp_path):
    import sqlite3
    from db import Database
    p = str(tmp_path / "old.db")
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE custom_words (chat_id INTEGER NOT NULL, lang TEXT NOT NULL, word TEXT NOT NULL, "
                "diff INTEGER NOT NULL DEFAULT 2, added_by INTEGER, alts TEXT NOT NULL DEFAULT '', "
                "PRIMARY KEY (chat_id, lang, word))")
    con.execute("INSERT INTO custom_words VALUES (1, 'it', 'zattera', 3, 5, 'barchetta')")
    con.commit(); con.close()
    db = Database(p)
    db.ensure_dictionary(1, "it")
    assert db.count_custom(1, "it") == len(words.load("it")) + 1
    z = next(w for w in db.dictionary(1, "it") if w["w"] == "zattera")
    assert z["d"] == 3 and z["alts"] == ["barchetta"] and z["cat"] == "custom" and not z["lock"]
    for _ in range(6):                                  # `base` was never set: the level is the prior
        db.record_appearance(1, "it", "zattera", 0.0, 1.0)
    assert db.query("SELECT diff FROM custom_words WHERE chat_id = 1 AND word = 'zattera'")[0][0] == 3
