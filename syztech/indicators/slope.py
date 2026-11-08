"""Slope of a moving average, read at the right edge."""
import pandas as pd

RISING, FALLING, FLAT = "rising", "falling", "flat"


def slope_ratio(ma: pd.Series, lookback: int = 20) -> pd.Series:
    """MA[t] / MA[t - lookback] - 1."""
    return ma / ma.shift(lookback) - 1.0


def classify(ratio: float, flat_band: float) -> str | None:
    """rising if > +flat_band, falling if < -flat_band, else flat. None when not computable."""
    if ratio is None or pd.isna(ratio):
        return None
    if ratio > flat_band:
        return RISING
    if ratio < -flat_band:
        return FALLING
    return FLAT


def slope_state(ma: pd.Series, lookback: int, flat_band: float) -> pd.Series:
    """Slope classification for every bar (object Series of rising/falling/flat/None)."""
    return slope_ratio(ma, lookback).map(lambda r: classify(r, flat_band))
