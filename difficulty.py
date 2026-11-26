"""Adaptive word difficulty: how easily a word is guessed decides its level (1 easy .. 3 hard).

Every appearance of a word scores an "ease" between 0 and 1; a decaying weighted average,
pulled towards what the word's starting level predicts, gives the estimate. The level changes only
past a threshold (different going up and going down, so it doesn't flicker)."""
import config


def ease(mode: str, solved: int, guessers: int, remaining_share: float, hints: int) -> float:
    """Ease of one appearance. Classic: share of the guessers who got it. Speedrun the round ends at the
    first right answer, so: 0 if nobody, else the faster, the easier. Hints make guessing easier, so they
    discount the result."""
    if mode == "speedrun":
        base = (config.EASE_SPEEDRUN_FLOOR + (1 - config.EASE_SPEEDRUN_FLOOR)
                * max(0.0, min(1.0, remaining_share))) if solved else 0.0
    else:
        base = solved / guessers if guessers else 0.0
    return base * max(0.0, 1.0 - config.HINT_PENALTY * hints)


def weight(guessers: int) -> float:
    return min(guessers, config.EASE_WEIGHT_CAP) / config.EASE_WEIGHT_CAP


def update(a: float, b: float, value: float, w: float) -> tuple[float, float]:
    """Fold one appearance into the running sums (A = weighted ease, B = weight)."""
    return config.EASE_DECAY * a + w * value, config.EASE_DECAY * b + w


def estimate(a: float, b: float, base: int) -> float:
    """Expected ease: the starting level's prior counts for a few appearances, then the data takes over."""
    m = config.EASE_PRIOR_WEIGHT
    return (m * config.EASE_PRIOR.get(base, 0.5) + a) / (m + b)


def next_level(level: int, est: float) -> int:
    if level == 1:
        return 1 if est >= config.EASE_UP_BACK else (3 if est <= config.EASE_DOWN else 2)
    if level == 3:
        return 3 if est <= config.EASE_DOWN_BACK else (1 if est >= config.EASE_UP else 2)
    return 1 if est >= config.EASE_UP else (3 if est <= config.EASE_DOWN else 2)


def first_level(value: float) -> int:
    """Level of a brand-new word, from its first appearance alone (no prior)."""
    return 1 if value >= config.EASE_UP else (3 if value <= config.EASE_DOWN else 2)
