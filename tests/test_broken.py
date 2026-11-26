"""Broken Canva: sign-up rules, passes, assignments, timeouts, the Mini App endpoints and the GIFs."""
import io

import pytest
from PIL import Image

import config
import gifmaker
from conftest import Env
from engine import GameError
from game import Phase, broken_steps


@pytest.fixture(autouse=True)
def no_gif_gap(monkeypatch):
    monkeypatch.setattr(config, "BROKEN_GIF_GAP", 0.0)
    monkeypatch.setattr(config, "SNAPSHOT_MIN_INTERVAL", 0.0)


def jpeg(color="white") -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (80, 60), color).save(b, "JPEG")
    return b.getvalue()


def start_broken(env: Env, n: int = 4, lang: str = "it", cycles: int | str = 2):
    """Most tests use 2 cycles (3 passes); the default is one cycle per player."""
    for uid in range(1, n + 1):
        env.db.add_dm(uid)
    env.db.set_setting(env.CHAT, "cycles", str(cycles))
    return env.start_match(n, lang, "broken")


def write_all(env: Env, uids=None, prefix="frase"):
    for uid in uids or list(env.game.broken.order):
        env.run(env.engine.on_private(uid, f"{prefix} {uid}"))


def draw_all(env: Env, uids=None):
    for uid in uids or list(env.game.players):
        env.run(env.engine.bk_submit(env.CHAT, uid, jpeg()))


def play_to_the_end(env: Env):
    g = env.game
    write_all(env)
    while env.game is not None:
        if g.broken.kind == "draw":
            draw_all(env)
        else:
            write_all(env, prefix="descr")


# ---------------------------------------------------------------- rules
@pytest.mark.parametrize("n,steps", [(4, 7), (5, 9), (6, 9), (12, 9)])
def test_default_is_one_cycle_per_player_at_most_5(n, steps):
    assert broken_steps(n) == steps and steps % 2 == 1


@pytest.mark.parametrize("cycles,steps", [(1, 1), (2, 3), (3, 5), (5, 9)])
def test_a_cycle_is_a_description_and_its_drawing(cycles, steps):
    assert broken_steps(6, cycles) == steps          # the phrase counts as the first description


def test_cycles_setting_changes_the_length_of_the_match(env):
    g = start_broken(env, 5, cycles=3)
    write_all(env)
    assert g.broken.steps == 5
    g2 = Env()
    for u in range(1, 5):
        g2.db.add_dm(u)
    g2.start_match(4, "it", "broken")                 # auto: one per player
    assert g2.game.cycles is None
    write_all(g2)
    assert g2.game.broken.steps == 7
    assert not env.db.set_setting(env.CHAT, "cycles", "6") and env.db.set_setting(env.CHAT, "cycles", "5")


# ---------------------------------------------------------------- sign-up
def test_broken_needs_the_bot_started_in_private(env):
    e = env.engine
    env.run(e.new_game(env.CHAT, 1, "Ada", "it", "broken"))
    assert env.game is None
    last = env.io.sent[-1]
    assert "Avvia il bot" in last["buttons"][0][0] and f"start=j{abs(env.CHAT)}" in last["buttons"][0][1]
    env.db.add_dm(1)
    env.run(e.new_game(env.CHAT, 1, "Ada", "it", "broken"))
    assert env.game.mode == "broken"
    env.run(e.join(env.CHAT, 2, "Bea", "it"))              # Bea never started the bot
    assert 2 not in env.game.players and env.io.sent[-1]["buttons"]
    env.db.add_dm(2)
    env.run(e.join(env.CHAT, 2, "Bea", "it"))
    assert 2 in env.game.players


def test_broken_needs_four_players(env):
    e = env.engine
    for uid in (1, 2, 3):
        env.db.add_dm(uid)
    env.run(e.new_game(env.CHAT, 1, "Ada", "it", "broken"))
    for uid in (2, 3):
        env.run(e.join(env.CHAT, uid, f"P{uid}", "it"))
    env.run(e.ready(env.CHAT, 1, "it"))
    assert env.game.phase == Phase.LOBBY and "almeno 4" in env.io.texts()[-1]
    env.run(env.io.advance(config.LOBBY_SECONDS))              # sign-ups expire with 3 players
    assert env.game is None and "4" in env.io.texts()[-1]


