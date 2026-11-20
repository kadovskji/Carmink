import random

import pytest

import words
from words import Entry


def test_normalization_ignores_case_accents_spaces_and_punctuation():
    assert words.compact("  Città-Vecchia ") == "cittavecchia"
    assert words.compact("PERCHÉ?") == "perche"


def test_is_correct_uses_main_word_and_alternatives():
    e = Entry("frigorifero", alts=("frigo",))
    assert words.is_correct(e, "Frigo!")
    assert words.is_correct(e, "frigorifero")
    assert not words.is_correct(e, "frigoriferi")


def test_is_close_only_one_typo_and_long_words():
    e = Entry("elefante")
    assert words.is_close(e, "elefnte")        # missing letter
    assert words.is_close(e, "elefantr")       # wrong letter
    assert words.is_close(e, "elefantee")      # extra letter
    assert not words.is_close(e, "elefante")   # exact is correct, not close
    assert not words.is_close(e, "elefxxte")   # two typos
    assert not words.is_close(Entry("gatto"[:4]), "gatt")   # words under 5 letters never "close"


def test_contains_answer_finds_spoilers():
    e = Entry("orso polare", alts=("orso",))
    assert words.contains_answer(e, "secondo me è un ORSO!")
    assert not words.contains_answer(e, "è un animale?")
    assert not words.contains_answer(Entry("io"), "io penso di sì")   # too short to be a spoiler


def test_mask_and_hint_limits():
    assert words.make_mask("orso polare") == "_ _ _ _   _ _ _ _ _ _"
    assert words.make_mask("gatto", {0, 4}) == "g _ _ _ o"
    assert words.make_mask("sci-fi", {0}) == "s _ _ - _ _"
    assert words.max_hints("gatto") == 2
    assert words.max_hints("orso polare") == 3
    assert words.max_hints("sì") == 1
    assert words.max_hints("a") == 0


def test_validate_custom_word():
    assert words.validate_custom("  orso   polare ") == "orso polare"
    assert words.validate_custom("l'ape") == "l'ape"
    assert words.validate_custom("x") is None
    assert words.validate_custom("tre quattro cinque sei") is None
    assert words.validate_custom("abc123") is None
    assert words.validate_custom("a" * 31) is None


@pytest.mark.parametrize("lang", words.LANGUAGES)
def test_builtin_dictionary_is_clean(lang):
    entries = words.load(lang)
    assert entries
    seen: dict[str, str] = {}
    for e in entries:
        assert e.cat in words.CATEGORIES and e.diff in (1, 2, 3)
        assert 3 <= len(words.compact(e.word)) <= words.config.WORD_MAX_LEN, e.word
        for form in e.forms():
            assert form not in seen, f"{form!r} appears in {e.word!r} and {seen[form]!r}"
            seen[form] = e.word
    for cat in words.CATEGORIES:
        for diff in (1, 2, 3):
            assert sum(1 for e in entries if e.cat == cat and e.diff == diff) >= 10, (cat, diff)


def test_pick_choices_gives_one_word_per_difficulty_without_repeats():
    pool = words.load("it")
    rng = random.Random(3)
    used: set[str] = set()
    for _ in range(40):
        picked = words.pick_choices(pool, used, rng)
        assert [e.diff for e in picked] == [1, 2, 3]
        assert not any(words.compact(e.word) in used for e in picked)
        used.add(words.compact(picked[0].word))


def test_pick_choices_with_a_tiny_pool():
    pool = [Entry("uno", diff=1), Entry("due", diff=1)]
    picked = words.pick_choices(pool, set(), random.Random(1))
    assert {e.word for e in picked} == {"uno", "due"}
    assert words.pick_choices([], set(), random.Random(1)) == []


def test_parse_custom_synonyms():
    assert words.parse_custom("orso polare") == ("orso polare", ())
    assert words.parse_custom(" Scooter | kick  scooter |scooter| SCOOTER ") == ("Scooter", ("kick scooter",))
    assert words.parse_custom("aa | bb | cc | dd | ee | ff | gg | hh")[1] == ("bb", "cc", "dd", "ee", "ff")
    assert words.parse_custom("| xx") is None and words.parse_custom("xx | 12") is None
    assert words.parse_custom("") is None
