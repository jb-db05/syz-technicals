"""Relative strength versus benchmark. Informational only – never enters the verdict."""
import pandas as pd

from .ma import sma
from .slope import RISING, FALLING, FLAT


def relative_strength(close: pd.Series, benchmark: pd.Series) -> pd.Series:
    """close / benchmark x 100 on common dates (no filling)."""
    both = pd.concat([close, benchmark], axis=1, join="inner").dropna()
    return both.iloc[:, 0] / both.iloc[:, 1] * 100.0


OUTPERFORMING, UNDERPERFORMING, MIXED = "outperforming", "underperforming", "mixed"


def rs_trend(vs_ma200: str, slope63: str) -> str:
    """outperforming: RS above its 200d and rising over 63 days; underperforming: below and falling; else mixed."""
    if vs_ma200 == "above" and slope63 == RISING:
        return OUTPERFORMING
    if vs_ma200 == "below" and slope63 == FALLING:
        return UNDERPERFORMING
    return MIXED


def rs_summary(close: pd.Series, benchmark: pd.Series, ma_window: int = 200, slope_window: int = 63) -> dict:
    rs = relative_strength(close, benchmark)
    if len(rs) <= max(ma_window, slope_window):
        return {"rs": None, "rs_ma200": None, "rs_slope63": None, "rs_vs_ma200": None, "rs_chg63": None, "rs_trend": None}
    ma = sma(rs, ma_window)
    chg = rs.iloc[-1] / rs.iloc[-1 - slope_window] - 1.0
    sign = RISING if chg > 0 else FALLING if chg < 0 else FLAT
    vs = "above" if rs.iloc[-1] > ma.iloc[-1] else "below"
    return {
        "rs": float(rs.iloc[-1]),
        "rs_ma200": float(ma.iloc[-1]),
        "rs_slope63": sign,
        "rs_vs_ma200": vs,
        "rs_chg63": float(chg),
        "rs_trend": rs_trend(vs, sign),
    }
