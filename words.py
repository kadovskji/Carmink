"""Dictionary: loading, picking three words, answer matching and hint masks."""
import json
import random
import re
import unicodedata
from dataclasses import dataclass

import config

CATEGORIES = ("animals", "nature", "plants", "body", "food", "people", "places", "vehicles", "objects",
              "actions", "sport", "music", "other")
CATEGORY_ICON = {"animals": "🐾", "nature": "🏔", "plants": "🌿", "body": "👕", "food": "🍕", "people": "👷",
                 "places": "🏛", "vehicles": "🚗", "objects": "🪑", "actions": "🎭", "sport": "⚽",
                 "music": "🎸", "other": "✨"}


def cat_of(cat: str | None) -> str:
    """A stored category; anything unknown (and the old 'custom') is 'other'."""
    return cat if cat in CATEGORY_ICON else "other"
LANGUAGES = ("it", "en")


@dataclass(frozen=True)
class Entry:
    word: str                   # shown to the drawer and revealed at the end
    alts: tuple[str, ...] = ()  # other spellings / synonyms accepted as correct
    diff: int = 2               # 1 easy, 2 medium, 3 hard
    cat: str = "other"

    def forms(self) -> set[str]:
        return {compact(w) for w in (self.word, *self.alts) if compact(w)}


# ---------------------------------------------------------------- text helpers
def norm(s: str) -> str:
    """Lowercase and strip accents."""
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).casefold().strip()


def compact(s: str) -> str:
    """Like norm(), but also without spaces and punctuation."""
    return re.sub(r"[\W_]+", "", norm(s))


def _distance_is_one(a: str, b: str) -> bool:
    """True if a and b differ by exactly one insertion, deletion or substitution."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    i = 0
    while i < len(short) and short[i] == long_[i]:
        i += 1
    return short[i:] == long_[i + 1:]


# ---------------------------------------------------------------- matching
def is_correct(entry: Entry, text: str) -> bool:
    return compact(text) in entry.forms()


def is_close(entry: Entry, text: str) -> bool:
    """One typo away from the main word (only for words of 5+ letters)."""
    main = compact(entry.word)
    return len(main) >= 5 and _distance_is_one(compact(text), main)


def contains_answer(entry: Entry, text: str) -> bool:
    """The message reveals the answer (used to delete spoilers)."""
    flat = compact(text)
    return any(len(f) >= 3 and f in flat for f in entry.forms())


# ---------------------------------------------------------------- hints
def letter_positions(word: str) -> list[int]:
    return [i for i, ch in enumerate(word) if ch.isalnum()]


def max_hints(word: str) -> int:
    """At most 3 hints, and always leave at least half of the letters hidden."""
    return min(config.MAX_HINTS, len(letter_positions(word)) // 2)


def make_mask(word: str, revealed: set[int] | frozenset[int] = frozenset()) -> str:
    """'orso polare' -> '_ _ _ _   _ _ _ _ _ _' with the revealed positions shown."""
    parts = []
    for i, ch in enumerate(word):
        if ch.isalnum():
            parts.append(ch if i in revealed else "_")
        elif ch.isspace():
            parts.append(" ")
        else:
            parts.append(ch)
    return " ".join(parts)


# ---------------------------------------------------------------- loading
_cache: dict[str, list[Entry]] = {}


def _parse(raw: str, cat: str, diff: int) -> Entry:
    word, *alts = (p.strip() for p in raw.split("|"))
    return Entry(word=word, alts=tuple(a for a in alts if a), diff=diff, cat=cat)


def load(lang: str) -> list[Entry]:
    """Built-in dictionary for a language (data/words_<lang>.json), cached."""
    if lang not in _cache:
        path = config.DATA_DIR / f"words_{lang}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        _cache[lang] = [_parse(raw, cat, int(diff))
                        for cat, levels in data.items()
                        for diff, raws in levels.items()
                        for raw in raws]
    return _cache[lang]


def validate_custom(text: str) -> str | None:
    """Clean a word written by a player or an admin; None if it isn't acceptable."""
    word = " ".join(text.split())
    if not 2 <= len(word) <= config.WORD_MAX_LEN or len(word.split()) > config.WORD_MAX_WORDS:
        return None
    if not all(ch.isalpha() or ch in " '-" for ch in word):
        return None
    return word


def parse_custom(text: str) -> tuple[str, tuple[str, ...]] | None:
    """'word | synonym | synonym' -> (word, synonyms); None if any part is not acceptable.

    Synonyms equal to the word itself (or repeated) are dropped; at most CUSTOM_ALTS_MAX are kept."""
    parts = [p for p in (x.strip() for x in text.split("|")) if p]
    if not parts or text.strip().startswith("|"):
        return None
    cleaned = [validate_custom(p) for p in parts]
    if any(c is None for c in cleaned):
        return None
    main, seen, alts = cleaned[0], {compact(cleaned[0])}, []
    for a in cleaned[1:]:
        if compact(a) not in seen:
            seen.add(compact(a))
            alts.append(a)
    return main, tuple(alts[:config.CUSTOM_ALTS_MAX])


# ---------------------------------------------------------------- choosing
def pick_choices(pool: list[Entry], used: set[str], rng: random.Random) -> list[Entry]:
    """Three words for the drawer, one per difficulty level when possible."""
    fresh = [e for e in pool if compact(e.word) not in used] or list(pool)
    chosen: list[Entry] = []
    for diff in (1, 2, 3):
        level = [e for e in fresh if e.diff == diff and e not in chosen]
        if level:
            chosen.append(rng.choice(level))
    rest = [e for e in fresh if e not in chosen]
    rng.shuffle(rest)
    while len(chosen) < 3 and rest:
        chosen.append(rest.pop())
    return sorted(chosen, key=lambda e: e.diff)
