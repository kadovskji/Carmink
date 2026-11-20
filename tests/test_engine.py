"""Whole-match scenarios driven through the Engine with a fake clock."""
import config
import words
from engine import GameError
from game import Phase, guess_points
import pytest


def word_of(env):
    return env.game.turn.word.word


# ---------------------------------------------------------------- lobby
def test_lobby_needs_three_players_and_ready_starts(env):
    e = env.engine
    env.run(e.new_game(env.CHAT, 1, "Ada", "it"))
    env.run(e.join(env.CHAT, 2, "Bob", "it"))
    env.run(e.ready(env.CHAT, 1, "it"))
    assert env.game.phase == Phase.LOBBY
    assert "almeno 3" in env.io.texts()[-1]
    env.run(e.join(env.CHAT, 3, "Cy", "it"))
    env.run(e.ready(env.CHAT, 2, "it"))
    assert env.game.phase == Phase.BREAK
    assert any("3 giocatori, 6 round" in t for t in env.io.texts())
    assert "Prossimo disegnatore" in env.io.texts()[-1]
    assert env.io.sent[-1]["buttons"][0][1].startswith("https://t.me/carminkgame/app?startapp=c1001")


def test_second_game_and_double_join_are_refused(env):
    e = env.engine
    env.run(e.new_game(env.CHAT, 1, "Ada", "it"))
    env.run(e.new_game(env.CHAT, 2, "Bob", "it"))
    assert "già una partita" in env.io.texts()[-1]
    env.run(e.join(env.CHAT, 1, "Ada", "it"))
    assert "già in partita" in env.io.texts()[-1]
    env.run(e.join(env.CHAT, 2, "Bob", "it"))
    env.run(e.join(env.CHAT, 3, "Cy", "it"))
    env.run(e.new_game(-2002, 3, "Cy", "it"))           # Cy is busy in the other group
    assert "già in una partita" in env.io.texts()[-1]


def test_lobby_expires_cancels_without_enough_players(env):
    env.run(env.engine.new_game(env.CHAT, 1, "Ada", "en"))
    env.run(env.io.advance(config.LOBBY_SECONDS))
    assert env.game is None
    assert "cancelled" in env.io.texts()[-1]


def test_lobby_expires_starts_with_enough_players(env):
    e = env.engine
    env.run(e.new_game(env.CHAT, 1, "Ada", "it"))
    for uid in (2, 3):
        env.run(e.join(env.CHAT, uid, f"P{uid}", "it"))
    env.run(env.io.advance(config.LOBBY_SECONDS))
    assert env.game.phase == Phase.BREAK


def test_wait_extends_the_lobby(env):
    e = env.engine
    env.run(e.new_game(env.CHAT, 1, "Ada", "it"))
    env.run(e.wait(env.CHAT, 1, "3,5", "it"))
    env.run(e.wait(env.CHAT, 1, "99", "it"))
    env.run(e.wait(env.CHAT, 1, "abc", "it"))
    env.run(env.io.advance(config.LOBBY_SECONDS + 100))
    assert env.game is not None and env.game.phase == Phase.LOBBY    # 3.5 minutes more
    env.run(env.io.advance(120))
    assert env.game is None


def test_stop_only_creator_or_admin(env):
    env.start_match(3)
    env.run(env.engine.stop(env.CHAT, 2, "it"))
    assert env.game is not None
    env.io.admins.add(2)
    env.run(env.engine.stop(env.CHAT, 2, "it"))
    assert env.game is None and not env.engine.user_game and not env.io.timers


