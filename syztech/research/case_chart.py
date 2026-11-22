"""Research chart: price, 200-day average, confirmed swing points, and the verdict history under both rules."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..charts.syz_style import FONT, register_fonts
from .swing import family, monthly_move, pivots

COL = {"Bullish": "#3BAF90", "Neutral": "#B8BFCC", "Bearish": "#AC5D85"}


def case_chart(s: pd.Series, name: str, hist: pd.DataFrame, out: Path, k: float = 2.0, years: int = 3,
               bands=(("v0", "Current rule"), ("d1.5", "Recommended"))) -> Path:
    register_fonts()
    plt.rcParams["font.family"] = FONT
    s = s.dropna()
    piv = pivots(s, (k * monthly_move(s)).to_numpy())
    start = s.index[-1] - pd.DateOffset(years=years)
    i0 = int(s.index.searchsorted(start))
    x = np.arange(len(s))
    ma = s.rolling(200).mean()
    fig = plt.figure(figsize=(10.28, 5.0), dpi=200)
    ax = fig.add_axes([0.07, 0.30, 0.90, 0.62])
    ax.plot(x[i0:], s.iloc[i0:], color="#202945", lw=1.0)
    ax.plot(x[i0:], ma.iloc[i0:], color="#FF6C0E", lw=1.8, label="200-day average")
    for kind, ei, v, ci in piv:
        if ei >= i0:
            ax.scatter([ei], [v], s=26, zorder=3, color="#3BAF90" if kind == "L" else "#AC5D85", edgecolors="white", linewidths=0.6)
            ax.annotate(f"{'H' if kind == 'H' else 'L'} {v:,.0f}", (ei, v), xytext=(0, 7 if kind == "H" else -12),
                        textcoords="offset points", fontsize=7, ha="center", color="#202945")
    ax.set_yscale("log")
    from matplotlib.ticker import FuncFormatter, NullFormatter
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}" if v >= 10 else f"{v:,.2f}"))
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.set_xlim(i0, len(s) + 5)
    ax.set_title(f"{name}: swings confirmed by a {k:g}× one-month-move reversal (H / L)", fontsize=11, loc="left", color="#202945",
                 fontweight="bold")
    ax.tick_params(labelsize=7.5, colors="#4B5F80")
    ax.set_xticks([])
    ax.legend(loc="upper left", fontsize=8, frameon=False)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    h = hist[hist.date >= start]
    for j, (col, lab) in enumerate(bands):
        bx = fig.add_axes([0.07, 0.18 - j * 0.08, 0.90, 0.06], sharex=ax)
        for a, b_, v in zip(h.i.iloc[:-1], h.i.iloc[1:], h[col].iloc[:-1]):
            bx.axvspan(a, b_, color=COL.get(family(v), "#FFFFFF"), lw=0)
        bx.set_yticks([])
        bx.text(-0.005, 0.5, lab, transform=bx.transAxes, ha="right", va="center", fontsize=7.5, color="#202945")
        for sp in bx.spines.values():
            sp.set_visible(False)
        yr = [i for i in range(i0 + 1, len(s)) if s.index[i].year != s.index[i - 1].year]
        bx.set_xticks(yr if j == 1 else [])
        bx.set_xticklabels([str(s.index[i].year) for i in yr] if j == 1 else [], fontsize=7.5)
    fig.text(0.07, 0.015, "Green Bullish · grey Neutral · purple Bearish (weekly). Sources : Syz Research, Bloomberg", fontsize=7.5,
             color="#4B5F80")
    fig.savefig(out)
    plt.close(fig)
    return out
