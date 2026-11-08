"""Synthetic close series built from segments (trend, range, break).

Segments are log-linear so a move of x% takes the same shape at any price level.
Every series gets a business-day DatetimeIndex; computations use bar positions only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


class Path:
    def __init__(self, start: float):
        self.values: list[float] = [float(start)]

    def to(self, end: float, bars: int) -> "Path":
        """Log-linear move from the last value to `end` over `bars` bars."""
        a = self.values[-1]
        steps = np.exp(np.linspace(np.log(a), np.log(end), bars + 1))[1:]
        self.values.extend(steps.tolist())
        return self

    def hold(self, bars: int) -> "Path":
        self.values.extend([self.values[-1]] * bars)
        return self

    def zigzag(self, points: list[float], bars_each: int) -> "Path":
        for p in points:
            self.to(p, bars_each)
        return self

    def oscillate(self, centre: float, amp: float, period: int, bars: int) -> "Path":
        t = np.arange(1, bars + 1)
        self.values.extend((centre * (1 + amp * np.sin(2 * np.pi * t / period))).tolist())
        return self

    def set_last(self, value: float) -> "Path":
        self.values[-1] = float(value)
        return self

    def append(self, value: float) -> "Path":
        self.values.append(float(value))
        return self

    def __len__(self):
        return len(self.values)

    def series(self, name: str = "TEST", end: str = "2026-11-06") -> pd.Series:
        idx = pd.bdate_range(end=end, periods=len(self.values))
        return pd.Series(self.values, index=idx, name=name, dtype=float)