# ---------------------------------------------------------------- one turn
def test_full_turn_guess_scores_and_next_drawer(env):
    g = env.start_match(3)
    t = env.to_choosing()
    drawer = t.drawer
    assert g.phase == Phase.CHOOSING and len(t.choices) == 3
    assert [c.diff for c in t.choices] == [1, 2, 3]
    env.engine.choose(env.CHAT, drawer, 1)
    assert g.phase == Phase.STARTING
    env.run(env.io.advance(3))
    env.run(env.engine.start_drawing(env.CHAT, drawer))
    assert g.phase == Phase.DRAWING
    word = word_of(env)
    guessers = [u for u in g.players if u != drawer]

    env.run(env.io.advance(10))
    env.guess(guessers[0], "boh", mid=11)                 # wrong: ignored
    assert g.scores[guessers[0]] == 0
    env.guess(guessers[0], word.upper() + "!", mid=12)    # right: message deleted, points given
    expected = guess_points(50, t.word.diff, 0)
    assert g.scores[guessers[0]] == expected and 12 in env.io.deleted
    env.run(env.io.advance(10))
    env.guess(guessers[1], word, mid=13)                  # last one: round ends at once
    second = guess_points(40, t.word.diff, 0)
    assert second < expected
    assert g.phase == Phase.BREAK and g.turn_no == 2
    assert g.scores[drawer] == round(config.DRAWER_PER_GUESS * 2 * config.DIFFICULTY_MULT[t.word.diff])
    text = env.io.texts()[-1]
    assert "Hanno indovinato tutti" in text and f"<b>{word}</b>" in text and "Classifica" in text
    assert "Prossimo disegnatore" in text


def test_time_up_without_guesses(env):
    g = env.start_match(3)
    t = env.to_drawing()
    env.run(env.io.advance(config.DRAW_SECONDS))
    assert "Tempo scaduto" in env.io.texts()[-1] and "Nessuno ha indovinato" in env.io.texts()[-1]
    assert g.scores[t.drawer] == 0 and g.phase == Phase.BREAK


def test_drawer_who_does_not_choose_is_skipped(env):
    g = env.start_match(3)
    t = env.to_choosing()
    env.run(env.io.advance(config.CHOOSE_SECONDS))
    assert "non ha scelto la parola" in env.io.texts()[-1]
    assert g.turn.drawer != t.drawer or g.turn_no == 2
    assert g.turn_no == 2 and g.phase == Phase.BREAK


def test_drawer_who_does_not_start_is_skipped(env):
    g = env.start_match(3)
    t = env.to_choosing()
    env.engine.choose(env.CHAT, t.drawer, 0)
    env.run(env.io.advance(config.START_SECONDS - 1))
    assert g.phase == Phase.STARTING
    env.run(env.io.advance(1))
    assert "non ha iniziato a disegnare" in env.io.texts()[-1] and g.turn_no == 2


def test_clock_starts_at_first_stroke_not_at_choice(env):
    g = env.start_match(3)
    t = env.to_choosing()
    env.engine.choose(env.CHAT, t.drawer, 0)
    env.run(env.io.advance(15))
    env.run(env.engine.start_drawing(env.CHAT, t.drawer))
    env.run(env.io.advance(config.DRAW_SECONDS - 1))
    assert g.phase == Phase.DRAWING
    env.run(env.io.advance(1))
    assert g.phase == Phase.BREAK


def test_late_timers_never_fire_into_the_next_phase(env):
    g = env.start_match(3)
    t = env.to_drawing()
    for u in g.players:
        if u != t.drawer:
            env.guess(u, word_of(env))
    assert g.phase == Phase.BREAK
    env.run(env.io.advance(config.DRAW_SECONDS))     # the old 60s timer must be dead
    assert sum("Tempo scaduto" in x for x in env.io.texts()) == 0


# ---------------------------------------------------------------- spoilers, close guesses
def test_spoilers_from_drawer_and_from_players_who_already_guessed_are_deleted(env):
    g = env.start_match(3)
    t = env.to_drawing()
    word = word_of(env)
    a, b = [u for u in g.players if u != t.drawer]
    env.guess(t.drawer, f"è un {word}", mid=21)
    env.guess(a, word, mid=22)
    env.guess(a, f"vi dico: {word}", mid=23)
    env.guess(b, "ciao a tutti", mid=24)
    assert env.io.deleted == [21, 22, 23]


