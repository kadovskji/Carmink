"""Adaptive difficulty: ease of a round, the running estimate, level changes."""
import pytest

import config
import difficulty as d


def test_classic_ease_is_the_share_of_guessers_who_got_it():
    assert d.ease("classic", 4, 5, 0, 0) == pytest.approx(0.8)
    assert d.ease("classic", 0, 5, 0, 0) == 0


def test_speedrun_ease_depends_on_how_fast_the_word_was_guessed():
    assert d.ease("speedrun", 0, 5, 0.9, 0) == 0
    fast, slow = d.ease("speedrun", 1, 5, 0.95, 0), d.ease("speedrun", 1, 5, 0.05, 0)
    assert fast > slow >= config.EASE_SPEEDRUN_FLOOR
    assert d.ease("speedrun", 1, 5, 1.0, 0) == pytest.approx(1.0)


def test_hints_discount_the_ease():
    assert d.ease("classic", 5, 5, 0, 2) == pytest.approx(1 - 2 * config.HINT_PENALTY)


def test_more_guessers_weigh_more_up_to_a_cap():
    assert d.weight(2) < d.weight(4) < d.weight(config.EASE_WEIGHT_CAP) == d.weight(20) == 1.0


def run(base, ease, n=1, guessers=5):
    a = b = 0.0
    out = []
    for _ in range(n):
        a, b = d.update(a, b, ease, d.weight(guessers))
        out.append(d.estimate(a, b, base))
    return out


def test_a_medium_word_becomes_easy_after_about_five_good_rounds_not_after_one():
    est = run(2, 0.8, 6)
    levels = [d.next_level(2, e) for e in est]
    assert levels[:4] == [2, 2, 2, 2] and levels[4:] == [1, 1]


def test_a_medium_word_nobody_guesses_becomes_hard_after_about_five_rounds():
    levels = [d.next_level(2, e) for e in run(2, 0.0, 6)]
    assert levels[:4] == [2, 2, 2, 2] and levels[4:] == [3, 3]


def test_levels_do_not_flicker_around_a_threshold():
    assert d.next_level(1, 0.60) == 1 and d.next_level(2, 0.60) == 2      # easy stays easy above 0.55
    assert d.next_level(1, 0.50) == 2 and d.next_level(1, 0.20) == 3
    assert d.next_level(3, 0.30) == 3 and d.next_level(2, 0.30) == 2      # hard stays hard below 0.35
    assert d.next_level(3, 0.40) == 2 and d.next_level(3, 0.70) == 1


def test_old_rounds_fade():
    a = b = 0.0
    for _ in range(10):
        a, b = d.update(a, b, 0.0, 1.0)
    for _ in range(12):
        a, b = d.update(a, b, 1.0, 1.0)
    assert d.next_level(2, d.estimate(a, b, 2)) == 1


@pytest.mark.parametrize("ease,level", [(1.0, 1), (0.8, 1), (0.6, 2), (0.4, 2), (0.2, 3), (0.1, 3)])
def test_a_new_word_gets_its_level_from_its_first_round(ease, level):
    assert d.first_level(ease) == level