def test_no_joining_once_started(env):
    start_broken(env)
    env.run(env.engine.join(env.CHAT, 9, "Late", "it"))
    assert 9 not in env.game.players and "Broken Canva" in env.io.texts()[-1]


def test_a_player_we_cannot_write_to_is_left_out(env):
    for uid in range(1, 6):
        env.db.add_dm(uid)
    env.io.dm_fail.add(5)
    env.start_match(5, "it", "broken")
    assert sorted(env.game.broken.order) == [1, 2, 3, 4]
    assert 5 not in env.game.players and "P5" in "".join(env.io.texts())


def test_game_cancelled_if_too_many_cannot_be_reached(env):
    for uid in range(1, 5):
        env.db.add_dm(uid)
    env.io.dm_fail.add(4)
    env.start_match(4, "it", "broken")
    assert env.game is None and "annullata" in env.io.texts()[-1]


# ---------------------------------------------------------------- phrases
def test_the_game_starts_when_everybody_has_written(env):
    g = start_broken(env)
    assert g.phase == Phase.WRITING and len(env.io.dms) == 4
    write_all(env, [1, 2, 3])
    assert g.phase == Phase.WRITING
    assert "✅" in env.io.text_edits[-1]["text"] and "⏳" in env.io.text_edits[-1]["text"]
    env.run(env.engine.on_private(4, "x" * (config.BROKEN_TEXT_MAX + 1)))
    assert g.phase == Phase.WRITING and "Troppo lunga" in env.io.dms[-1]["text"]
    env.run(env.engine.on_private(4, "  una   frase\nbuffa "))
    assert g.phase == Phase.STEP and g.broken.step == 1
    assert [c[0]["text"] for c in g.broken.chains if c[0]["author"] == 4] == ["una frase buffa"]


def test_a_phrase_can_be_replaced_before_the_pass_closes(env):
    g = start_broken(env)
    env.run(env.engine.on_private(1, "prima"))
    env.run(env.engine.on_private(1, "seconda"))
    assert g.broken.inbox[1]["text"] == "seconda" and "Sostituita" in env.io.dms[-1]["text"]


def test_silent_players_are_dropped_when_the_time_is_up(env):
    g = start_broken(env, 5)
    write_all(env, [1, 2, 3, 4])
    env.run(env.io.advance(config.BROKEN_PHRASE_SECONDS))
    assert 5 not in g.players and g.phase == Phase.STEP and len(g.broken.order) == 4
    assert "P5" in "".join(env.io.texts())


def test_game_cancelled_if_too_few_wrote(env):
    start_broken(env)
    write_all(env, [1, 2, 3])
    env.run(env.io.advance(config.BROKEN_PHRASE_SECONDS))
    assert env.game is None and "annullata" in env.io.texts()[-1]


def test_private_text_without_a_game_is_ignored(env):
    assert env.run(env.engine.on_private(42, "ciao")) is False


# ---------------------------------------------------------------- passes
@pytest.mark.parametrize("n", [4, 5, 6, 8, 9])
def test_nobody_ever_meets_the_chain_of_their_own_phrase(env, n):
    g = start_broken(env, n)
    write_all(env)
    bk = g.broken
    seen: dict[int, set] = {u: set() for u in bk.order}     # chains (by author of the phrase) each user handles
    while env.game is not None:
        for u, item in bk.given.items():
            origin = next(c[0]["author"] for c in bk.chains if any(item is x for x in c))
            seen[u].add(origin)
            assert origin != u
        if bk.kind == "draw":
            draw_all(env)
        else:
            write_all(env, prefix="descr")
    assert all(len(v) == bk.steps for v in seen.values())    # a different chain at every pass