def test_non_players_and_other_phases_are_ignored(env):
    g = env.start_match(3)
    env.to_choosing()
    env.guess(2, "qualcosa")
    env.engine.choose(env.CHAT, g.turn.drawer, 0)
    env.guess(99, g.turn.word.word)
    assert not env.io.deleted and all(v == 0 for v in g.scores.values())


def test_close_guess_gets_a_hint_twice_per_turn(env):
    g = env.start_match(3)
    t = env.to_choosing()
    longest = max(range(3), key=lambda i: len(words.compact(t.choices[i].word)))
    env.engine.choose(env.CHAT, t.drawer, longest)
    env.run(env.engine.start_drawing(env.CHAT, t.drawer))
    word = word_of(env)
    typo = word[:-1]
    assert words.is_close(t.word, typo)
    guesser = next(u for u in g.players if u != t.drawer)
    for i in range(4):
        env.guess(guesser, typo, mid=30 + i)
    replies = [m for m in env.io.sent if m["reply_to"]]
    assert len(replies) == config.CLOSE_NOTICES_PER_TURN


# ---------------------------------------------------------------- hints, skip
def test_hints_reduce_points_for_guessers_and_drawer(env):
    g = env.start_match(3)
    t = env.to_drawing()
    word = t.word
    mask = env.run(env.engine.hint(env.CHAT, t.drawer))
    assert mask.count("_") == len(words.letter_positions(word.word)) - 1
    assert "-20%" in env.io.texts()[-1]
    a, b = [u for u in g.players if u != t.drawer]
    env.guess(a, word.word)
    assert g.scores[a] == guess_points(60, word.diff, 1)
    env.guess(b, word.word)
    assert g.scores[t.drawer] == round(30 * 2 * config.DIFFICULTY_MULT[word.diff] * 0.8)


def test_hint_limit_and_permissions(env):
    g = env.start_match(3)
    t = env.to_drawing()
    limit = words.max_hints(t.word.word)
    for _ in range(limit):
        env.run(env.engine.hint(env.CHAT, t.drawer))
    with pytest.raises(GameError) as exc:
        env.run(env.engine.hint(env.CHAT, t.drawer))
    assert exc.value.code == "no_more_hints"
    other = next(u for u in g.players if u != t.drawer)
    with pytest.raises(GameError) as exc:
        env.run(env.engine.hint(env.CHAT, other))
    assert exc.value.code == "not_drawer"


def test_skip_while_choosing_loses_the_turn_and_while_drawing_ends_it(env):
    g = env.start_match(3)
    t = env.to_choosing()
    env.run(env.engine.skip(env.CHAT, t.drawer))
    assert "ha saltato il proprio turno" in env.io.texts()[-1] and g.turn_no == 2
    t = env.to_drawing()
    env.run(env.engine.skip(env.CHAT, t.drawer))
    assert "Turno concluso dal disegnatore" in env.io.texts()[-1] and g.turn_no == 3


# ---------------------------------------------------------------- canvas pictures
JPEG = b"\xff\xd8\xff\xe0" + b"x" * 50


def test_snapshot_validation(env):
    g = env.start_match(3)
    t = env.to_drawing()
    with pytest.raises(GameError) as exc:
        env.engine.snapshot(env.CHAT, t.drawer, b"not a jpeg")
    assert exc.value.code == "bad_image"
    with pytest.raises(GameError):
        env.engine.snapshot(env.CHAT, t.drawer, JPEG + b"0" * config.SNAPSHOT_MAX_BYTES)
    other = next(u for u in g.players if u != t.drawer)
    with pytest.raises(GameError) as exc:
        env.engine.snapshot(env.CHAT, other, JPEG)
    assert exc.value.code == "not_drawer"
    env.engine.snapshot(env.CHAT, t.drawer, JPEG)
    with pytest.raises(GameError) as exc:
        env.engine.snapshot(env.CHAT, t.drawer, JPEG)
    assert exc.value.code == "too_fast"


