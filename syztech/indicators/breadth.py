"""Breadth of a list of stocks over time: share in an uptrend (200-day average rising) and above the 200-day.

Each stock is measured on its own closes; a stock counts on a date only once its 200-day average and the
20-day slope exist (no filling). The denominator is the number of stocks measurable on that date.
"""
from __future__ import annotations

import pandas as pd

from .ma import sma
from .slope import slope_ratio


def breadth_history(closes: dict[str, pd.Series], index: pd.DatetimeIndex, *, window: int = 200, lookback: int = 20,
                    flat_band: float = 0.002) -> pd.DataFrame:
    """Columns: rising (% with the 200-day average rising), above (% closing above it), n (stocks measured)."""
    rising, above = {}, {}
    for t, c in closes.items():
        c = c.dropna()
        ma = sma(c, window)
        r = slope_ratio(ma, lookback)
        ok = r.notna()
        rising[t] = (r > flat_band).where(ok).reindex(index)
        above[t] = (c > ma).where(ok).reindex(index)
    R, A = pd.DataFrame(rising, index=index, dtype=float), pd.DataFrame(above, index=index, dtype=float)
    n = R.notna().sum(axis=1)
    out = pd.DataFrame({"rising": R.sum(axis=1) / n * 100, "above": A.sum(axis=1) / n * 100, "n": n}, index=index)
    return out.where(n > 0)
