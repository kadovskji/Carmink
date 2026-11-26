"""Dictionary export and import: the file, a pasted list, and the short share codes.

File format (what "export" produces): {"carmink": 1, "words": {"it": [{"w", "alts", "d", "c", "b", "ea", "eb",
"n", "l"}, ...], "en": [...]}} - the level, and what the group learned about each word, travel with it.
A plain list is accepted too, one word per line: `word | synonym | synonym | 2` (the last number is the level)."""
import json
import secrets

import config
import words
from db import Database

FORMAT = 1
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"      # no 0/O, 1/I/L


def dump(rows: dict[str, list[dict]]) -> str:
    return json.dumps({"carmink": FORMAT, "words": rows}, ensure_ascii=False, separators=(",", ":"))


def _num(v, lo: float, hi: float, default: float = 0.0) -> float:
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return default


def _item(raw: dict) -> dict | None:
    if not isinstance(raw, dict) or not isinstance(raw.get("w"), str):
        return None
    word = words.validate_custom(raw["w"])
    if not word:
        return None
    alts, seen = [], {words.compact(word)}
    for a in raw.get("alts") or []:
        a = words.validate_custom(a) if isinstance(a, str) else None
        if a and words.compact(a) not in seen:
            seen.add(words.compact(a))
            alts.append(a)
    d = int(_num(raw.get("d"), 1, 3, 2))
    return {"w": word, "alts": alts[:config.CUSTOM_ALTS_MAX], "d": d,
            "c": "other" if raw.get("c") == "custom" else words.cat_of(raw.get("c")),
            "b": int(_num(raw.get("b"), 1, 3, d)), "ea": _num(raw.get("ea"), 0, 100),
            "eb": _num(raw.get("eb"), 0, 100), "n": int(_num(raw.get("n"), 0, 100000)),
            "l": bool(raw.get("l"))}


def parse(text: str, lang: str) -> tuple[dict[str, list[dict]], int]:
    """({lang: [item]}, how many entries were not acceptable). Raises ValueError for an unreadable file."""
    text = text.strip().lstrip("﻿")
    out: dict[str, list[dict]] = {}
    bad = 0
    if text.startswith("{"):
        try:
            data = json.loads(text)
            groups = data["words"]
        except (ValueError, KeyError, TypeError):
            raise ValueError("unreadable")
        if not isinstance(groups, dict):
            raise ValueError("unreadable")
        for lg, items in groups.items():
            if lg not in words.LANGUAGES or not isinstance(items, list):
                bad += len(items) if isinstance(items, list) else 1
                continue
            for raw in items:
                it = _item(raw)
                if it:
                    out.setdefault(lg, []).append(it)
                else:
                    bad += 1
        return out, bad
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        diff = 2
        head, sep, tail = line.rpartition("|")
        if sep and tail.strip() in ("1", "2", "3"):
            diff, line = int(tail), head
        parsed = words.parse_custom(line)
        if not parsed:
            bad += 1
            continue
        out.setdefault(lang, []).append({"w": parsed[0], "alts": list(parsed[1]), "d": diff, "c": "other",
                                         "b": diff, "ea": 0.0, "eb": 0.0, "n": 0, "l": False})
    return out, bad


def _alt_keys(word: str, alts) -> frozenset:
    """Synonyms as they match answers (ignoring case, accents, spaces), without the word itself."""
    return frozenset(words.compact(a) for a in alts if a) - {words.compact(word)}


def merge(db: Database, chat_id: int, items: dict[str, list[dict]], user_id: int, dry: bool,
          update: bool = False) -> dict:
    """Add the words the group doesn't have yet. Words it already has are left alone, unless `update`: then
    their level, synonyms and statistics become the file's. With `dry` only count what would happen."""
    for lang in items:
        db.ensure_dictionary(chat_id, lang)       # the built-in words first: what the file brings is on top
    res = {"new": 0, "existing": 0, "changed": 0, "full": 0}
    for lang, rows in items.items():
        total = db.count_custom(chat_id, lang)
        have = {words.compact(e.word): e.word for e in db.custom_entries(chat_id, lang)}
        for it in rows:
            key = words.compact(it["w"])
            if key in have:
                res["existing"] += 1
                stored = have[key]
                cur = db.word_data(chat_id, lang, stored)
                if cur and (cur[0], _alt_keys(stored, cur[1].split("|")), cur[2], bool(cur[3])) != (
                        it["d"], _alt_keys(it["w"], it["alts"]), it["n"], it["l"]):
                    res["changed"] += 1
                    if update and not dry:
                        db.overwrite_word(chat_id, lang, stored, tuple(it["alts"]), it["d"], it["b"],
                                          (it["ea"], it["eb"], it["n"]), it["l"], it["c"])
            elif total >= config.CUSTOM_WORDS_MAX:
                res["full"] += 1
            else:
                have[key] = it["w"]
                total += 1
                res["new"] += 1
                if not dry:
                    db.add_word(chat_id, lang, it["w"], it["d"], user_id, tuple(it["alts"]), it["c"],
                                (it["ea"], it["eb"], it["n"]), it["l"], it["b"])
    return res


def new_code() -> str:
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def clean_code(text: str) -> str:
    raw = "".join(c for c in text.upper() if c.isalnum())
    return f"{raw[:4]}-{raw[4:]}" if len(raw) == 8 else ""