def test_picture_is_posted_once_then_edited_only_when_it_changes(env):
    g = env.start_match(3)
    t = env.to_drawing()
    env.engine.snapshot(env.CHAT, t.drawer, JPEG)
    env.run(env.io.advance(config.SNAPSHOT_FIRST_SECONDS))
    assert len(env.io.photos) == 1 and not env.io.edits
    env.run(env.io.advance(config.SNAPSHOT_EDIT_SECONDS))
    assert not env.io.edits                                    # nothing changed: no edit
    env.engine.snapshot(env.CHAT, t.drawer, JPEG + b"y")
    env.run(env.io.advance(config.SNAPSHOT_EDIT_SECONDS))
    assert len(env.io.edits) == 1 and env.io.edits[0]["id"] == env.io.photos[0]["id"]
    env.run(env.engine.hint(env.CHAT, t.drawer))
    env.run(env.io.advance(config.SNAPSHOT_EDIT_SECONDS))
    assert len(env.io.edits) == 2 and "<code>" in env.io.edits[1]["caption"]
    env.run(env.io.advance(config.DRAW_SECONDS))               # time up: final edit reveals the word
    assert f"<b>{t.word.word}</b>" in env.io.edits[-1]["caption"]


# ---------------------------------------------------------------- players coming and going
def test_whole_match_three_players_two_laps(env):
    g = env.start_match(3)
    drawers = []
    while env.game:
        t = env.to_drawing()
        drawers.append(t.drawer)
        for u in list(g.players):
            if u != t.drawer:
                env.guess(u, word_of(env))
    assert len(drawers) == 6
    assert sorted(drawers) == [1, 1, 2, 2, 3, 3]
    assert "Partita finita" in env.io.texts()[-1] and "Vince" in env.io.texts()[-1]
    stats = env.db.group_stats(env.CHAT)
    assert stats["games"] == 1 and sum(w for _, w in stats["wins"]) >= 1
    assert env.db.user_stats(1, env.CHAT)["drawn"] == 2
    assert not env.engine.games and not env.engine.user_game and not env.io.timers


def test_five_players_draw_once(env):
    g = env.start_match(5)
    assert g.total_turns == 5


def test_quit_in_lobby_and_by_drawer(env):
    g = env.start_match(4)
    t = env.to_choosing()
    env.run(env.engine.quit(env.CHAT, t.drawer, "it"))
    assert t.drawer not in g.players and "turno saltato" in env.io.texts()[-1]
    assert g.turn_no == 2
    env.run(env.engine.quit(env.CHAT, t.drawer, "it"))
    assert "Non sei in partita" in env.io.texts()[-1]


def test_drawer_quits_while_drawing_ends_turn_and_reveals_word(env):
    g = env.start_match(4)
    t = env.to_drawing()
    word = t.word.word
    env.run(env.engine.quit(env.CHAT, t.drawer, "it"))
    assert f"<b>{word}</b>" in env.io.texts()[-1] and g.turn_no == 2


def test_match_ends_when_too_few_players_remain(env):
    g = env.start_match(3)
    env.to_choosing()
    env.run(env.engine.quit(env.CHAT, 2, "it"))
    env.run(env.engine.quit(env.CHAT, 3, "it"))
    assert env.game is None
    assert any("Partita finita" in t for t in env.io.texts())


def test_last_missing_guesser_leaving_ends_the_turn(env):
    g = env.start_match(4)
    t = env.to_drawing()
    a, b, c = [u for u in g.players if u != t.drawer]
    env.guess(a, word_of(env))
    env.guess(b, word_of(env))
    assert g.phase == Phase.DRAWING
    env.run(env.engine.quit(env.CHAT, c, "it"))
    assert g.phase == Phase.BREAK


