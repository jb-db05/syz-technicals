"""Exceptions report (BUILD_SPEC §3.4)."""
import pandas as pd
import pytest

from syztech.trend.exceptions import classify_frame, compare, levels_stale, render_markdown, trigger_crossed


@pytest.mark.parametrize("mech,badge,expected", [
    ("Bullish", "Bullish", "agree"),
    ("Neutral", "Neutral+", "tilt_only"),
    ("Neutral-", "Neutral+", "tilt_only"),
    ("Bearish_LM", "Bearish", "tilt_only"),
    ("Neutral-", "Bearish", "one_step"),
    ("Neutral+", "Bullish", "one_step"),
    ("Bullish", "Neutral", "conflict"),          # two rungs apart
    ("Bullish", "Bearish", "conflict"),
    ("Bearish", "Neutral+", "conflict"),
    ("Bullish", None, "no_badge"),
    ("insufficient_data", "Bullish", "not_scored"),
])
def test_compare(mech, badge, expected):
    assert compare(mech, badge) == expected


def _s(values, start="2026-10-26"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), dtype=float)


def test_trigger_crossed_after_badge_only():
    s = _s([101, 102, 101, 100.5, 99.9, 100.2])          # badge on day 3 (Wed 28 Oct)
    hit = trigger_crossed(s, 100.0, None, "2026-10-28")
    assert hit[0] == "close below support" and str(hit[1]) == "2026-10-30"
    assert trigger_crossed(s, 100.0, None, "2026-11-02") is None          # already below at badge date
    assert trigger_crossed(s, 99.9, None, "2026-10-28") is None           # exactly at the level: not crossed
    assert trigger_crossed(s, None, 101.5, "2026-10-28") is None
    assert trigger_crossed(_s([100, 101, 103]), None, 102, "2026-10-26")[0] == "close above resistance"


def test_levels_stale():
    assert levels_stale("2026-10-01", "2026-11-06", True)
    assert not levels_stale("2026-10-20", "2026-11-06", True)
    assert not levels_stale(None, "2026-11-06", False)
    assert levels_stale(None, "2026-11-06", True)


def _scores():
    base = dict(name="X", group="G", decimals=1, ma200=100.0, ma50=101.0, slope200="rising", slope200_pct=0.01,
                price_vs_200="above", last_band="upper", last_band_date="2026-09-01", last_band_level=99.0,
                structure="intact", structure_event=None, structure_date=None, cross="none", cross_date=None,
                missing=None, support=None, resistance=None, levels_asof=None, badge_asof="2026-11-02", close=110.0)
    rows = [dict(base, ticker="A", verdict="Bullish", rule="rising_support_intact", badge="Bullish"),
            dict(base, ticker="B", verdict="Bullish", rule="rising_support_intact", badge="Bearish"),
            dict(base, ticker="C", verdict="Neutral+", rule="rising_support_broken", badge="Neutral",
                 structure="support_broken", structure_date="2026-10-01"),
            dict(base, ticker="D", verdict="Bullish", rule="rising_support_intact", badge="Bullish",
                 support=105.0, levels_asof="2026-11-02"),
            dict(base, ticker="E", verdict="Bullish", rule="rising_support_intact", badge="Bullish",
                 support=50.0, levels_asof="2026-08-01")]
    return pd.DataFrame(rows)


def test_sections_and_markdown():
    closes = {"D": _s([108, 107, 106, 104.9, 106], start="2026-10-29")}
    ex = classify_frame(_scores(), closes, "2026-11-04").set_index("ticker")
    assert ex.loc["A", "section"] == "agree"
    assert ex.loc["B", "section"] == "conflict"
    assert ex.loc["C", "section"] == "tilt_only"
    assert ex.loc["D", "section"] == "trigger_hit"
    assert ex.loc["E", "section"] == "levels_stale"
    assert ex.loc["A", "reason"].startswith("200d rising, no band break in force")
    assert ex.loc["D", "reason"] == "200d rising, support 105.0 intact → Bullish; badge Bullish"
    md = render_markdown(ex.reset_index(), "2026-11-04")
    order = [md.index(h) for h in ("## Trigger hit", "## Conflict", "## Tilt only", "## Levels stale", "## Agree: 1")]
    assert order == sorted(order)
    assert "—" not in md                          # en dashes only
