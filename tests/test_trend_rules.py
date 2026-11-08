"""One test per documented correction (BUILD_SPEC §3.6)."""
import pandas as pd
import pytest

from syztech.indicators.ma import sma
from syztech.indicators.rs import rs_summary
from syztech.trend.rules import (BEARISH, BEARISH_LM, BULLISH, INSUFFICIENT, NEUTRAL, NEUTRAL_NEG,
                                 NEUTRAL_POS, TrendParams, evaluate, structure_state)
from tests.fixtures import series as fx


def run(fixture):
    s, kw = fixture()
    bench = kw.pop("benchmark", None)
    return s, evaluate(s, **kw), bench


def test_csi300_falling_ma_intact_structure():
    s, r, _ = run(fx.csi300_falling_ma_intact_structure)
    snap = r.snapshot
    assert snap.slope200 == "falling"
    assert not snap.structure.support_broken
    assert snap.close > 68.0
    assert (r.verdict, r.rule) == (NEUTRAL_NEG, "falling_range_intact")


def test_csi300_death_cross_after_support_break():
    s, r, _ = run(fx.csi300_death_cross_after_support_break)
    assert r.snapshot.ma50 < r.snapshot.ma200
    assert r.snapshot.structure.support_broken
    assert (r.verdict, r.rule) == (BEARISH, "falling_support_broken")


def test_jpm_adxy_falling_ma_broken_support():
    s, r, _ = run(fx.jpm_adxy_falling_ma_broken_support)
    st = r.snapshot.structure
    assert st.support_source == "band-fallback" and st.resistance_source == "band-fallback"
    assert r.snapshot.last_band == "lower"
    assert (r.verdict, r.rule) == (BEARISH, "falling_support_broken")


@pytest.mark.parametrize("fixture", [fx.unicaja_rising_ma_minor_low_lost, fx.smfg_rising_ma_minor_low_lost])
def test_rising_ma_minor_low_lost(fixture):
    """SMFG rule: losing a minor swing low without a MIN100 break does not change the structure."""
    s, r, bench = run(fixture)
    assert r.snapshot.slope200 == "rising"
    assert r.snapshot.last_band == "upper"
    assert s.iloc[-16] < s.iloc[-46]          # the dip went below the prior minor swing low
    assert (r.verdict, r.rule) == (BULLISH, "rising_support_intact")
    if bench is not None:
        assert rs_summary(s, bench)["rs"] is not None


def test_alphabet_rising_ma_lower_highs():
    s, r, bench = run(fx.alphabet_rising_ma_lower_highs)
    assert r.snapshot.slope200 == "rising"
    assert r.snapshot.last_band == "upper"            # no MIN100 break since the peak
    assert rs_summary(s, bench)["rs_slope63"] == "falling"   # RS negative – informational only
    assert (r.verdict, r.rule) == (BULLISH, "rising_support_intact")


def test_gold_rising_ma_below_price_support_holds():
    s, r, _ = run(fx.gold_rising_ma_below_price_support_holds)
    assert r.snapshot.slope200 == "rising"
    assert r.snapshot.price_vs_200 == "below"
    assert not r.snapshot.structure.support_broken
    assert (r.verdict, r.rule) == (BULLISH, "rising_support_intact")


def test_usdbrl_falling_ma_price_above_higher_lows():
    s, r, _ = run(fx.usdbrl_falling_ma_price_above_higher_lows)
    snap = r.snapshot
    assert snap.slope200 == "falling"
    assert snap.price_vs_200 == "above"
    assert snap.ma50_slope_ratio > 0
    assert snap.structure.support_broken and snap.structure.event == "close below MIN100"
    assert snap.close < 108.0
    assert (r.verdict, r.rule) == (BEARISH_LM, "falling_losing_momentum")


def test_usdbrl_resistance_break_slope_still_falling():
    s, r, _ = run(fx.usdbrl_resistance_break_slope_still_falling)
    assert r.snapshot.slope200 == "falling"
    assert r.snapshot.structure.resistance_broken
    assert (r.verdict, r.rule) == (NEUTRAL, "falling_resistance_broken")


def test_crypto_golden_cross_hooked_ma_resistance_break():
    s, r, _ = run(fx.crypto_golden_cross_hooked_ma_resistance_break)
    snap = r.snapshot
    ma = sma(s, 200)
    assert ma.iloc[-21] / ma.iloc[-41] - 1 < -0.002          # still falling 20 bars before the end
    assert snap.slope200 == "rising"                          # hooked up at the right edge
    assert snap.cross == "golden" and snap.cross_pos >= len(s) - 40
    assert snap.last_band == "upper" and snap.last_band_pos == len(s) - 1
    assert (r.verdict, r.rule) == (BULLISH, "rising_support_intact")