def test_passes_alternate_and_end_with_a_drawing(env):
    g = start_broken(env, 4)
    write_all(env)
    kinds = []
    bk = g.broken
    while env.game is not None:
        kinds.append(bk.kind)
        draw_all(env) if bk.kind == "draw" else write_all(env, prefix="d")
    assert kinds == ["draw", "text", "draw"]
    assert len(env.io.animations) == 4
    for a in env.io.animations:
        im = Image.open(io.BytesIO(a["data"]))
        assert a["data"][:6] == b"GIF89a" and im.n_frames == 2      # (phrase + drawing), (description + drawing)


def test_the_dms_follow_the_pass(env):
    g = start_broken(env, 4)
    write_all(env)
    drawing = [d for d in env.io.dms if "Passo 1/3" in d["text"]]
    assert len(drawing) == 4 and all(d["buttons"] for d in drawing)
    prompts = {d["text"].split("«")[1].rstrip("»") for d in drawing}
    assert prompts == {f"frase {u}" for u in range(1, 5)}
    draw_all(env)
    assert len(env.io.dm_photos) == 4 and "Passo 2/3" in env.io.dm_photos[0]["caption"]
    assert g.deadline - env.io.now() == config.BROKEN_DESCRIBE_SECONDS


def test_a_pass_closes_as_soon_as_everybody_has_answered(env):
    g = start_broken(env)
    write_all(env)
    assert g.broken.step == 1
    draw_all(env, [1, 2, 3])
    assert g.broken.step == 1
    draw_all(env, [4])
    assert g.broken.step == 2 and g.broken.kind == "text"


def test_missing_drawings_use_the_last_draft_or_a_blank_canvas(env):
    g = start_broken(env)
    write_all(env)
    env.engine.bk_draft(env.CHAT, 1, jpeg("red"))
    draw_all(env, [2, 3])
    env.run(env.io.advance(g.draw_seconds + config.BROKEN_GRACE_SECONDS))
    assert g.broken.step == 2
    items = [c[1] for c in g.broken.chains]
    by_author = {i["author"]: i for i in items}
    assert by_author[1]["jpeg"] == jpeg("red") and by_author[4]["jpeg"] == gifmaker.BLANK_JPEG


def test_missing_descriptions_become_dots(env):
    g = start_broken(env)
    write_all(env)
    draw_all(env)
    write_all(env, [1, 2])
    env.run(env.io.advance(config.BROKEN_DESCRIBE_SECONDS))
    texts = sorted(c[2]["text"] for c in g.broken.chains)
    assert texts.count("…") == 2 and g.broken.step == 3


def test_a_player_who_cannot_be_reached_hands_in_dots(env):
    g = start_broken(env)
    write_all(env)
    env.io.dm_fail.add(3)
    draw_all(env)
    assert 3 in g.broken.inbox and g.broken.inbox[3]["text"] == "…"


def test_texts_are_refused_during_a_drawing_pass_and_drawings_during_a_text_pass(env):
    g = start_broken(env)
    write_all(env)
    env.run(env.engine.on_private(1, "ciao"))
    assert "Ora si disegna" in env.io.dms[-1]["text"] and 1 not in g.broken.inbox
    draw_all(env)
    with pytest.raises(GameError) as exc:
        env.run(env.engine.bk_submit(env.CHAT, 1, jpeg()))
    assert exc.value.code == "wrong_phase"


# ---------------------------------------------------------------- leaving
def test_leaving_midway_gives_blanks_and_the_game_goes_on(env):
    g = start_broken(env, 5)
    write_all(env)
    env.run(env.engine.quit(env.CHAT, 5, "it"))
    draw_all(env)                                       # the four who are left
    assert g.broken.step == 2
    blank = [c[1] for c in g.broken.chains if c[1]["author"] == 5]       # 5 left: an empty canvas
    assert len(blank) == 1 and blank[0]["jpeg"] == gifmaker.BLANK_JPEG
    while env.game is not None:                                       # the match still reaches the end
        draw_all(env) if g.broken.kind == "draw" else write_all(env, [u for u in g.players], "d")
    assert len(env.io.animations) == 5


def test_the_game_ends_when_too_few_are_left(env):
    start_broken(env, 4)
    write_all(env)
    for uid in (2, 3, 4):
        env.run(env.engine.quit(env.CHAT, uid, "it"))
    assert env.game is None and any("pochi giocatori" in t for t in env.io.texts())


