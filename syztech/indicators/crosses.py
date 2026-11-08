"""Golden / death crosses of MA50 over MA200, qualified by the 200-day slope on the cross bar."""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .slope import FALLING, RISING

GOLDEN, DEATH, UNQUALIFIED, NO_CROSS = "golden", "death", "cross_unqualified", "none"


def cross_events(fast: pd.Series, slow: pd.Series) -> pd.Series:
    """+1 on the bar fast closes above slow (was <= on the prior bar), -1 for the reverse, else 0."""
    diff = fast - slow
    prev = diff.shift(1)
    up = (diff > 0) & (prev <= 0)
    down = (diff < 0) & (prev >= 0)
    return up.astype(int) - down.astype(int)


@dataclass(frozen=True)
class Cross:
    kind: str                 # golden / death / cross_unqualified / none
    direction: str | None     # golden / death (raw direction, also for unqualified crosses)
    pos: int | None


def last_cross(fast: pd.Series, slow: pd.Series, slow_slope: pd.Series, lookback: int) -> Cross:
    """Most recent cross within the last `lookback` bars.

    golden: MA50 crossed above MA200 and the 200-day slope was rising on the cross bar.
    death:  MA50 crossed below MA200 and the 200-day slope was falling on the cross bar.
    Any other cross is `cross_unqualified` and does not count.
    """
    ev = cross_events(fast, slow).to_numpy()
    n = len(ev)
    idx = np.flatnonzero(ev[max(0, n - lookback):]) + max(0, n - lookback)
    if idx.size == 0:
        return Cross(NO_CROSS, None, None)
    p = int(idx[-1])
    direction = GOLDEN if ev[p] > 0 else DEATH
    s = slow_slope.iloc[p]
    if (direction == GOLDEN and s == RISING) or (direction == DEATH and s == FALLING):
        return Cross(direction, direction, p)
    return Cross(UNQUALIFIED, direction, p)
