import config
from game import drawer_points, guess_points, hint_factor, laps, ranking


def test_laps_two_below_five_players_else_one():
    assert [laps(n) for n in (3, 4, 5, 6, 12)] == [2, 2, 1, 1, 1]
    assert 3 * laps(3) == 6 and 4 * laps(4) == 8      # the rounds from the spec
    assert all(n * laps(n) >= 5 for n in range(3, 20))


def test_guess_points_fall_with_time_and_rise_with_difficulty():
    fast = guess_points(config.DRAW_SECONDS, 1, 0)
    slow = guess_points(1, 1, 0)
    assert fast == 100 and slow >= 40 and fast > slow
    assert guess_points(30, 3, 0) > guess_points(30, 2, 0) > guess_points(30, 1, 0)
    assert guess_points(-5, 1, 0) == guess_points(0, 1, 0) == 40      # never below the floor


def test_every_hint_costs_twenty_percent():
    assert [round(hint_factor(h), 6) for h in range(4)] == [1.0, 0.8, 0.6, 0.4]
    assert guess_points(60, 1, 1) == 80
    assert guess_points(60, 1, 3) == 40
    assert drawer_points(2, 1, 1) == round(60 * 0.8)


def test_drawer_earns_more_when_more_players_guess():
    assert drawer_points(0, 2, 0) == 0
    assert drawer_points(1, 1, 0) < drawer_points(2, 1, 0) < drawer_points(5, 1, 0)


def test_ranking_shares_rank_on_ties_and_ignores_missing_players():
    rows = ranking({1: 50, 2: 80, 3: 80, 9: 999}, {1: "Ada", 2: "Zoe", 3: "Bob"})
    assert rows == [(1, 3, "Bob", 80), (1, 2, "Zoe", 80), (3, 1, "Ada", 50)]
