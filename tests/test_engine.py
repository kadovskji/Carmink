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
    env.guess(guessers[0], word.upper() + "!", mid=12)    # right: points given
    expected = guess_points(config.DRAW_SECONDS - 10, t.word.diff, 0)
    assert g.scores[guessers[0]] == expected
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
    env.chat(t.drawer, f"è un {word}", mid=21)
    env.guess(a, word, mid=22)                           # typed in the Mini App: nothing to delete
    env.chat(a, f"vi dico: {word}", mid=23)
    env.chat(b, "ciao a tutti", mid=24)
    assert env.io.deleted == [21, 23]


def test_non_players_and_other_phases_are_ignored(env):
    g = env.start_match(3)
    env.to_choosing()
    env.guess(2, "qualcosa")
    env.engine.choose(env.CHAT, g.turn.drawer, 0)
    env.guess(99, g.turn.word.word)
    assert not env.io.deleted and all(v == 0 for v in g.scores.values())


def test_close_guess_gets_a_hint_twice_per_turn(env):
    g = env.start_match(3, mode="speedrun")
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
    assert g.scores[a] == guess_points(config.DRAW_SECONDS, word.diff, 1)
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
    env.run(env.io.advance(config.DRAW_SECONDS))               # time up: waiting for the final canvas
    env.run(env.io.advance(config.FINAL_SNAPSHOT_WAIT))        # (it never came: the last one is used)
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


# ---------------------------------------------------------------- speedrun
def test_speedrun_first_correct_guess_wins_the_round(env):
    g = env.start_match(4, mode="speedrun")
    t = env.to_drawing()
    word = t.word
    a, b, _ = [u for u in g.players if u != t.drawer]
    env.run(env.io.advance(15))
    env.guess(a, "boh", mid=1)
    assert g.phase == Phase.DRAWING
    env.guess(a, word.word, mid=2)
    assert 2 in env.io.deleted and g.phase == Phase.BREAK
    assert g.scores[a] == guess_points(config.DRAW_SECONDS - 15, word.diff, 0)
    d = g.scores[t.drawer]
    assert 0 < d <= config.DRAWER_SPEEDRUN_MAX
    assert "Round vinto" in "\n".join(env.io.texts())
    env.guess(b, word.word, mid=3)                      # too late: the turn is over
    assert g.scores[b] == 0


def test_speedrun_nobody_guesses_means_no_points(env):
    g = env.start_match(3, mode="speedrun")
    t = env.to_drawing()
    env.run(env.io.advance(config.DRAW_SECONDS))
    assert all(p == 0 for p in g.scores.values())


def test_speedrun_drawer_points_rule():
    from game import speedrun_drawer_points
    assert speedrun_drawer_points(config.DRAW_SECONDS, 0) == config.DRAWER_SPEEDRUN_MAX
    assert speedrun_drawer_points(0, 0) == round(config.DRAWER_SPEEDRUN_MAX * config.GUESS_MIN_SHARE)
    assert speedrun_drawer_points(config.DRAW_SECONDS, 2) == round(config.DRAWER_SPEEDRUN_MAX * 0.6)
    assert speedrun_drawer_points(-5, 3) >= 1


def test_old_database_gets_the_latejoin_column(tmp_path):
    import sqlite3
    from db import Database
    p = str(tmp_path / "old2.db")
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE chat_settings (chat_id INTEGER PRIMARY KEY, lang TEXT NOT NULL DEFAULT 'it', "
                "words TEXT NOT NULL DEFAULT 'admins')")
    con.execute("INSERT INTO chat_settings VALUES (1, 'en', 'everyone')")
    con.commit(); con.close()
    db = Database(p)
    assert db.get_settings(1) == {"lang": "en", "words": "everyone", "latejoin": "on", "drawtime": "auto"}
    assert db.set_setting(1, "latejoin", "off") and db.get_settings(1)["latejoin"] == "off"


