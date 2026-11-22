"""Indicator arithmetic against hand-computed values on a 30-bar series (small windows)."""
import math

import numpy as np

import pandas as pd
import pytest

from syztech.indicators.bands import band_events, bollinger_bandwidth, last_band, max_prior, min_prior
from syztech.indicators.crosses import cross_events, last_cross
from syztech.indicators.ma import sma
from syztech.indicators.slope import classify, slope_ratio

C = pd.Series([10, 11, 12, 13, 14, 15, 14, 13, 12, 11, 10, 9, 8, 9, 10,
               11, 12, 13, 14, 15, 16, 15, 14, 13, 12, 11, 10, 11, 12, 13], dtype=float)


def test_sma():
    m = sma(C, 3)
    assert m.iloc[:2].isna().all()
    assert m.iloc[2] == 11.0
    assert m.iloc[5] == 14.0
    assert m.iloc[12] == 9.0


def test_bands_exclude_current_bar():
    mx, mn = max_prior(C, 5), min_prior(C, 5)
    assert mx.iloc[:5].isna().all()
    assert mx.iloc[5] == 14.0 and mx.iloc[6] == 15.0
    assert mn.iloc[12] == 9.0


def test_band_events_and_last_band():
    up, lo = band_events(C, 5)
    # bar 15: 11 > max(10, 9, 8, 9, 10) = 10 → upper; bar 8: 12 < min(13, 14, 15, 14, 13) = 13 → lower
    assert list(up[up].index) == [5, 15, 16, 17, 18, 19, 20, 29]
    assert list(lo[lo].index) == [8, 9, 10, 11, 12, 23, 24, 25, 26]
    lb = last_band(C, 5)
    assert (lb.side, lb.pos, lb.level) == ("upper", 29, 12.0)     # bar 29: 13 > max(12, 11, 10, 11, 12) = 12
    lb26 = last_band(C.iloc[:27], 5)
    assert (lb26.side, lb26.pos, lb26.level) == ("lower", 26, 11.0)


def test_slope_ratio_and_classification():
    ma = pd.Series([100.0, 100.1, 100.3, 100.1])
    r = slope_ratio(ma, 2)
    assert r.iloc[2] == pytest.approx(0.003)
    assert classify(r.iloc[2], 0.002) == "rising"
    assert classify(r.iloc[3], 0.002) == "flat"           # +0.0% over 2 bars
    assert classify(-0.0021, 0.002) == "falling"
    assert classify(0.002, 0.002) == "flat"               # boundary is flat


def test_bollinger_bandwidth():
    bw = bollinger_bandwidth(pd.Series([1.0, 2.0, 3.0, 4.0]), window=4, k=2)
    assert bw.iloc[-1] == pytest.approx(4 * math.sqrt(1.25) / 2.5)
    assert bollinger_bandwidth(pd.Series([5.0] * 4), window=4).iloc[-1] == 0.0


def test_cross_events():
    fast = pd.Series([1, 1, 1, 3, 3, 1.0])
    slow = pd.Series([2, 2, 2, 2, 2, 2.0])
    assert cross_events(fast, slow).tolist() == [0, 0, 0, 1, 0, -1]


def test_golden_cross_requires_rising_slope():
    fast = pd.Series([1, 1, 1, 3, 3, 3.0])
    slow = pd.Series([2, 2, 2, 2, 2, 2.0])
    rising = pd.Series(["rising"] * 6)
    falling = pd.Series(["falling"] * 6)
    assert last_cross(fast, slow, rising, lookback=5).kind == "golden"
    c = last_cross(fast, slow, falling, lookback=5)
    assert (c.kind, c.direction, c.pos) == ("cross_unqualified", "golden", 3)
    assert last_cross(fast, slow, rising, lookback=2).kind == "none"   # outside the lookback


def test_death_cross_requires_falling_slope():
    fast = pd.Series([3, 3, 3, 1, 1.0])
    slow = pd.Series([2, 2, 2, 2, 2.0])
    assert last_cross(fast, slow, pd.Series(["falling"] * 5), 5).kind == "death"
    assert last_cross(fast, slow, pd.Series(["flat"] * 5), 5).kind == "cross_unqualified"


