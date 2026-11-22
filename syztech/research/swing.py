"""Research only – candidate trend rule (19 Nov 2026 discussion), not used by any report.

Verdict = 200-day slope (direction) × swing structure (higher highs / higher lows), both scaled to the
instrument's volatility:
  * one-month move  m_t = stdev(daily log returns, 100 days) × √20
  * swing threshold θ_t = k × m_t   – a swing high / low is confirmed once the close reverses θ from the extreme
  * flat band          |MA200_t / MA200_t-20 − 1| < f × m_t
Structure: up = last two confirmed highs and lows both rising; down = both falling; else mixed. A close below the last
confirmed swing low moves the structure one step down (up → mixed, mixed → down); a close above the last swing high
moves it one step up. Verdict table:
               up          mixed       down
  rising    Bullish      Neutral+    Neutral
  flat      Neutral+     Neutral     Neutral-
  falling   Neutral      Neutral-    Bearish
Closes only (the exports carry PX_LAST); nothing is filled.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TABLE = {("rising", "up"): "Bullish", ("rising", "mixed"): "Neutral+", ("rising", "down"): "Neutral",
         ("flat", "up"): "Neutral+", ("flat", "mixed"): "Neutral", ("flat", "down"): "Neutral-",
         ("falling", "up"): "Neutral", ("falling", "mixed"): "Neutral-", ("falling", "down"): "Bearish"}


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


def swing_history(close: pd.Series, k: float = 2.0, flat_f: float = 0.25) -> pd.DataFrame:
    """Daily slope state, structure and verdict, using only information available on each bar."""
    close = close.dropna()
    m = monthly_move(close)
    theta = (k * m).to_numpy()
    ma = close.rolling(200, min_periods=200).mean()
    s20 = (ma / ma.shift(20) - 1).to_numpy()
    band = (flat_f * m).to_numpy()
    piv = pivots(close, theta)
    c = close.to_numpy(dtype=float)
    n = len(c)
    by_conf = {}
    for p in piv:
        by_conf.setdefault(p[3], []).append(p)
    H, L, Hi, Li = [], [], [], []
    rows = []
    for i in range(n):
        for p in by_conf.get(i, []):
            (H if p[0] == "H" else L).append(p[2])
            (Hi if p[0] == "H" else Li).append(p[1])
        if np.isnan(s20[i]) or np.isnan(band[i]):
            rows.append((None,) * 11); continue
        slope = "rising" if s20[i] > band[i] else "falling" if s20[i] < -band[i] else "flat"
        st = "mixed"
        if len(H) >= 2 and len(L) >= 2:
            if H[-1] > H[-2] and L[-1] > L[-2]:
                st = "up"
            elif H[-1] < H[-2] and L[-1] < L[-2]:
                st = "down"
        last_l, last_h = (L[-1] if L else None), (H[-1] if H else None)
        if last_l is not None and c[i] < last_l:
            st = {"up": "mixed", "mixed": "down", "down": "down"}[st]
        elif last_h is not None and c[i] > last_h:
            st = {"down": "mixed", "mixed": "up", "up": "up"}[st]
        rows.append((slope, st, TABLE[(slope, st)], last_l, last_h, Li[-1] if Li else None, Hi[-1] if Hi else None,
                     L[-2] if len(L) > 1 else None, Li[-2] if len(Li) > 1 else None,
                     H[-2] if len(H) > 1 else None, Hi[-2] if len(Hi) > 1 else None))
    return pd.DataFrame(rows, index=close.index,
                        columns=["slope", "structure", "verdict", "swing_low", "swing_high", "swing_low_bar", "swing_high_bar",
                                 "prev_low", "prev_low_bar", "prev_high", "prev_high_bar"])


def family(v) -> str | None:
    if not isinstance(v, str):
        return None
    return "Bullish" if v == "Bullish" else "Bearish" if v.startswith("Bearish") else "Neutral" if v.startswith("Neutral") else None
