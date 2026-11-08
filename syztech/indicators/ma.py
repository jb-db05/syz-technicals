"""Simple moving averages. Always rebuilt from unrounded closes, never read from exports."""
import pandas as pd


def sma(close: pd.Series, window: int) -> pd.Series:
    """Simple moving average; NaN until `window` bars are available."""
    return close.rolling(window, min_periods=window).mean()
