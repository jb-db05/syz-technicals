"""The trend rule on weekly closes – used by the master-list screen only (Florian, 25 Nov 2026).

Same rule set as the daily engine (BUILD_SPEC §3), every window divided by five:
  200-day average -> 40 weeks; 50-day -> 10 weeks; direction over 20 days -> 4 weeks, same 0.20% flat band;
  100-day band -> 20 weeks; one-month move = stdev of weekly log returns over 20 weeks × √4; swing threshold =
  1.5 × its median over 52 weeks (at least 26); minimum history 320 days -> 64 weeks.
Relative trend: direction of the 40-week average of price ÷ benchmark over 4 weeks (rising = Outperform).
Weekly close = the last close of each calendar week; nothing is filled.
Basis: `syztech/research/study_weekly.py` – 160 series, 13,318 dated comparisons, same verdict family as the daily
rule 88.4% of the time, opposite 0.1%, same relative trend 95.9%, 2.2 verdict changes a year against 2.5.
Every other document keeps the daily rule.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..indicators.rs import relative_strength
from .rules import INSUFFICIENT, TrendParams, TrendResult, evaluate
from .swing_levels import SWING_K, SwingLevels, pivots

WEEKLY_PARAMS = TrendParams(ma_long=40, ma_short=10, band_window=20, slope_lookback=4, flat_band=0.0020, cross_lookback=8,
                            bb_window=20, min_history=64, levels_lookback=20)
MOVE_WINDOW, MEDIAN_WINDOW, MEDIAN_MIN, WEEKS_PER_MONTH = 20, 52, 26, 4
RS_MA, RS_LOOK = 40, 4


def to_weekly(s: pd.Series) -> pd.Series:
    """Last close of each calendar (ISO) week. A series that is already weekly comes back unchanged."""
    s = s.dropna()
    iso = s.index.isocalendar()
    return s.groupby([iso.year.to_numpy(), iso.week.to_numpy()]).tail(1)


def weekly_swing_levels(w: pd.Series, k: float = SWING_K) -> SwingLevels | None:
    """Swing levels on weekly closes; same construction as `swing_levels` (a broken level stands)."""
    w = w.dropna()
    if len(w) < MOVE_WINDOW + 2 or (w <= 0).any():
        return None
    m = np.log(w).diff().rolling(MOVE_WINDOW, min_periods=MOVE_WINDOW).std() * np.sqrt(WEEKS_PER_MONTH)
    theta = (k * m.rolling(MEDIAN_WINDOW, min_periods=MEDIAN_MIN).median()).to_numpy()
    piv = pivots(w, theta)
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


def resolve_weekly_levels(w: pd.Series):
    """(support, resistance, support_origin, resistance_origin, start): swing levels, else the 52-week low / high."""
    sw = weekly_swing_levels(w)
    if sw is not None:
        d = lambda b: w.index[b].date()
        return (sw.support, sw.resistance, f"swing low ({d(sw.support_bar)})" + (", broken" if sw.support_broken_prior else ""),
                f"swing high ({d(sw.resistance_bar)})" + (", broken" if sw.resistance_broken_prior else ""), sw.start)
    x = w.iloc[-53:-1]
    if len(x) < 2:
        return None, None, None, None, None
    return float(x.min()), float(x.max()), f"52w low ({x.idxmin().date()})", f"52w high ({x.idxmax().date()})", len(w) - 1


def evaluate_weekly(w: pd.Series) -> tuple[TrendResult, dict]:
    """Verdict on weekly closes `w` (ascending). Returns the result and the levels used."""
    w = w.dropna()
    sup, res, so, ro, st = resolve_weekly_levels(w)
    r = evaluate(w, WEEKLY_PARAMS, sup, res, None, support_start=st, resistance_start=st)
    return r, dict(support=sup, resistance=res, support_origin=so, resistance_origin=ro)


def relative_weekly(w: pd.Series, bw: pd.Series) -> dict:
    """Relative trend on weekly closes: direction of the 40-week average of price ÷ benchmark over 4 weeks."""
    rs = relative_strength(w, bw).dropna()
    if len(rs) <= RS_MA + RS_LOOK:
        return {"rel_state": None, "rel_rule": "rs_history_too_short",
                "rel_missing": f"fewer than {RS_MA + RS_LOOK + 1} common weekly closes with the benchmark"}
    m = rs.rolling(RS_MA).mean()
    c = float(m.iloc[-1] / m.iloc[-1 - RS_LOOK] - 1)
    st = "Outperform" if c > 0 else "Underperform" if c < 0 else "Neutral"
    return {"rel_state": st, "rel_rule": {"Outperform": "rs_ma40w_rising", "Underperform": "rs_ma40w_falling", "Neutral": "rs_ma40w_unchanged"}[st],
            "rel_missing": None}