# ---------------------------------------------------------------- classic mode
def test_classic_everybody_keeps_guessing_and_chat_messages_do_not_count(env):
    g = env.start_match(4)                                  # classic
    t = env.to_drawing()
    word = t.word
    a, b, c = [u for u in g.players if u != t.drawer]
    env.chat(a, word.word, mid=1)                           # typed in the chat: deleted, not counted
    assert 1 in env.io.deleted and g.scores[a] == 0
    assert "non vale" in env.io.texts()[-1]
    env.chat(a, word.word, mid=2)                           # the notice is sent once per turn
    assert sum("non vale" in m for m in env.io.texts()) == 1
    r = env.guess(a, word.word)
    assert r["result"] == "right" and g.phase == Phase.DRAWING        # the others may go on
    r = env.guess(b, word.word)
    assert r["result"] == "right" and g.phase == Phase.DRAWING
    assert env.guess(a, word.word) == "already_guessed"
    env.guess(c, word.word)
    assert g.phase == Phase.BREAK and set(t.guessed) == {a, b, c}


def test_classic_attempts_are_public_but_the_answer_never_is(env):
    g = env.start_match(3)
    t = env.to_drawing()
    word = t.word
    a, b = [u for u in g.players if u != t.drawer]
    assert env.guess(a, "boh")["result"] == "wrong"
    assert env.guess(a, f"credo sia un {word.word}")["result"] == "wrong"
    assert env.guess(b, word.word.upper())["result"] == "right"
    shown = env.engine.live(env.CHAT, g.turn_no, 0, 0)["attempts"]
    assert shown[0] == {"u": g.players[a], "t": "boh", "r": False}
    assert shown[1]["t"] == "🙈"
    assert shown[-1]["r"] is True and shown[-1]["t"] is None
    assert all(word.word not in str(x) for x in shown)


def test_classic_guess_rules(env, monkeypatch):
    g = env.start_match(3)
    t = env.to_choosing()
    a, _ = [u for u in g.players if u != t.drawer]
    assert env.guess(a, "x") == "wrong_phase"
    env.engine.choose(env.CHAT, t.drawer, 0)
    env.run(env.engine.start_drawing(env.CHAT, t.drawer))
    assert env.guess(t.drawer, "x") == "is_drawer"
    assert env.guess(99, "x") == "not_player"
    assert env.guess(a, "   ") == "bad_request"
    monkeypatch.setattr(config, "GUESS_MIN_INTERVAL", 1.0)
    assert env.guess(a, "uno")["result"] == "wrong"
    assert env.guess(a, "due") == "too_fast"
    env.run(env.io.advance(1.1))
    assert env.guess(a, "tre")["result"] == "wrong"
    assert len(env.engine.live(env.CHAT, g.turn_no, 0, 0)["attempts"]) == 2


def test_speedrun_rejects_mini_app_guesses(env):
    g = env.start_match(3, mode="speedrun")
    env.to_drawing()
    a = next(u for u in g.players if u != g.turn.drawer)
    assert env.guess(a, "x") is None                         # goes through the chat instead
    with pytest.raises(GameError):
        env.run(env.engine.web_guess(env.CHAT, a, "x"))


def test_classic_points_use_the_same_time_curve(env):
    g = env.start_match(3)
    t = env.to_drawing()
    a, _ = [u for u in g.players if u != t.drawer]
    env.run(env.io.advance(30))
    r = env.guess(a, t.word.word)
    assert r["pts"] == guess_points(config.DRAW_SECONDS - 30, t.word.diff, 0)


# ---------------------------------------------------------------- live drawing events
PEN = {"k": "s", "c": "#ff0000", "w": 7, "p": [[10, 10]]}


def test_events_are_stored_once_and_served_incrementally(env):
    g = env.start_match(3)
    t = env.to_drawing()
    e = env.engine
    batch = [{"e": "begin", "op": PEN}, {"e": "pt", "p": [[20, 20], [30, 30]]}, {"e": "end"}]
    assert e.post_events(env.CHAT, t.drawer, 0, batch) == 3
    assert e.post_events(env.CHAT, t.drawer, 0, batch) == 3                      # a retry changes nothing
    assert e.post_events(env.CHAT, t.drawer, 2, batch[2:] + [{"e": "undo"}]) == 4  # partly known batch
    with pytest.raises(GameError):
        e.post_events(env.CHAT, t.drawer, 9, [])                                  # a hole in the stream
    with pytest.raises(GameError):
        e.post_events(env.CHAT, 3 if t.drawer != 3 else 2, 0, [])                 # not the drawer
    live = e.live(env.CHAT, g.turn_no, 0, 0)
    assert live["turn"] == g.turn_no and len(live["events"]) == 4 and live["ev"] == 0
    assert [x["e"] for x in e.live(env.CHAT, g.turn_no, 3, 0)["events"]] == ["undo"]
    assert e.live(env.CHAT, g.turn_no - 1, 3, 5)["ev"] == 0                       # other turn: start over