def test_stop_cancels_everything(env):
    start_broken(env)
    env.run(env.engine.stop(env.CHAT, 1, "it"))
    assert env.game is None and not env.engine.user_game


# ---------------------------------------------------------------- the end
def test_stats_count_the_game_but_give_no_points_or_wins(env):
    start_broken(env)
    play_to_the_end(env)
    s = env.db.group_stats(env.CHAT)
    assert s["games"] == 1 and not any(v for _, v in s["wins"]) and not any(v for _, v in s["points"])
    u = env.db.user_stats(1)
    assert u["games"] == 1 and u["wins"] == 0 and u["points"] == 0


def test_a_new_game_can_start_after_the_recap(env):
    start_broken(env)
    play_to_the_end(env)
    assert not env.engine.user_game and env.CHAT not in env.engine.games


def test_recap_falls_back_to_text_without_pillow(env, monkeypatch):
    monkeypatch.setattr(gifmaker, "available", lambda: False)
    start_broken(env)
    play_to_the_end(env)
    assert not env.io.animations
    recap = [t for t in env.io.texts() if "Catena" in t]
    assert len(recap) == 4 and "(disegno)" in recap[0]


def test_an_undecodable_drawing_does_not_break_the_gif(env):
    g = start_broken(env)
    write_all(env)
    for uid in g.players:
        env.run(env.engine.bk_submit(env.CHAT, uid, b"\xff\xd8\xffgarbage"))
    write_all(env, prefix="d")
    draw_all(env)
    assert len(env.io.animations) == 4


# ---------------------------------------------------------------- Mini App
def test_web_state_for_broken(env):
    g = start_broken(env)
    st = env.engine.web_state(env.CHAT, 1)
    assert st["mode"] == "broken" and st["phase"] == "writing" and st["bk"]["kind"] == "text"
    write_all(env)
    st = env.engine.web_state(env.CHAT, 1)
    assert st["phase"] == "step" and st["bk"]["kind"] == "draw" and st["bk"]["prompt"].startswith("frase")
    assert st["bk"]["active"] and not st["bk"]["done"] and 0 < st["ends_in"] <= g.draw_seconds
    env.run(env.engine.bk_submit(env.CHAT, 1, jpeg()))
    assert env.engine.web_state(env.CHAT, 1)["bk"]["done"] is True
    assert "prompt" not in env.engine.web_state(env.CHAT, 99)["bk"]
    assert env.engine.web_state(env.CHAT, 99)["bk"]["active"] is False


def test_submit_validation(env):
    start_broken(env)
    write_all(env)
    for bad, code in ((b"nope", "bad_image"), (b"\xff\xd8\xff" + b"0" * config.BROKEN_JPEG_MAX, "bad_image")):
        with pytest.raises(GameError) as exc:
            env.run(env.engine.bk_submit(env.CHAT, 1, bad))
        assert exc.value.code == code
    with pytest.raises(GameError) as exc:
        env.run(env.engine.bk_submit(env.CHAT, 99, jpeg()))
    assert exc.value.code == "not_player"
    env.run(env.engine.bk_submit(env.CHAT, 1, jpeg()))
    with pytest.raises(GameError) as exc:
        env.run(env.engine.bk_submit(env.CHAT, 1, jpeg()))
    assert exc.value.code == "already_done"


# ---------------------------------------------------------------- the pictures
def test_gif_of_a_chain_with_long_text_and_wide_characters():
    items = [{"kind": "text", "name": "Ada", "text": "parola " * 17},
             {"kind": "draw", "name": "Bea", "jpeg": jpeg("blue")},
             {"kind": "text", "name": "Zoë", "text": "Ünïcödé — ok"},
             {"kind": "draw", "name": "Dan", "jpeg": None}]
    data = gifmaker.make_gif(items, {"start": "Phrase by {name}", "draw": "Drawing by {name}",
                                     "describe": "{name} wrote"})
    im = Image.open(io.BytesIO(data))
    assert im.n_frames == 2 and im.size == gifmaker.SIZE      # one frame per phrase + drawing pair