def test_relative_strength_trend():
    from syztech.indicators.rs import rs_summary, rs_trend
    idx = pd.bdate_range("2025-01-01", periods=300)
    bench = pd.Series(100.0, index=idx)
    up = pd.Series(np.linspace(100, 130, 300), index=idx)
    down = pd.Series(np.linspace(100, 70, 300), index=idx)
    assert rs_summary(up, bench)["rs_trend"] == "outperforming"
    assert rs_summary(down, bench)["rs_trend"] == "underperforming"
    assert rs_summary(up, bench)["rs_chg63"] > 0
    assert rs_trend(0.0) == "mixed" and rs_trend(0.001) == "outperforming" and rs_trend(-0.001) == "underperforming"
    # RS Mom is slow: a long outperformer that drops hard for 3 months keeps a rising RS 200-day
    idx2 = pd.bdate_range("2024-01-01", periods=400)
    fade = pd.Series(np.r_[np.linspace(100, 200, 340), np.linspace(200, 170, 60)], index=idx2)
    sm = rs_summary(fade, pd.Series(100.0, index=idx2))
    assert sm["rs_chg63"] < 0 and sm["rs_trend"] == "outperforming"
    assert rs_summary(up.iloc[:100], bench)["rs_trend"] is None      # not enough common history


def test_breadth_history_counts_only_measurable_stocks():
    import numpy as np
    import pandas as pd
    from syztech.indicators.breadth import breadth_history
    idx = pd.bdate_range("2020-01-01", periods=400)
    up = pd.Series(np.linspace(100, 200, 400), index=idx)           # rising 200-day, above it
    down = pd.Series(np.linspace(200, 100, 400), index=idx)         # falling 200-day, below it
    late = pd.Series(np.linspace(100, 200, 100), index=idx[-100:])  # too short to measure
    b = breadth_history({"U": up, "D": down, "L": late}, idx)
    assert b["n"].iloc[-1] == 2
    assert b["rising"].iloc[-1] == 50.0 and b["above"].iloc[-1] == 50.0
    assert b["rising"].iloc[:218].isna().all()                      # 200 bars for the average + 20 for the slope
    assert b["rising"].iloc[219] == 50.0


def test_swing_pivots_and_structure_on_a_staircase():
    import numpy as np
    import pandas as pd
    from syztech.research.swing import pivots, swing_history
    # up 20%, down 10%, up 20%, down 10% ... : higher highs and higher lows
    legs = []
    x = 100.0
    for _ in range(6):
        up = np.linspace(x, x * 1.2, 30); x = up[-1]
        dn = np.linspace(x, x * 0.9, 20); x = dn[-1]
        legs += [up, dn]
    s = pd.Series(np.concatenate(legs), index=pd.bdate_range("2020-01-01", periods=sum(len(l) for l in legs)))
    piv = pivots(s, np.full(len(s), 0.05))
    hs = [p[2] for p in piv if p[0] == "H"]; ls = [p[2] for p in piv if p[0] == "L"]
    assert all(b > a for a, b in zip(hs, hs[1:])) and all(b > a for a, b in zip(ls, ls[1:]))
    assert all(p[3] > p[1] for p in piv)                 # confirmed after the extreme, never on it
    h = swing_history(s, k=2.0)
    assert h.structure.dropna().iloc[-1] in ("up", "mixed")


def test_swing_break_of_last_low_downgrades_structure():
    import numpy as np
    import pandas as pd
    from syztech.research.swing import swing_history
    base = np.concatenate([np.linspace(100, 130, 120), np.linspace(130, 115, 60), np.linspace(115, 150, 120),
                           np.linspace(150, 135, 60), np.linspace(135, 170, 120), np.linspace(170, 120, 60)])
    s = pd.Series(base, index=pd.bdate_range("2020-01-01", periods=len(base)))
    h = swing_history(s, k=1.0)
    last = h.dropna(subset=["swing_low"]).iloc[-1]
    assert s.iloc[-1] < last.swing_low and last.structure != "up"
