"""Named synthetic fixtures for BUILD_SPEC §3.6.

Each returns (close Series, kwargs for `evaluate`). Shapes were chosen so the stated
conditions hold at the last bar; the tests assert those conditions as well as the verdict,
so a fixture that drifts away from its description fails loudly.
"""
from .builders import Path

RANGE_LOWER_HIGHS = [73.8, 71, 73.6, 71.2, 73.4, 71.4, 73.2, 71.6, 73.0, 71.8]


def csi300_falling_ma_intact_structure():
    s = Path(100).to(70, 250).zigzag(RANGE_LOWER_HIGHS, 15).series("SHSZ300 Index")
    return s, dict(support=68.0)


def csi300_death_cross_after_support_break():
    s = (Path(100).to(70, 250).zigzag(RANGE_LOWER_HIGHS[:-1], 15)
         .to(70.0, 14).append(67.9).series("SHSZ300 Index"))
    return s, dict(support=68.0)


def jpm_adxy_falling_ma_broken_support():
    s = Path(100).to(80, 300).zigzag([82, 80.5, 81.5], 30).to(79.5, 9).series("ADXY Index")
    return s, {}


def unicaja_rising_ma_minor_low_lost():
    # MAX100 breaks into bar 340, minor swing low 95, then a dip to 94.5 (minor low lost)
    s = Path(50).to(100, 340).zigzag([95, 98, 94.5, 96], 15).series("UNI SM Equity")
    return s, {}


def smfg_rising_ma_minor_low_lost():
    s = Path(50).to(100, 340).zigzag([95, 98, 94.5, 96], 15).series("8316 JT Equity")
    bench = Path(1000).to(1800, 340).zigzag([1750, 1820, 1780, 1810], 15).series("TPX Index")
    return s, dict(benchmark=bench)


def alphabet_rising_ma_lower_highs():
    # peak 100, then lower highs 98 / 96.5 / 96 with rising lows – no MIN100 break
    s = Path(50).to(100, 300).zigzag([94, 98, 94.5, 96.5, 95, 96], 16).series("GOOGL US Equity")
    bench = Path(4000).to(6000, 300).to(6600, 96).series("SPX Index")   # benchmark keeps rising → RS falls
    return s, dict(benchmark=bench)


def gold_rising_ma_below_price_support_holds():
    s = Path(50).to(100, 300).to(82, 99).series("XAU Curncy")
    return s, dict(support=78.0)


def _usdbrl_base(last_leg_bars=49):
    return Path(150).to(90, 250).hold(50).to(105, 20).to(85, 30).to(100, last_leg_bars)


def usdbrl_falling_ma_price_above_higher_lows():
    return _usdbrl_base().series("USDBRL Curncy"), dict(resistance=108.0)


def usdbrl_resistance_break_slope_still_falling():
    return _usdbrl_base(44).to(109, 5).series("USDBRL Curncy"), dict(resistance=108.0)


def crypto_golden_cross_hooked_ma_resistance_break():
    # MA200 falls for 160 bars, still falling 20 bars before the end, then hooks up;
    # golden cross at bar 395 with the slope already rising; MAX100 break on the last bar.
    s = Path(150).to(60, 210).to(90, 40).to(60, 110).to(110, 39).series("XBTUSD Curncy")
    return s, {}


def eurusd_falling_ma_support_intact():
    s = (Path(1.20).to(1.05, 300)
         .zigzag([1.068, 1.052, 1.066, 1.054, 1.064, 1.056], 16).series("EURUSD Curncy"))
    return s, dict(support=1.0350)


def dxy_flat_or_rising_ma_below_resistance():
    s = Path(90).to(106, 330).zigzag([103.5, 105, 103.8, 104.6], 17).series("DXY Curncy")
    return s, dict(support=100.0, resistance=107.5)


def _rolled_over():
    # mirror of the crypto shape: MA200 rolls over first, then a qualified death cross (bar 396)
    return Path(20).to(50, 210).to(33.3, 40).to(50, 110).to(27.3, 39).series("XAG Curncy")


def silver_close_below_trigger():
    s = _rolled_over()
    return s, dict(support=27.4)          # last close 27.3: one tick (0.1) below; prior close 27.7 above


def gold_close_above_floor():
    s = _rolled_over().rename("XAU Curncy")
    return s, dict(support=27.2)          # last close 27.3 above the floor


def cac40_declining_ma_death_cross_range_intact():
    s = _rolled_over().rename("CAC Index")
    return s, dict(support=round(s.iloc[-1] / 1.06, 2))   # price ~6% above drawn support


def eurchf_flat_ma_small_support_loss():
    support = 0.9271
    s = (Path(0.9400).oscillate(0.9400, 0.004, 60, 300).to(0.9300, 90).to(0.9285, 8)
         .append(support * (1 - 0.004)).series("EURCHF Curncy"))
    return s, dict(support=support)


def slope_reads_right_edge():
    # MA200 falls bar-on-bar for 150 bars, then rises bar-on-bar for the last 25
    return Path(150).to(100, 150).to(70, 199).to(130, 50).series("TEST"), {}


def insufficient_history():
    return Path(100).to(120, 249).series("TEST"), {}