def test_events_are_validated_and_capped(env, monkeypatch):
    g = env.start_match(3)
    t = env.to_drawing()
    e = env.engine
    bad = [[{"e": "nope"}], [{"e": "begin", "op": {"k": "s", "c": "red", "w": 5, "p": [[1, 1]]}}],
           [{"e": "pt", "p": [["a", 1]]}], "text", [{"e": "pt", "p": []}]]
    for events in bad:
        with pytest.raises(GameError):
            e.post_events(env.CHAT, t.drawer, 0, events)
    clamped = [{"e": "begin", "op": {"k": "s", "c": "#00ff00", "w": 5, "p": [[-50, 9999]], "x": "junk"}}]
    e.post_events(env.CHAT, t.drawer, 0, clamped)
    assert t.events[0]["op"] == {"k": "s", "c": "#00ff00", "w": 5.0, "p": [[0.0, 600.0]]}
    monkeypatch.setattr(config, "EVENTS_MAX", 3)
    with pytest.raises(GameError):
        e.post_events(env.CHAT, t.drawer, 1, [{"e": "undo"}] * 3)


def test_events_only_while_drawing(env):
    env.start_match(3)
    t = env.to_choosing()
    with pytest.raises(GameError):
        env.engine.post_events(env.CHAT, t.drawer, 0, [])


def test_classic_close_attempt_is_reported_to_the_guesser_only(env):
    g = env.start_match(3)
    t = env.to_choosing()
    longest = max(range(3), key=lambda i: len(words.compact(t.choices[i].word)))
    env.engine.choose(env.CHAT, t.drawer, longest)
    env.run(env.engine.start_drawing(env.CHAT, t.drawer))
    a = next(u for u in g.players if u != t.drawer)
    r = env.guess(a, t.word.word[:-1])
    assert r["result"] == "close"
    assert env.engine.live(env.CHAT, g.turn_no, 0, 0)["attempts"][0]["r"] is False   # public entry is a plain miss


# ---------------------------------------------------------------- the finished canvas
def _drawn_turn(env, mode="classic", n=3, photo_first=True):
    g = env.start_match(n, mode=mode)
    t = env.to_drawing()
    env.engine.post_events(env.CHAT, t.drawer, 0, [{"e": "op", "op": {"k": "x"}}])
    if photo_first:
        env.engine.snapshot(env.CHAT, t.drawer, JPEG)
        env.run(env.io.advance(config.SNAPSHOT_FIRST_SECONDS))
    return g, t


def test_final_canvas_replaces_the_picture_when_the_round_ends(env):
    g, t = _drawn_turn(env)
    env.run(env.engine.skip(env.CHAT, t.drawer))
    assert g.phase == Phase.BREAK and t.final_open and not env.io.edits
    assert env.engine.web_state(env.CHAT, t.drawer)["final"] is True
    assert "final" not in env.engine.web_state(env.CHAT, next(u for u in g.players if u != t.drawer))
    env.run(env.engine.final_snapshot(env.CHAT, t.drawer, JPEG + b"final"))
    assert not t.final_open and env.io.edits[-1]["jpeg"] == JPEG + b"final"
    assert f"<b>{t.word.word}</b>" in env.io.edits[-1]["caption"]
    env.run(env.io.advance(config.BREAK_SECONDS))              # and the match goes on
    assert g.turn is not t


def test_final_picture_is_posted_even_if_none_was_shown_before(env):
    g, t = _drawn_turn(env, mode="speedrun", photo_first=False)
    env.run(env.engine.skip(env.CHAT, t.drawer))
    env.run(env.engine.final_snapshot(env.CHAT, t.drawer, JPEG))
    assert len(env.io.photos) == 1 and f"<b>{t.word.word}</b>" in env.io.photos[0]["caption"]