def test_eurusd_falling_ma_support_intact():
    s, r, _ = run(fx.eurusd_falling_ma_support_intact)
    assert r.snapshot.slope200 == "falling" and r.snapshot.price_vs_200 == "below"
    assert (r.verdict, r.rule) == (NEUTRAL_NEG, "falling_range_intact")


def test_dxy_flat_or_rising_ma_below_resistance():
    s, r, _ = run(fx.dxy_flat_or_rising_ma_below_resistance)
    assert r.snapshot.slope200 == "rising" and r.snapshot.close < 107.5
    assert (r.verdict, r.rule) == (BULLISH, "rising_support_intact")


def test_silver_close_below_trigger():
    s, r, _ = run(fx.silver_close_below_trigger)
    assert r.snapshot.slope200 == "falling" and r.snapshot.cross == "death"
    assert s.iloc[-2] > 27.4 > s.iloc[-1]                     # break happens on the last close
    assert (r.verdict, r.rule) == (BEARISH, "falling_support_broken")


def test_gold_close_above_floor():
    s, r, _ = run(fx.gold_close_above_floor)
    assert r.snapshot.cross == "death" and s.iloc[-1] > 27.2
    assert (r.verdict, r.rule) == (NEUTRAL_NEG, "falling_range_intact")


def test_cac40_declining_ma_death_cross_range_intact():
    """A death cross does not confirm Bearish while the drawn support holds (CAC 40, 1 Nov 2026)."""
    s, r, _ = run(fx.cac40_declining_ma_death_cross_range_intact)
    _, kw = fx.cac40_declining_ma_death_cross_range_intact()
    assert r.snapshot.cross == "death"
    assert s.iloc[-1] / kw["support"] - 1 == pytest.approx(0.06, abs=0.001)
    assert (r.verdict, r.rule) == (NEUTRAL_NEG, "falling_range_intact")


def test_eurchf_flat_ma_small_support_loss():
    """OPEN DECISION (§3.3 flat branch). Default: flat + support broken + MA50 < MA200 → Bearish.
    EUR/CHF on 25 Oct 2026 was held at Neutral- by the analyst. Change this test with the rule."""
    s, r, _ = run(fx.eurchf_flat_ma_small_support_loss)
    snap = r.snapshot
    assert snap.slope200 == "flat"
    assert snap.ma50 < snap.ma200
    assert 1 - snap.close / 0.9271 == pytest.approx(0.004, abs=1e-6)
    assert (r.verdict, r.rule) == (BEARISH, "flat_support_broken_ma50_below")


def test_slope_reads_right_edge():
    s, _ = fx.slope_reads_right_edge()
    d = sma(s, 200).diff()
    assert (d.iloc[-175:-25] < 0).all() and (d.iloc[-25:] > 0).all()
    r = evaluate(s)
    assert r.snapshot.slope200 == "rising"


def test_insufficient_history():
    s, _ = fx.insufficient_history()
    r = evaluate(s)
    assert len(s) == 250
    assert r.verdict == INSUFFICIENT and r.score is None
    assert "250 bars" in r.missing


# --- state-machine and trigger semantics (§3.2 / §3.3 notes) --------------------------


def test_close_exactly_at_trigger_is_not_broken():
    s, _ = fx.silver_close_below_trigger()
    assert not structure_state(s, support=float(s.iloc[-1])).support_broken
    assert structure_state(s, support=float(s.iloc[-1]) + 1e-9).support_broken


def test_support_broken_is_a_state_not_last_bar():
    """Broken support stays broken after price recovers above it, until a resistance event."""
    s, kw = fx.csi300_death_cross_after_support_break()
    recovered = pd.concat([s, pd.Series([69.0, 70.0, 70.5], index=pd.bdate_range(s.index[-1], periods=4)[1:])])
    st = structure_state(recovered, support=68.0)
    assert recovered.iloc[-1] > 68.0 and st.support_broken


def test_flat_band_is_a_parameter():
    s, kw = fx.eurchf_flat_ma_small_support_loss()
    r = evaluate(s, params=TrendParams(flat_band=0.0005), **kw)
    assert r.snapshot.slope200 == "falling"


def test_levels_asof_limits_drawn_breaks():
    """A drawn support only counts from levels_asof: an older dip below it is not a break."""
    from tests.fixtures.builders import Path
    s = Path(60).to(110, 300).to(95, 30).to(104, 40).series()   # dip to 95 below support 100, never reset
    assert evaluate(s, support=100.0, levels_asof=s.index[0]).verdict == NEUTRAL_POS
    assert evaluate(s, support=100.0, levels_asof=s.index[-10]).verdict == BULLISH
