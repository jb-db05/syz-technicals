"""100-day band structure (highest / lowest close of the prior N bars) and Bollinger bandwidth."""
from dataclasses import dataclass

import numpy as np
import pandas as pd

UPPER, LOWER, NONE = "upper", "lower", "none"


def max_prior(close: pd.Series, window: int = 100) -> pd.Series:
    """Highest close of the prior `window` bars, excluding the current bar."""
    return close.shift(1).rolling(window, min_periods=window).max()


def min_prior(close: pd.Series, window: int = 100) -> pd.Series:
    """Lowest close of the prior `window` bars, excluding the current bar."""
    return close.shift(1).rolling(window, min_periods=window).min()


def band_events(close: pd.Series, window: int = 100) -> tuple[pd.Series, pd.Series]:
    """Boolean Series: close above MAX(window) / close below MIN(window). Strict inequalities."""
    upper = (close > max_prior(close, window)).fillna(False)
    lower = (close < min_prior(close, window)).fillna(False)
    return upper.astype(bool), lower.astype(bool)


@dataclass(frozen=True)
class LastBand:
    side: str                 # upper / lower / none
    pos: int | None           # integer trading-day position of the event bar
    level: float | None       # the MAX100 / MIN100 level that was broken


def last_band(close: pd.Series, window: int = 100) -> LastBand:
    """Most recent band event in the available history."""
    upper, lower = band_events(close, window)
    hi = np.flatnonzero(upper.to_numpy())
    lo = np.flatnonzero(lower.to_numpy())
    last_hi = hi[-1] if hi.size else -1
    last_lo = lo[-1] if lo.size else -1
    if last_hi < 0 and last_lo < 0:
        return LastBand(NONE, None, None)
    if last_hi > last_lo:
        return LastBand(UPPER, int(last_hi), float(max_prior(close, window).iloc[last_hi]))
    return LastBand(LOWER, int(last_lo), float(min_prior(close, window).iloc[last_lo]))


def bollinger_bandwidth(close: pd.Series, window: int = 100, k: float = 2.0) -> pd.Series:
    """(UBB - LBB) / ((UBB + LBB) / 2), population standard deviation."""
    mid = close.rolling(window, min_periods=window).mean()
    sd = close.rolling(window, min_periods=window).std(ddof=0)
    upper, lower = mid + k * sd, mid - k * sd
    return (upper - lower) / ((upper + lower) / 2.0)
