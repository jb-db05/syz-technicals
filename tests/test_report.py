"""Weekly document: trigger detection and distance formatting."""
import pandas as pd

from syztech.report.weekly import dist, triggers


def _row(**kw):
    base = dict(ticker="X", name="X", verdict="Bullish", close=100.0, decimals=1, asset_class="index",
                support=98.5, s_origin="chart", resistance=120.0, r_origin="52w high (2026-01-01)", trendline=None)
    base.update(kw)
    return base


def test_triggers_within_two_percent():
    df = pd.DataFrame([_row(ticker="A"), _row(ticker="B", support=90.0), _row(ticker="C", support=90.0, trendline=101.5),
                       _row(ticker="D", support=90.0, resistance=101.0)])
    t = triggers(df).set_index("ticker")
    assert set(t.index) == {"A", "C", "D"}
    assert t.loc["A", "kind"] == "Support" and t.loc["C", "kind"] == "Trendline"
    assert t.loc["D", "kind"] == "52-week high"


def test_distance_in_bp_for_yields():
    r = pd.Series(_row(asset_class="rate", close=4.86))
    assert dist(r, 5.02) == "–16bp"
    assert dist(pd.Series(_row()), 98.5) == "+1.5%"


def test_add_momentum_uses_closes_and_52w_high():
    from types import SimpleNamespace
    import numpy as np
    from syztech.report.sectordoc import add_momentum
    idx = pd.bdate_range("2025-01-01", periods=400)
    s = pd.Series(np.linspace(100, 200, 400), index=idx)
    prices = SimpleNamespace(series=lambda t: s)
    df = pd.DataFrame([dict(ticker="X", last_date=idx[-1], hi52=250.0)])
    out = add_momentum(df, prices).iloc[0]
    m1 = s[s.index <= idx[-1] - pd.DateOffset(months=1)].iloc[-1]
    assert out.chg1m == 200 / m1 - 1
    assert abs(out.from_hi52 - (200 / 250 - 1)) < 1e-12
    assert out.chg12m > 0
