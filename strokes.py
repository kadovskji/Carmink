"""Validation of the live drawing events sent by the drawer's Mini App.

The drawer streams small events (begin / pt / sh / end / op / undo / redo, see web/board.js);
the server stores them and hands them to everybody else, so they are checked and rebuilt
here: only known keys survive, numbers are clamped to the canvas.
"""
import re

import config

W, H = 800, 600
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_EVENTS = {"op", "begin", "pt", "sh", "end", "undo", "redo"}


def _num(v, lo: float, hi: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
        raise ValueError("number expected")
    return round(min(max(float(v), lo), hi), 1)


def _point(p) -> list[float]:
    if not isinstance(p, (list, tuple)) or len(p) != 2:
        raise ValueError("point expected")
    return [_num(p[0], 0, W), _num(p[1], 0, H)]


def _points(ps) -> list[list[float]]:
    if not isinstance(ps, (list, tuple)) or not 1 <= len(ps) <= config.STROKE_POINTS_MAX:
        raise ValueError("points expected")
    return [_point(p) for p in ps]


def _op(op) -> dict:
    if not isinstance(op, dict):
        raise ValueError("op expected")
    kind = op.get("k")
    if kind == "x":
        return {"k": "x"}
    color = op.get("c")
    if not isinstance(color, str) or not _COLOR.match(color):
        raise ValueError("bad colour")
    if kind == "f":
        return {"k": "f", "c": color, "x": int(_num(op.get("x"), 0, W - 1)),
                "y": int(_num(op.get("y"), 0, H - 1))}
    width = _num(op.get("w"), 1, 80)
    if kind == "s":
        return {"k": "s", "c": color, "w": width, "p": _points(op.get("p"))}
    if kind == "sh":
        if op.get("t") not in ("circle", "rect"):
            raise ValueError("bad shape")
        return {"k": "sh", "t": op["t"], "f": bool(op.get("f")), "c": color, "w": width,
                "a": _point(op.get("a")), "b": _point(op.get("b"))}
    raise ValueError("bad op")


def clean_event(ev) -> dict:
    """Return a sanitised copy of one event, or raise ValueError."""
    if not isinstance(ev, dict) or ev.get("e") not in _EVENTS:
        raise ValueError("bad event")
    kind = ev["e"]
    if kind in ("op", "begin"):
        return {"e": kind, "op": _op(ev.get("op"))}
    if kind == "pt":
        return {"e": "pt", "p": _points(ev.get("p"))}
    if kind == "sh":
        return {"e": "sh", "b": _point(ev.get("b"))}
    if kind == "end":
        return {"e": "end", "b": _point(ev["b"])} if ev.get("b") is not None else {"e": "end"}
    return {"e": kind}


def clean_events(events) -> list[dict]:
    if not isinstance(events, list) or len(events) > config.EVENTS_PER_POST:
        raise ValueError("too many events")
    return [clean_event(e) for e in events]
