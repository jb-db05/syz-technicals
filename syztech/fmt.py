"""Number formatting: thousands separator, fixed decimals per instrument, en dash for missing."""
import math

EN_DASH = "–"


def num(x, decimals: int = 1) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return EN_DASH
    return f"{x:,.{int(decimals)}f}"


def pct(x, decimals: int = 2) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return EN_DASH
    return f"{x * 100:+.{decimals}f}%"
