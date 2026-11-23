"""Support / resistance from volatility-scaled swings (adopted 22 Nov 2026, BUILD_SPEC §2.2 / §3.2).

* one-month move  m_t = stdev(daily log returns, 100 days) × √20
* swing size      θ_t = k × median(m over the past 252 bars), k = 1.5 – the median of a year of one-month moves, so a
  parabolic run or a crash cannot inflate it (fix of 23 Nov 2026: Teradyne / AMAT / ON read Bullish after −55–58%
  because a 25–36% threshold left only 2024–25 swing lows)
* a swing high / low is confirmed once the close reverses θ_t from the extreme
* support = last confirmed swing low, resistance = last confirmed swing high
* a broken level stands: after a lower low the prior swing low (now broken) stays the support, its break counting
  until the resistance breaks; after a higher high the prior swing high stays the resistance
Breaks count from the earlier of the two swing points used. Closes only; nothing is filled. Series with values ≤ 0
(negative yields) cannot be measured in log returns and return None (caller falls back to the 52-week levels).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

SWING_K = 1.5


@dataclass(frozen=True)
class SwingLevels:
    support: float
    support_bar: int
    support_broken_prior: bool          # True: support is a prior swing low already undercut (lower low)
    resistance: float
    resistance_bar: int
    resistance_broken_prior: bool       # True: resistance is a prior swing high already exceeded (higher high)
    start: int                          # breaks count from this bar (earlier of the two swing points)


def monthly_move(close: pd.Series, window: int = 100) -> pd.Series:
    r = np.log(close).diff()
    return r.rolling(window, min_periods=window).std() * np.sqrt(20)


def pivots(close: pd.Series, theta: np.ndarray) -> list[tuple[str, int, float, int]]:
    """Confirmed swing points on closes: (kind 'H'/'L', bar of the extreme, value, bar of confirmation)."""
    c = close.to_numpy(dtype=float)
    out = []
    trend, ext, ext_i = 0, c[0], 0
    lo, lo_i, hi, hi_i = c[0], 0, c[0], 0
    for i in range(1, len(c)):
        x, th = c[i], theta[i]
        if np.isnan(th):
            continue
        if trend == 0:                       # first leg: whichever side moves θ first
            if x > hi:
                hi, hi_i = x, i
            if x < lo:
                lo, lo_i = x, i
            if x <= hi * (1 - th):
                out.append(("H", hi_i, hi, i)); trend, ext, ext_i = -1, x, i
            elif x >= lo * (1 + th):
                out.append(("L", lo_i, lo, i)); trend, ext, ext_i = 1, x, i
            continue
        if trend == 1:
            if x > ext:
                ext, ext_i = x, i
            elif x <= ext * (1 - th):
                out.append(("H", ext_i, ext, i)); trend, ext, ext_i = -1, x, i
        else:
            if x < ext:
                ext, ext_i = x, i
            elif x >= ext * (1 + th):
                out.append(("L", ext_i, ext, i)); trend, ext, ext_i = 1, x, i
    return out


def swing_threshold(close: pd.Series, k: float = SWING_K) -> pd.Series:
    """θ_t = k × median one-month move over the past 252 bars (at least 120 needed)."""
    return k * monthly_move(close).rolling(252, min_periods=120).median()


def swing_levels(close: pd.Series, k: float = SWING_K) -> SwingLevels | None:
    """Levels at the last bar of `close` (ascending closes). None when no swing high and low are confirmed yet."""
    close = close.dropna()
    if len(close) < 102 or (close <= 0).any():
        return None
    piv = pivots(close, swing_threshold(close, k).to_numpy())
    H = [(p[2], p[1]) for p in piv if p[0] == "H"]
    L = [(p[2], p[1]) for p in piv if p[0] == "L"]
    if not H or not L:
        return None
    (sup, sb), sp = L[-1], False
    (res, rb), rp = H[-1], False
    if len(L) > 1 and L[-1][0] < L[-2][0]:
        (sup, sb), sp = L[-2], True
    if len(H) > 1 and H[-1][0] > H[-2][0]:
        (res, rb), rp = H[-2], True
    return SwingLevels(float(sup), int(sb), sp, float(res), int(rb), rp, int(min(sb, rb)))
