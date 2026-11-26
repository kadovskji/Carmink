"""Carmeleon and Code Stroke (beta): setup, secrets, turns, votes, grid rules, scoring."""
import io

import pytest
from PIL import Image

import config
from engine import GameError
from game import Phase


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(config, "SNAPSHOT_MIN_INTERVAL", 0.0)


def jpeg(color="white") -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (80, 60), color).save(b, "JPEG")
    return b.getvalue()


def cb(env, uid, data):
    return env.run(env.engine.on_callback(env.CHAT, uid, data))


def draw_turn(env, mode="carmeleon"):
    """The current drawer hands a drawing in through the Mini App endpoints."""
    g = env.game
    uid = g.cm.current
    env.run(env.engine.bk_submit(env.CHAT, uid, jpeg()))
    return uid


# ================================================================ Carmeleon
def start_cm(env, n=4, lang="it"):
    return env.start_match(n, lang, "carmeleon")


def test_carmeleon_table_secret_and_roles(env):
    g = start_cm(env)
    cm = g.cm
    assert len(cm.table) == 15 and len({e.cat for e in cm.table}) == 3
    assert all(sum(1 for e in cm.table if e.cat == c) == 5 for c in {e.cat for e in cm.table})
    states = {u: env.engine.web_state(env.CHAT, u) for u in g.players}
    cham = cm.chameleon
    assert states[cham]["cm"]["me"] == "chameleon" and states[cham]["cm"]["key"] is None
    for u, s in states.items():
        if u != cham:
            assert s["cm"]["key"] == cm.key and s["cm"]["me"] == "knows"
    assert env.engine.web_state(env.CHAT, 999)["cm"]["key"] is None        # a spectator doesn't see the key
    cur = cm.current
    assert states[cur]["bk"]["prompt"] and states[cur]["bk"]["active"]
    assert all("bk" not in s for u, s in states.items() if u != cur)


def test_carmeleon_nobody_joins_a_running_match(env):
    g = start_cm(env)
    env.run(env.engine.join(env.CHAT, 77, "Late", "it"))
    assert 77 not in g.players and any("non permette" in t for t in env.io.texts())


def test_carmeleon_needs_four_players(env):
    env.run(env.engine.new_game(env.CHAT, 1, "Ada", "it", "carmeleon"))
    for u in (2, 3):
        env.run(env.engine.join(env.CHAT, u, f"P{u}", "it"))
    env.run(env.engine.ready(env.CHAT, 1, "it"))
    assert env.game.phase == Phase.LOBBY


def test_carmeleon_only_the_current_drawer_can_hand_in(env):
    g = start_cm(env)
    other = next(u for u in g.players if u != g.cm.current)
    with pytest.raises(GameError):
        env.run(env.engine.bk_submit(env.CHAT, other, jpeg()))
    with pytest.raises(GameError):
        env.run(env.engine.bk_submit(env.CHAT, g.cm.current, b"not a jpeg"))


def one_lap(env):
    for _ in range(len(env.game.cm.order)):
        draw_turn(env)


def test_carmeleon_drawings_are_posted_then_the_group_decides(env):
    g = start_cm(env)
    one_lap(env)
    assert len(env.io.photos) == 4 and g.cm.stage == "decide"
    assert any(b for m in env.io.sent for b in (m["buttons"] or []) if isinstance(b, list))


def test_carmeleon_majority_for_another_lap_then_straight_to_the_vote(env):
    g = start_cm(env)
    one_lap(env)
    for u in (1, 2, 3):
        cb(env, u, "cm:more")
    cb(env, 4, "cm:vote")
    assert g.cm.lap == 2 and g.cm.stage == "draw" and g.cm.pos == 0
    one_lap(env)
    assert g.cm.stage == "vote"                      # no second chance to ask for another lap


def test_carmeleon_no_majority_goes_to_the_vote_with_one_button_per_drawing(env):
    g = start_cm(env)
    one_lap(env)
    for u in (1, 2):
        cb(env, u, "cm:more")
    env.run(env.io.advance(config.CARMELEON_DECIDE_SECONDS))
    assert g.cm.stage == "vote" and len(g.cm.vote_msgs) == 4
    voting = [p for p in env.io.photos if p["buttons"]]
    assert len(voting) == 4 and all(p["buttons"][0][1].startswith("cb:cm:v:") for p in voting)


def votes(env, mapping):
    for voter, target in mapping.items():
        cb(env, voter, f"cm:v:{target}")


def to_vote(env):
    g = start_cm(env)
    one_lap(env)
    env.run(env.io.advance(config.CARMELEON_DECIDE_SECONDS))
    return g


def test_carmeleon_cannot_vote_for_yourself(env):
    g = to_vote(env)
    assert "stesso" in cb(env, 1, "cm:v:1") and 1 not in g.cm.votes