def test_late_joiner_guesses_now_and_draws_at_the_end(env):
    g = env.start_match(3)
    t = env.to_drawing()
    env.run(env.engine.join(env.CHAT, 9, "Late", "it"))
    assert 9 in g.players and g.queue[-1] == 9 and g.total_turns == 7
    env.guess(9, word_of(env))
    assert g.scores[9] > 0


def test_english_match_uses_english_words_and_texts(env):
    g = env.start_match(3, lang="en")
    t = env.to_choosing()
    en_words = {w.word for w in words.load("en")}
    assert all(c.word in en_words for c in t.choices)
    assert "Next drawer" in " ".join(env.io.texts())


def test_group_dictionary_words_join_the_pool(env):
    env.db.add_word(env.CHAT, "it", "supercalifragilistico", 3, 1)
    g = env.start_match(3)
    assert any(e.word == "supercalifragilistico" for e in g.pool)
    assert not any(e.word == "supercalifragilistico" for e in env.engine.words_for(-5, "it"))


# ---------------------------------------------------------------- Mini App view of the match
def test_web_state_hides_the_word_from_everyone_but_the_drawer(env):
    g = env.start_match(3)
    t = env.to_choosing()
    other = next(u for u in g.players if u != t.drawer)
    mine = env.engine.web_state(env.CHAT, t.drawer)
    theirs = env.engine.web_state(env.CHAT, other)
    assert mine["role"] == "drawer" and len(mine["choices"]) == 3 and "choices" not in theirs
    env.engine.choose(env.CHAT, t.drawer, 2)
    mine = env.engine.web_state(env.CHAT, t.drawer)
    theirs = env.engine.web_state(env.CHAT, other)
    assert mine["word"] == t.word.word and "word" not in theirs
    assert theirs["phase"] == "starting" and "mask" not in theirs
    env.run(env.engine.start_drawing(env.CHAT, t.drawer))
    env.run(env.engine.hint(env.CHAT, t.drawer))
    theirs = env.engine.web_state(env.CHAT, other)
    assert theirs["mask"].count("_") == len(words.letter_positions(t.word.word)) - 1
    assert 0 < theirs["ends_in"] <= config.DRAW_SECONDS
    assert env.engine.web_state(-777, 1)["phase"] == "none"


def test_bad_choice_and_wrong_phase_errors(env):
    g = env.start_match(3)
    t = env.to_choosing()
    with pytest.raises(GameError) as exc:
        env.engine.choose(env.CHAT, t.drawer, 7)
    assert exc.value.code == "bad_choice"
    with pytest.raises(GameError) as exc:
        env.run(env.engine.start_drawing(env.CHAT, t.drawer))
    assert exc.value.code == "wrong_phase"


def test_player_who_guessed_and_then_left_keeps_the_name_in_the_round_summary(env):
    g = env.start_match(4)
    t = env.to_drawing()
    a, b, c = [u for u in g.players if u != t.drawer]
    name_a = g.players[a]
    env.guess(a, word_of(env))
    env.run(env.engine.quit(env.CHAT, a, "it"))
    env.run(env.io.advance(config.DRAW_SECONDS))
    assert f"✅ {name_a} +" in " ".join(env.io.texts())


def test_old_database_gets_alts_column(tmp_path):
    import sqlite3
    from db import Database
    p = str(tmp_path / "old.db")
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE custom_words (chat_id INTEGER NOT NULL, lang TEXT NOT NULL, word TEXT NOT NULL, "
                "diff INTEGER NOT NULL DEFAULT 2, added_by INTEGER, PRIMARY KEY (chat_id, lang, word))")
    con.execute("INSERT INTO custom_words VALUES (1, 'it', 'zattera', 2, 5)")
    con.commit(); con.close()
    db = Database(p)
    assert [(e.word, e.alts) for e in db.custom_entries(1, "it")] == [("zattera", ())]
    assert db.add_word(1, "it", "barca", 1, 5, ("nave",))
