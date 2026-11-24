"""Thematic review helpers: duplicate sets, cluster composite (no filling), momentum score."""
import numpy as np
import pandas as pd

from syztech.report.thematic import composite, dedupe, momentum_score


def test_dedupe_keeps_the_fund_then_the_longest_history():
    order = ["AAA Index", "AAA US Equity", "BBB US Equity", "CCC LN Equity"]
    C = pd.DataFrame(np.eye(4), index=order, columns=order)
    C.loc["AAA Index", "AAA US Equity"] = C.loc["AAA US Equity", "AAA Index"] = 0.99      # an index and its ETF
    C.loc["BBB US Equity", "CCC LN Equity"] = C.loc["CCC LN Equity", "BBB US Equity"] = 0.96  # two listings
    keep, dropped = dedupe(order, C, {"AAA Index": 2000, "AAA US Equity": 900, "BBB US Equity": 800, "CCC LN Equity": 1500})
    assert set(keep) == {"AAA US Equity", "CCC LN Equity"}
    assert dropped == {"AAA US Equity": ["AAA Index"], "CCC LN Equity": ["BBB US Equity"]}


def test_composite_is_equal_weight_and_never_fills():
    idx = pd.bdate_range("2024-01-01", periods=6)
    a = pd.Series([100, 101, 102, 103, 104, 105.0], index=idx)
    b = pd.Series([50, 50.5, np.nan, 51.5, 52, 52.5], index=idx)          # one missing close
    c = composite({"a": a, "b": b})
    ra, rb = np.log(a).diff(), np.log(b.dropna()).diff()
    assert np.isclose(np.log(c.iloc[0] / 100), (ra.iloc[1] + rb.iloc[1]) / 2)      # both members
    # the day b is missing: a alone; the day b comes back its two-day move is one return, not spread or invented
    assert len(c) == 5 and np.isclose(np.log(c.iloc[1] / c.iloc[0]), ra.iloc[2])


def test_momentum_score_sign_and_short_history():
    idx = pd.bdate_range("2023-01-02", periods=300)
    rng = np.random.default_rng(1)
    b = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.008, 300))), index=idx)
    up = b * np.exp(np.linspace(0, 0.3, 300)) * np.exp(np.cumsum(rng.normal(0, 0.004, 300)))
    down = b * np.exp(np.linspace(0, -0.3, 300)) * np.exp(np.cumsum(rng.normal(0, 0.004, 300)))
    assert momentum_score(up, b)["mom"] > 0 > momentum_score(down, b)["mom"]
    assert momentum_score(up, b)["rs12"] > 0
    assert momentum_score(up.iloc[:200], b)["mom"] is None and momentum_score(up.iloc[:200], b)["rs6"] is not None
    assert momentum_score(up.iloc[:50], b) == {"rs3": None, "rs6": None, "rs12": None, "mom": None}
