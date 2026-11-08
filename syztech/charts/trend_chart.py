"""Trend chart for conflict / trigger_hit instruments (BUILD_SPEC §3.5).

Close, MA50, MA200, MAX100 / MIN100 bands, drawn levels, verdict badge top-right.
5 years, log scale, trading-day integer axis (no weekend kinks).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import FuncFormatter, NullLocator

from ..fmt import num
from ..indicators.bands import max_prior, min_prior
from ..indicators.ma import sma
from .syz_style import (AMBER, BLUEBERRY, GREY, NAVY, ORANGE, SOURCE_LINE, VERDICT_COLOUR, VERDICT_GLYPH,
                        VERDICT_LABEL, register_fonts)

YEARS_BARS = 5 * 252


def trend_chart(close: pd.Series, row: pd.Series, out: str | Path) -> Path:
    family = register_fonts()
    plt.rcParams.update({"font.family": [family, "DejaVu Sans"], "font.size": 9, "axes.edgecolor": GREY,
                         "axes.labelcolor": NAVY, "xtick.color": NAVY, "ytick.color": NAVY})
    dec = int(row.decimals) if pd.notna(row.get("decimals")) else 1

    ma50, ma200 = sma(close, 50), sma(close, 200)
    hi, lo = max_prior(close, 100), min_prior(close, 100)
    n = len(close)
    start = max(0, n - YEARS_BARS)
    x = np.arange(n - start)
    sl = slice(start, n)

    fig = plt.figure(figsize=(11, 6.2), dpi=150)
    ax = fig.add_axes([0.06, 0.12, 0.82, 0.68])
    ax.fill_between(x, lo.iloc[sl], hi.iloc[sl], color=BLUEBERRY, alpha=0.07, lw=0, label="100-day high / low band")
    ax.plot(x, hi.iloc[sl], color=BLUEBERRY, lw=0.6, alpha=0.5)
    ax.plot(x, lo.iloc[sl], color=BLUEBERRY, lw=0.6, alpha=0.5)
    ax.plot(x, close.iloc[sl], color=NAVY, lw=1.1, label="Close")
    ax.plot(x, ma50.iloc[sl], color=AMBER, lw=1.0, label="50-day MA")
    ax.plot(x, ma200.iloc[sl], color=ORANGE, lw=1.6, label="200-day MA")
    for key, lab in (("support", "Support"), ("resistance", "Resistance")):
        v = row.get(key)
        if v is not None and pd.notna(v):
            ax.axhline(v, color=BLUEBERRY, lw=1.1, ls=(0, (5, 3)))
            ax.text(x[-1] + 4, v, f"{lab} {num(v, dec)}", color=BLUEBERRY, va="center", fontsize=8)

    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: num(v, dec)))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.yaxis.tick_right()
    # trading-day axis, labelled at the first bar of each year
    idx = close.index[start:]
    yr = [i for i in range(1, len(idx)) if idx[i].year != idx[i - 1].year]
    ax.set_xticks(yr)
    ax.set_xticklabels([str(idx[i].year) for i in yr])
    ax.set_xlim(0, x[-1] + 1)
    for s in ("top", "left"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color=GREY, alpha=0.35, lw=0.5)
    ax.annotate(num(close.iloc[-1], dec), (x[-1], close.iloc[-1]), xytext=(6, 0), textcoords="offset points",
                color="white", fontsize=8, fontweight="bold", va="center",
                bbox=dict(boxstyle="round,pad=0.25", fc=NAVY, ec="none"))
    ax.legend(loc="upper left", frameon=False, fontsize=8, ncol=4, labelcolor=NAVY)

    fig.text(0.06, 0.93, f"{row['name']}", fontsize=17, fontweight="bold", color=NAVY)
    fig.text(0.06, 0.885, f"{row.ticker}  |  daily close, log scale, 5 years", fontsize=9, color=BLUEBERRY)
    fig.text(0.06, 0.845, row.reason, fontsize=8.5, color=NAVY, fontweight=300)

    v = row.verdict
    col = VERDICT_COLOUR.get(v, BLUEBERRY)
    bx = fig.add_axes([0.70, 0.865, 0.25, 0.10]); bx.axis("off")
    bx.add_patch(FancyBboxPatch((0.02, 0.08), 0.96, 0.84, boxstyle="round,pad=0.0,rounding_size=0.18",
                                fc=col, ec="none", transform=bx.transAxes))
    bx.text(0.5, 0.62, f"{VERDICT_GLYPH.get(v, '')} {VERDICT_LABEL.get(v, v)}", ha="center", va="center",
            color="white", fontsize=10.5, fontweight="bold", transform=bx.transAxes)
    badge = row.get("badge")
    bx.text(0.5, 0.27, f"Mechanical  |  published: {badge if isinstance(badge, str) else '–'}", ha="center",
            va="center", color="white", fontsize=7.5, transform=bx.transAxes)

    fig.text(0.06, 0.03, SOURCE_LINE, fontsize=7.5, color=BLUEBERRY)
    fig.text(0.88, 0.03, f"Data to {close.index[-1]:%d %b %Y}", fontsize=7.5, color=BLUEBERRY, ha="right")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out
