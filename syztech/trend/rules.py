"""House doctrine (BUILD_SPEC §3.2–3.3) as mechanical rules.

The engine works on a trading-day integer axis: every lookback below is a count of bars,
never of calendar days.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..indicators.bands import LOWER, NONE, UPPER, bollinger_bandwidth, last_band, max_prior, min_prior
from ..indicators.crosses import DEATH, GOLDEN, last_cross
from ..indicators.ma import sma
from ..indicators.slope import FALLING, FLAT, RISING, classify, slope_ratio, slope_state

# ---------------------------------------------------------------------------
# Parameters – the only place these numbers live.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrendParams:
    ma_long: int = 200
    ma_short: int = 50
    band_window: int = 100
    slope_lookback: int = 20
    flat_band: float = 0.0020        # 0.20% over 20 bars; to be calibrated against Florian's calls
    cross_lookback: int = 40
    bb_window: int = 100
    bb_k: float = 2.0
    min_history: int = 320           # 200 (MA) + 100 (band) + 20 (slope)
    levels_lookback: int = 100       # drawn-level breaks count from this many bars before levels_asof


DEFAULT_PARAMS = TrendParams()

# Verdicts and score mapping (§3.3)
BULLISH, NEUTRAL_POS, NEUTRAL, NEUTRAL_NEG, BEARISH_LM, BEARISH = (
    "Bullish", "Neutral+", "Neutral", "Neutral-", "Bearish_LM", "Bearish")
INSUFFICIENT = "insufficient_data"
SCORE = {BULLISH: 2, NEUTRAL_POS: 1, NEUTRAL: 0, NEUTRAL_NEG: -1, BEARISH_LM: -1, BEARISH: -2}

# Structure states
SUPPORT_BROKEN, RESISTANCE_BROKEN, INTACT = "support_broken", "resistance_broken", "intact"

# ---------------------------------------------------------------------------
# Structure (§3.2): a state machine over the history, not a look at the last bar.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Structure:
    state: str                     # support_broken / resistance_broken / intact
    event_pos: int | None          # bar of the event that set the current state
    event: str | None              # what that event was (human readable)
    support_source: str            # drawn / band-fallback
    resistance_source: str

    @property
    def support_broken(self) -> bool:
        return self.state == SUPPORT_BROKEN

    @property
    def resistance_broken(self) -> bool:
        return self.state == RESISTANCE_BROKEN


def structure_state(close: pd.Series, params: TrendParams = DEFAULT_PARAMS,
                    support: float | None = None, resistance: float | None = None,
                    levels_start: int = 0) -> Structure:
    """Current structure state from the most recent structural event.

    Each side uses its drawn level when one exists, else the 100-day band (§3.2):
      * support side   – drawn: close < support;     fallback: close < MIN100
      * resistance side – drawn: close > resistance; fallback: close > MAX100
    A close exactly at a drawn level is not a break.

    When a side has a drawn level, a band break on that side does not set the state
    (the drawn level has priority) but it does reset the opposite state: a MIN100 break
    cancels an old `resistance_broken`, a MAX100 break cancels an old `support_broken`
    (§3.3 note: "stays broken until ... a MAX100 break or a close above the drawn
    resistance resets the structure").

    Drawn-level breaks are counted from `levels_start` (levels_asof minus `levels_lookback` bars) onward.
    """
    c = close.to_numpy(dtype=float)
    n = len(c)
    hi_band = np.nan_to_num(c > max_prior(close, params.band_window).to_numpy(), nan=0).astype(bool)
    lo_band = np.nan_to_num(c < min_prior(close, params.band_window).to_numpy(), nan=0).astype(bool)
    in_window = np.arange(n) >= levels_start

    has_s, has_r = support is not None, resistance is not None
    drawn_s = (c < support) & in_window if has_s else np.zeros(n, bool)
    drawn_r = (c > resistance) & in_window if has_r else np.zeros(n, bool)

    # Event code per bar. Drawn breaks outrank band breaks on the same bar.
    #  +2 resistance broken, -2 support broken, 0 reset to intact, nan no event
    code = np.full(n, np.nan)
    code[hi_band] = 0.0 if has_r else 2.0
    code[lo_band] = 0.0 if has_s else -2.0
    code[drawn_r] = 2.0
    code[drawn_s] = -2.0

    ev = np.flatnonzero(~np.isnan(code))
    s_src = "drawn" if has_s else "band-fallback"
    r_src = "drawn" if has_r else "band-fallback"
    if ev.size == 0:
        return Structure(INTACT, None, None, s_src, r_src)
    p = int(ev[-1])
    k = code[p]
    if k == -2.0:
        what = f"close below drawn support {support}" if drawn_s[p] else "close below MIN100"
        return Structure(SUPPORT_BROKEN, p, what, s_src, r_src)
    if k == 2.0:
        what = f"close above drawn resistance {resistance}" if drawn_r[p] else "close above MAX100"
        return Structure(RESISTANCE_BROKEN, p, what, s_src, r_src)
    what = "MAX100 break (resets support state)" if hi_band[p] else "MIN100 break (resets resistance state)"
    return Structure(INTACT, p, what, s_src, r_src)


# ---------------------------------------------------------------------------
# Indicator snapshot at the last bar (§3.1)
# ---------------------------------------------------------------------------


@dataclass
class Snapshot:
    n_bars: int
    close: float
    ma200: float
    ma50: float
    slope200_ratio: float
    slope200: str | None
    ma50_slope_ratio: float
    price_vs_200: str
    cross: str
    cross_direction: str | None
    cross_pos: int | None
    last_band: str
    last_band_pos: int | None
    last_band_level: float | None
    bbw100: float | None
    target: float | None
    structure: Structure


def snapshot(close: pd.Series, params: TrendParams = DEFAULT_PARAMS,
             support: float | None = None, resistance: float | None = None,
             levels_start: int = 0) -> Snapshot:
    ma200 = sma(close, params.ma_long)
    ma50 = sma(close, params.ma_short)
    s200 = slope_state(ma200, params.slope_lookback, params.flat_band)
    r200 = slope_ratio(ma200, params.slope_lookback)
    r50 = slope_ratio(ma50, params.slope_lookback)
    cr = last_cross(ma50, ma200, s200, params.cross_lookback)
    lb = last_band(close, params.band_window)
    bbw = target = None
    if lb.side != NONE:
        bbw = float(bollinger_bandwidth(close, params.bb_window, params.bb_k).iloc[lb.pos])
        target = lb.level * (1 + bbw) if lb.side == UPPER else lb.level * (1 - bbw)
    last = close.iloc[-1]
    return Snapshot(
        n_bars=len(close), close=float(last), ma200=float(ma200.iloc[-1]), ma50=float(ma50.iloc[-1]),
        slope200_ratio=float(r200.iloc[-1]), slope200=classify(r200.iloc[-1], params.flat_band),
        ma50_slope_ratio=float(r50.iloc[-1]),
        price_vs_200="above" if last > ma200.iloc[-1] else "below",
        cross=cr.kind, cross_direction=cr.direction, cross_pos=cr.pos,
        last_band=lb.side, last_band_pos=lb.pos, last_band_level=lb.level,
        bbw100=bbw, target=target,
        structure=structure_state(close, params, support, resistance, levels_start),
    )


# ---------------------------------------------------------------------------
# Verdict rules (§3.3) – first match wins.
#
# Order confirmed by Florian (BUILD_SPEC §3.3, 8 Nov 2026): Bearish_LM before Bearish,
# falling + resistance broken (Neutral) before falling + intact (Neutral-).
# Rising + resistance broken is covered by rising_support_intact.
# ---------------------------------------------------------------------------


LT_VIEW = {"rising_support_broken_death_cross": "Neutral – 200d rising"}


def _rules(s: Snapshot):
    st = s.structure
    sb, rb = st.support_broken, st.resistance_broken
    up = s.slope200 == RISING
    dn = s.slope200 == FALLING
    fl = s.slope200 == FLAT
    return [
        ("rising_support_intact", up and not sb, BULLISH),
        # Short-term Bearish, long-term Neutral stated alongside (lt_view) – KOSPI, 8 Nov 2026
        ("rising_support_broken_death_cross", up and sb and s.ma50 < s.ma200, BEARISH),
        ("rising_support_broken", up and sb, NEUTRAL_POS),
        ("falling_losing_momentum", dn and sb and s.price_vs_200 == "above" and s.ma50_slope_ratio > 0, BEARISH_LM),
        ("falling_support_broken", dn and sb and not rb, BEARISH),
        ("falling_resistance_broken", dn and rb, NEUTRAL),
        ("falling_range_intact", dn and not sb, NEUTRAL_NEG),
        # Flat branch (confirmed): support broken + MA50 below or rolling over → Bearish, no minimum break size.
        ("flat_support_broken_ma50_weak", fl and sb and (s.ma50 < s.ma200 or s.ma50_slope_ratio < 0), BEARISH),
        ("flat_negative", fl and (sb or s.cross == DEATH or s.price_vs_200 == "below"), NEUTRAL_NEG),
        ("flat_positive", fl and (rb or s.cross == GOLDEN or s.price_vs_200 == "above"), NEUTRAL_POS),
        ("flat_neutral", True, NEUTRAL),
    ]


@dataclass
class TrendResult:
    verdict: str
    rule: str
    score: int | None
    snapshot: Snapshot | None = None
    missing: str | None = None
    lt_view: str | None = None       # long-term view stated alongside a short-term verdict
    extras: dict = field(default_factory=dict)


def evaluate(close: pd.Series, params: TrendParams = DEFAULT_PARAMS,
             support: float | None = None, resistance: float | None = None,
             levels_asof=None) -> TrendResult:
    """Mechanical verdict for one instrument. `close` is ascending, trading days only."""
    close = close.dropna()
    if len(close) < params.min_history:
        return TrendResult(INSUFFICIENT, "insufficient_history", None,
                           missing=f"price history: {len(close)} bars < {params.min_history} required")
    levels_start = 0
    if levels_asof is not None and not pd.isna(levels_asof) and isinstance(close.index, pd.DatetimeIndex):
        levels_start = max(0, int(close.index.searchsorted(pd.Timestamp(levels_asof))) - params.levels_lookback)
    snap = snapshot(close, params, support, resistance, levels_start)
    for rule, cond, verdict in _rules(snap):
        if cond:
            lt = LT_VIEW.get(rule)
            return TrendResult(verdict, rule, SCORE.get(verdict), snap, lt_view=lt)
    raise AssertionError("unreachable: flat_neutral always matches")
