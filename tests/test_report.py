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


def test_chart_badge_only_three_reference_visuals():
    from syztech.charts.syz_style import BADGE_FAMILY, BADGE_H, BADGE_SPEC, BADGE_W
    assert set(BADGE_SPEC) == {"Bullish", "Neutral", "Bearish"}
    assert BADGE_SPEC["Bullish"] == ("#3BAF90", "▲", "BULLISH")
    assert BADGE_SPEC["Neutral"] == ("#4B5F80", "◆", "NEUTRAL")
    assert BADGE_SPEC["Bearish"] == ("#AC5D85", "▼", "BEARISH")
    assert (BADGE_W, BADGE_H) == (1.18, 0.34)
    assert BADGE_FAMILY["Neutral+"] == BADGE_FAMILY["Neutral-"] == "Neutral" and BADGE_FAMILY["Bearish_LM"] == "Bearish"


def test_html_row_reads_the_name_column_of_a_series():
    import pandas as pd
    from syztech.report.sector_html import _row
    r = pd.Series(dict(ticker="SPI Index", name="SPI", industry=None, bucket=None, close=1.0, decimals=1, slope200="rising",
                       vs200=0.1, chg1m=0.0, chg3m=0.0, chg12m=0.0, from_hi52=0.0, rs_trend=None, rs_chg63=None,
                       verdict="Bullish", hi52=1.0, lo52=1.0, hi100=1.0, lo100=1.0), name=7)
    assert _row(r, {})["n"] == "SPI"


def _prices(series: dict):
    import pandas as pd
    from syztech.io.bloomberg_prices import LoadResult, SeriesReport
    rows = [pd.DataFrame({"date": s.index, "ticker": t, "close": s.to_numpy()}) for t, s in series.items()]
    return LoadResult(pd.concat(rows, ignore_index=True), {t: SeriesReport(t, "test", bars=len(s)) for t, s in series.items()}, [])


def test_ratio_series_uses_common_dates_and_is_rebased_to_100():
    import pandas as pd
    from syztech.report.sectorstyle import add_ratio
    idx = pd.bdate_range("2024-01-01", periods=5)
    a = pd.Series([10.0, 11, 12, 13, 14], index=idx)
    b = pd.Series([5.0, 5, 6, 6], index=idx[[0, 1, 2, 4]])          # no close on day 4: that day is left out, not filled
    p = _prices({"A": a, "B": b})
    key = add_ratio(p, "A", "B")
    r = p.series(key)
    assert list(r.index) == list(idx[[0, 1, 2, 4]])
    assert r.iloc[0] == 100.0 and abs(r.iloc[-1] - (14 / 6) / (10 / 5) * 100) < 1e-9


def test_rotation_point_coordinates():
    import numpy as np
    import pandas as pd
    from syztech.report.sectorstyle import rotation_points
    idx = pd.bdate_range("2023-01-02", periods=400)
    bench = pd.Series(100.0, index=idx)
    up = pd.Series(np.linspace(100, 140, 400), index=idx)           # steadily outperforming
    pts = rotation_points(_prices({"X": up, "B": bench}), ["X"], "B", tail=0)
    rs = up / bench * 100
    assert abs(pts.x.iloc[0] - (rs.iloc[-1] / rs.iloc[-200:].mean() - 1) * 100) < 1e-9
    assert abs(pts.y.iloc[0] - (rs.iloc[-1] / rs.iloc[-64] - 1) * 100) < 1e-9
    assert pts.x.iloc[0] > 0 and pts.y.iloc[0] > 0                    # "Leading" quadrant
