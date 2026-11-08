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