def test_without_the_final_canvas_the_round_moves_on_after_a_moment(env):
    g, t = _drawn_turn(env, photo_first=False)
    env.engine.snapshot(env.CHAT, t.drawer, JPEG + b"last")
    env.run(env.engine.skip(env.CHAT, t.drawer))
    assert t.final_open
    env.run(env.io.advance(config.FINAL_SNAPSHOT_WAIT))
    assert not t.final_open and env.io.photos[-1]["jpeg"] == JPEG + b"last"


def test_final_canvas_is_only_accepted_from_the_drawer_while_waiting(env):
    g, t = _drawn_turn(env)
    with pytest.raises(GameError) as exc:
        env.run(env.engine.final_snapshot(env.CHAT, t.drawer, JPEG))     # round still running
    assert exc.value.code == "wrong_phase"
    env.run(env.engine.skip(env.CHAT, t.drawer))
    other = next(u for u in g.players if u != t.drawer)
    for uid, data, code in ((other, JPEG, "not_drawer"), (t.drawer, b"nope", "bad_image")):
        with pytest.raises(GameError) as exc:
            env.run(env.engine.final_snapshot(env.CHAT, uid, data))
        assert exc.value.code == code
    assert t.final_open


def test_no_wait_when_the_drawer_left(env):
    g, t = _drawn_turn(env)
    env.run(env.engine.quit(env.CHAT, t.drawer, "it"))
    assert not t.final_open


# ---------------------------------------------------------------- drawing time (/settings)
@pytest.mark.parametrize("mode,secs", [("speedrun", 120), ("classic", 120), ("broken", 180)])
def test_auto_drawing_time_depends_on_the_mode(env, mode, secs):
    for uid in range(1, 5):
        env.db.add_dm(uid)
    assert env.start_match(4, mode=mode).draw_seconds == secs


@pytest.mark.parametrize("value", [60, 90, 120, 180, 240, 300])
def test_chosen_drawing_time_is_used_by_the_clock_and_the_points(env, value):
    env.db.set_setting(env.CHAT, "drawtime", str(value))
    g = env.start_match(3, mode="classic")
    assert g.draw_seconds == value
    t = env.to_drawing()
    assert g.deadline - env.io.now() == value
    guesser = next(u for u in g.players if u != t.drawer)
    env.run(env.io.advance(value / 2))
    env.guess(guesser, t.word.word)
    half = guess_points(value / 2, t.word.diff, 0, value)
    assert t.guessed[guesser] == half and half == guess_points(45, t.word.diff, 0, 90)
    env.run(env.io.advance(value))                              # the round ends at the chosen time
    assert g.phase != Phase.DRAWING


def test_drawing_time_setting_rejects_other_values(env):
    assert env.db.get_settings(env.CHAT)["drawtime"] == "auto"
    assert not env.db.set_setting(env.CHAT, "drawtime", "45")
    assert env.db.set_setting(env.CHAT, "drawtime", "240") and env.db.set_setting(env.CHAT, "drawtime", "auto")


def test_broken_canva_uses_the_chosen_time_for_drawings_only(env):
    for uid in range(1, 5):
        env.db.add_dm(uid)
    env.db.set_setting(env.CHAT, "drawtime", "300")
    g = env.start_match(4, mode="broken")
    for uid in list(g.broken.order):
        env.run(env.engine.on_private(uid, f"frase {uid}"))
    assert g.deadline - env.io.now() == 300                     # drawing pass
    assert "5 minuti" in env.io.dms[-1]["text"]


def test_a_missing_bot_admin_right_is_pointed_out_for_speedrun_and_classic(env):
    env.io.bot_can_delete = False
    env.run(env.engine.new_game(env.CHAT, 1, "Ada", "it", "classic"))
    last = env.io.sent[-1]
    assert "amministratore" in last["text"] and "admin=delete_messages" in last["buttons"][0][1]
    env.engine.games.clear(); env.engine.user_game.clear()
    n = len(env.io.sent)
    env.db.add_dm(1)
    env.run(env.engine.new_game(env.CHAT, 1, "Ada", "it", "broken"))   # Broken Canva needs no deletions
    assert all("amministratore" not in m["text"] for m in env.io.sent[n:])