def test_carmeleon_unmasked_chameleon_that_misses_loses(env):
    g = to_vote(env)
    cham = g.cm.chameleon
    votes(env, {u: cham for u in g.players if u != cham} | {cham: next(u for u in g.players if u != cham)})
    assert g.cm.stage == "guess"
    wrong = next(i for i in range(len(g.cm.table)) if i != g.cm.key)
    assert "Solo" in cb(env, next(u for u in g.players if u != cham), f"cm:g:{wrong}")
    cb(env, cham, f"cm:g:{wrong}")
    assert env.game is None
    assert "non ha indovinato" in env.io.texts()[-1]
    rows = env.db.query("SELECT user_id, points FROM game_players")
    assert {u: p for u, p in rows}[cham] == 0 and all(p == 2 for u, p in rows if u != cham)


def test_carmeleon_unmasked_chameleon_that_guesses_wins_alone(env):
    g = to_vote(env)
    cham, key = g.cm.chameleon, g.cm.key
    votes(env, {u: cham for u in g.players if u != cham} | {cham: next(u for u in g.players if u != cham)})
    cb(env, cham, f"cm:g:{key}")
    rows = dict(env.db.query("SELECT user_id, points FROM game_players"))
    assert rows[cham] == 2 and all(p == 0 for u, p in rows.items() if u != cham)


def test_carmeleon_wrong_suspect_or_tie_gives_the_chameleon_three_points(env):
    g = to_vote(env)
    cham = g.cm.chameleon
    innocent = next(u for u in g.players if u != cham)
    votes(env, {u: innocent for u in g.players if u != innocent} | {innocent: cham})
    assert env.game is None
    rows = dict(env.db.query("SELECT user_id, points FROM game_players"))
    assert rows[cham] == 3
    assert "Chiave" in env.io.texts()[-1]


def test_carmeleon_tie_means_the_chameleon_wins(env):
    g = to_vote(env)
    a, b, c, d = list(g.players)
    votes(env, {a: b, b: a, c: b, d: a})
    assert env.game is None and "Pareggio" in env.io.texts()[-1]


def test_carmeleon_unanswered_vote_timer_still_closes_the_round(env):
    g = to_vote(env)
    env.run(env.io.advance(config.CARMELEON_VOTE_SECONDS))
    assert env.game is None and "Nessun voto" in env.io.texts()[-1]


def test_carmeleon_time_out_uses_the_draft_or_a_blank_drawing(env):
    g = start_cm(env)
    uid = g.cm.current
    env.engine.bk_draft(env.CHAT, uid, jpeg("red"))
    env.run(env.io.advance(g.draw_seconds + config.BROKEN_GRACE_SECONDS))
    assert len(g.cm.drawings) == 1 and g.cm.drawings[0]["jpeg"] == jpeg("red")
    assert g.cm.current != uid


def test_carmeleon_the_chameleon_leaving_ends_the_match(env):
    g = start_cm(env)
    cham = g.cm.chameleon
    env.run(env.engine.quit(env.CHAT, cham, "it"))
    assert env.game is None and "scappato" in env.io.texts()[-1]


def test_carmeleon_words_setting(env):
    env.db.set_setting(env.CHAT, "cmwords", "30")
    g = start_cm(env)
    assert len(g.cm.table) == 30 and all(sum(1 for e in g.cm.table if e.cat == c) == 10
                                         for c in {e.cat for e in g.cm.table})


# ================================================================ Code Stroke
def start_cs(env, n=4):
    return env.start_match(n, "it", "codestroke")


def clue(env, number=2):
    g = env.game
    spy = g.cs.spies[g.cs.team]
    env.run(env.engine.bk_submit(env.CHAT, spy, jpeg(), number))
    return spy


def cells(g, kind, team=None):
    return [i for i, k in enumerate(g.cs.key) if k == kind]


def test_codestroke_setup(env):
    g = start_cs(env, 5)
    cs = g.cs
    assert len(cs.grid) == 25 and len({e.word for e in cs.grid}) == 25
    assert [cs.key.count(k) for k in "BRNK"] == [9, 8, 7, 1]
    assert cs.team == "B"
    teams = list(cs.teams.values())
    assert teams.count("B") == 2 and teams.count("R") == 3       # the odd player goes to red, the team that starts second
    assert all(cs.teams[cs.spies[t]] == t for t in "BR")
    assert any("Blu" in m["text"] and "Rossa" in m["text"] for m in env.io.sent)


def test_codestroke_only_spies_see_the_key(env):
    g = start_cs(env)
    cs = g.cs
    spy_b, spy_r = cs.spies["B"], cs.spies["R"]
    mate = next(u for u in g.players if cs.teams[u] == "B" and u != spy_b)
    assert all(c["k"] for c in env.engine.web_state(env.CHAT, spy_b)["cs"]["grid"])
    assert all(c["k"] is None for c in env.engine.web_state(env.CHAT, mate)["cs"]["grid"])
    assert "bk" in env.engine.web_state(env.CHAT, spy_b) and "bk" not in env.engine.web_state(env.CHAT, spy_r)


