"""Game model and pure rules (points, laps, ranking). No Telegram, no I/O."""
import time
from dataclasses import dataclass, field
from enum import Enum, auto

import config
from words import Entry


class Phase(Enum):
    LOBBY = auto()      # sign-ups
    BREAK = auto()      # pause between turns: the next drawer is announced
    CHOOSING = auto()   # the drawer picks one of three words
    STARTING = auto()   # word chosen, waiting for the first stroke
    DRAWING = auto()    # the clock runs, the others guess
    WRITING = auto()    # Broken Canva: everybody sends the initial phrase to the bot
    STEP = auto()       # Broken Canva: drawing or describing
    DONE = auto()


@dataclass
class Turn:
    drawer: int
    choices: list[Entry]
    word: Entry | None = None
    reveal_order: list[int] = field(default_factory=list)   # letter positions, in reveal order
    hints: int = 0
    started_at: float | None = None
    guessed: dict[int, int] = field(default_factory=dict)   # user id -> points earned
    close_notices: dict[int, int] = field(default_factory=dict)
    photo_msg: int | None = None
    posted_ver: int = -1        # snapshot version shown in the chat
    posted_hints: int = 0
    win_remaining: float | None = None     # speedrun: seconds left when the winning guess came
    events: list[dict] = field(default_factory=list)      # live drawing events (see strokes.py)
    attempts: list[dict] = field(default_factory=list)    # classic: guesses typed in the Mini App
    last_attempt: dict[int, float] = field(default_factory=dict)
    chat_warned: set[int] = field(default_factory=set)
    final_open: bool = False    # round over, waiting for the drawer's finished canvas
    header: str = ""            # the round's result message, posted when the wait is over

    def revealed(self) -> set[int]:
        return set(self.reveal_order[:self.hints])


@dataclass
class BrokenState:
    """Broken Canva. chains[i] is the chain started by order[i]; at pass k player order[p]
    handles chain (p - k) mod N, so nobody ever meets the chain of their own phrase."""
    order: list[int]
    steps: int                                  # passes after the initial phrase, always odd
    chains: list[list[dict]] = field(default_factory=list)
    step: int = 0                               # 0 = initial phrases
    inbox: dict[int, dict] = field(default_factory=dict)    # this pass: user id -> item handed in
    given: dict[int, dict] = field(default_factory=dict)    # this pass: user id -> item received
    drafts: dict[int, bytes] = field(default_factory=dict)  # latest drawing draft per user
    last_draft: dict[int, float] = field(default_factory=dict)
    status_msg: int | None = None

    @property
    def kind(self) -> str:
        """What the players hand in at this pass: a phrase (even passes) or a drawing (odd)."""
        return "draw" if self.step % 2 else "text"


def broken_steps(n_players: int, cycles: int | None = None) -> int:
    """Passes after the phrase. A cycle is a phrase (or description) and its drawing, so `cycles`
    cycles are 2 * cycles - 1 passes. Default: one cycle per player, at most BROKEN_MAX_CYCLES."""
    c = cycles or min(n_players, config.BROKEN_MAX_CYCLES)
    return 2 * max(1, c) - 1


@dataclass
class Game:
    chat_id: int
    lang: str
    creator: int
    players: dict[int, str]                     # user id -> display name (current players)
    lobby_end: float
    mode: str = "speedrun"
    names: dict[int, str] = field(default_factory=dict)     # everybody who ever played here
    phase: Phase = Phase.LOBBY
    gen: int = 0                                # bumped at every phase change: stale timers die
    queue: list[int] = field(default_factory=list)          # drawers still to come
    turn_no: int = 0
    turn: Turn | None = None
    deadline: float = 0.0                       # end of the running timer (shown in the Mini App)
    scores: dict[int, int] = field(default_factory=dict)
    guesses: dict[int, int] = field(default_factory=dict)   # correct guesses per player
    drawings: dict[int, int] = field(default_factory=dict)  # turns actually drawn per player
    used: set[str] = field(default_factory=set)             # compact forms of words already used
    pool: list[Entry] = field(default_factory=list)
    snapshot: bytes | None = None
    snap_ver: int = 0
    last_snap_at: float = 0.0
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    broken: BrokenState | None = None
    draw_seconds: int = config.DRAW_SECONDS    # drawing time of this match (see /settings)
    cycles: int | None = None                  # Broken Canva cycles (None = one per player, see /settings)
    test: bool = False                          # admin test match: fake players, nothing saved
    test_ids: list[int] = field(default_factory=list)       # fake players, in order (Test 1, Test 2…)

    @property
    def min_players(self) -> int:
        return config.MIN_PLAYERS_BROKEN if self.mode == "broken" else config.MIN_PLAYERS

    def name(self, uid: int) -> str:
        return self.players.get(uid) or self.names.get(uid, "?")

    def go(self, phase: Phase, seconds: float = 0.0, now: float = 0.0) -> None:
        """Change phase, invalidating every timer of the previous one."""
        self.phase = phase
        self.gen += 1
        self.deadline = now + seconds if seconds else 0.0

    @property
    def total_turns(self) -> int:
        return self.turn_no + len(self.queue)


# ---------------------------------------------------------------- rules
def laps(n_players: int) -> int:
    """Everybody draws once with FEW_PLAYERS or more, twice with fewer (so: 5+ turns)."""
    return 1 if n_players >= config.FEW_PLAYERS else 2


def hint_factor(hints: int) -> float:
    return max(0.0, 1.0 - config.HINT_PENALTY * hints)


def guess_points(remaining: float, diff: int, hints: int, total: float | None = None) -> int:
    """Faster guess, more points; harder word and fewer hints, more points."""
    share = max(0.0, min(1.0, remaining / (total or config.DRAW_SECONDS)))
    base = config.GUESS_MAX * (config.GUESS_MIN_SHARE + (1 - config.GUESS_MIN_SHARE) * share)
    return max(1, round(base * config.DIFFICULTY_MULT.get(diff, 1.0) * hint_factor(hints)))


def speedrun_drawer_points(remaining: float, hints: int, total: float | None = None) -> int:
    """Speedrun: the drawer earns up to DRAWER_SPEEDRUN_MAX, less the later the word is guessed."""
    share = max(0.0, min(1.0, remaining / (total or config.DRAW_SECONDS)))
    base = config.DRAWER_SPEEDRUN_MAX * (config.GUESS_MIN_SHARE + (1 - config.GUESS_MIN_SHARE) * share)
    return max(1, round(base * hint_factor(hints)))


def drawer_points(n_guessers: int, diff: int, hints: int) -> int:
    """More players guess, more points for the drawer."""
    return round(config.DRAWER_PER_GUESS * n_guessers
                 * config.DIFFICULTY_MULT.get(diff, 1.0) * hint_factor(hints))


def ranking(scores: dict[int, int], players: dict[int, str]) -> list[tuple[int, int, str, int]]:
    """[(rank, user_id, name, points)] for the current players, ties share the rank."""
    rows = sorted(((scores.get(u, 0), n, u) for u, n in players.items()),
                  key=lambda r: (-r[0], r[1].casefold()))
    out, last, rank = [], None, 0
    for i, (pts, name, uid) in enumerate(rows, 1):
        if pts != last:
            rank, last = i, pts
        out.append((rank, uid, name, pts))
    return out