def test_codestroke_clue_then_guesses_with_number_plus_one(env):
    g = start_cs(env)
    cs = g.cs
    clue(env, 2)
    assert cs.stage == "guess" and cs.guesses_left == 3 and env.io.photos
    mate = next(u for u in g.players if cs.teams[u] == "B" and u != cs.spies["B"])
    mine = [i for i in cells(g, "B")]
    assert env.run(env.engine.cs_pick(g, mate, mine[0])) is None
    assert cs.revealed[mine[0]] and cs.team == "B" and cs.guesses_left == 2
    assert env.run(env.engine.cs_pick(g, mate, mine[0])) is not None         # already revealed


def test_codestroke_rules_about_who_can_pick(env):
    g = start_cs(env)
    cs = g.cs
    spy = cs.spies["B"]
    mate = next(u for u in g.players if cs.teams[u] == "B" and u != spy)
    enemy = next(u for u in g.players if cs.teams[u] == "R")
    assert "indizio" in env.run(env.engine.cs_pick(g, mate, 0))             # before the clue
    clue(env)
    assert env.run(env.engine.cs_pick(g, spy, 0)) is not None
    assert env.run(env.engine.cs_pick(g, enemy, 0)) is not None
    assert env.run(env.engine.cs_pick(g, 999, 0)) is not None
    assert cb(env, mate, "cs:pass")                                          # must pick at least one first


def test_codestroke_wrong_word_ends_the_turn(env):
    g = start_cs(env)
    cs = g.cs
    clue(env)
    mate = next(u for u in g.players if cs.teams[u] == "B" and u != cs.spies["B"])
    env.run(env.engine.cs_pick(g, mate, cells(g, "N")[0]))
    assert cs.team == "R" and cs.stage == "clue"


def test_codestroke_passing_after_a_good_pick(env):
    g = start_cs(env)
    cs = g.cs
    clue(env)
    mate = next(u for u in g.players if cs.teams[u] == "B" and u != cs.spies["B"])
    cb(env, mate, f"cs:g:{cells(g, 'B')[0]}")
    cb(env, mate, "cs:pass")
    assert cs.team == "R"


def test_codestroke_assassin_loses_at_once(env):
    g = start_cs(env)
    cs = g.cs
    clue(env)
    mate = next(u for u in g.players if cs.teams[u] == "B" and u != cs.spies["B"])
    env.run(env.engine.cs_pick(g, mate, cells(g, "K")[0]))
    assert env.game is None and "Vince la squadra" in env.io.texts()[-1]
    rows = env.db.query("SELECT user_id, won FROM game_players")
    red = {u for u, t in cs.teams.items() if t == "R"}
    assert {u for u, w in rows if w} == red


def test_codestroke_finding_every_word_wins(env):
    g = start_cs(env)
    cs = g.cs
    clue(env, 9)
    mate = next(u for u in g.players if cs.teams[u] == "B" and u != cs.spies["B"])
    for i in cells(g, "B"):
        env.run(env.engine.cs_pick(g, mate, i))
        if env.game is None:
            break
    assert env.game is None and cs.winner == "B"


def test_codestroke_revealing_the_other_teams_last_word_gives_them_the_win(env):
    g = start_cs(env)
    cs = g.cs
    for i in cells(g, "R")[:-1]:
        cs.revealed[i] = True
    clue(env, 3)
    mate = next(u for u in g.players if cs.teams[u] == "B" and u != cs.spies["B"])
    env.run(env.engine.cs_pick(g, mate, cells(g, "R")[-1]))
    assert env.game is None and cs.winner == "R"


def test_codestroke_missing_clue_or_guesses_pass_the_turn(env):
    g = start_cs(env)
    cs = g.cs
    env.run(env.io.advance(g.draw_seconds + config.BROKEN_GRACE_SECONDS))
    assert cs.team == "R" and cs.stage == "clue"
    clue(env)
    env.run(env.io.advance(config.CODESTROKE_GUESS_SECONDS))
    assert cs.team == "B"


def test_codestroke_the_grid_in_the_chat_has_25_buttons(env):
    g = start_cs(env)
    grid = next(m for m in env.io.sent if m["buttons"] and isinstance(m["buttons"][0], list) and len(m["buttons"][0]) == 5)
    assert sum(len(r) for r in grid["buttons"][:5]) == 25
    assert all(b[1].startswith("cb:cs:g:") for r in grid["buttons"][:5] for b in r)


def test_codestroke_clue_number_is_validated(env):
    start_cs(env)
    spy = env.game.cs.spies["B"]
    with pytest.raises(GameError):
        env.run(env.engine.bk_submit(env.CHAT, spy, jpeg(), 0))
    with pytest.raises(GameError):
        env.run(env.engine.bk_submit(env.CHAT, spy, jpeg(), 12))
