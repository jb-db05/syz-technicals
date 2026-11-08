"""Publication chart for the Syz decks (16:9): one instrument, one message.

Close, 50- and 200-day averages, drawn levels with their values printed on the axis,
optional trendlines (two anchor points each), optional relative-strength panel, and the
published verdict as the badge. Trading-day axis, log scale, 5 years.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import FuncFormatter, MaxNLocator, NullLocator

from ..fmt import num
from ..indicators.ma import sma
from ..indicators.rs import relative_strength
from .syz_style import (AMBER, BLUEBERRY, GREY, MINT, MULBERRY, NAVY, ORANGE, SOURCE_LINE, VERDICT_COLOUR,
                        VERDICT_GLYPH, register_fonts)

BARS_5Y = 5 * 252
MA50_BLUE = "#2F6FDE"     # agreed 8 Nov 2026 (outside the Syz palette)
BADGE_TEXT = {"Bullish": "BULLISH", "Neutral+": "NEUTRAL – POSITIVE TILT", "Neutral": "NEUTRAL",
              "Neutral-": "NEUTRAL – NEGATIVE TILT", "Bearish_LM": "BEARISH – LOSING MOMENTUM", "Bearish": "BEARISH"}


@dataclass
class Trendline:
    start: tuple[str, float]      # (date, price)
    end: tuple[str, float]
    label: str = "Trendline"


def _pos(index: pd.DatetimeIndex, d) -> float:
    return float(index.searchsorted(pd.Timestamp(d)))


def _axis_tag(tags, y, text, fc, fg="white", prio=1):
    """Queue a value tag for the right-hand axis (drawn later, spaced so none hides another)."""
    tags.append(dict(y=float(y), text=text, fc=fc, fg=fg, prio=prio))


def _draw_tags(ax, tags, min_gap_pt=19):
    """Place tags at their values; push apart vertically so every value stays readable."""
    if not tags:
        return
    min_gap_px = min_gap_pt * ax.figure.dpi / 72
    to_px = ax.transData.transform
    for tg in tags:
        tg["px"] = to_px((0, tg["y"]))[1]
    tags.sort(key=lambda tg: tg["px"])
    pos = [tg["px"] for tg in tags]
    for _ in range(50):                      # relax overlaps symmetrically
        moved = False
        for i in range(1, len(pos)):
            gap = pos[i] - pos[i - 1]
            if gap < min_gap_px:
                d = (min_gap_px - gap) / 2
                pos[i - 1] -= d; pos[i] += d; moved = True
        if not moved:
            break
    for tg, p in zip(tags, pos):
        dy = (p - tg["px"]) * 72 / ax.figure.dpi
        ax.annotate(tg["text"], xy=(1.0, tg["y"]), xycoords=("axes fraction", "data"), xytext=(8, dy),
                    textcoords="offset points", va="center", ha="left", fontsize=9, color=tg["fg"], fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.28,rounding_size=0.25", fc=tg["fc"], ec="none"), zorder=6,
                    annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=tg["fc"], lw=1, shrinkA=0, shrinkB=0) if abs(dy) > 1 else None)


def deck_chart(close: pd.Series, row: dict, out: str | Path, *, badge: str | None, badge_kind: str = "published",
               trendlines: list[Trendline] | None = None, benchmark: pd.Series | None = None,
               benchmark_name: str | None = None, ma50_colour: str = MA50_BLUE, show_52w: bool = True) -> Path:
    family = register_fonts()
    plt.rcParams.update({"font.family": [family, "DejaVu Sans"], "font.size": 10, "axes.edgecolor": GREY,
                         "xtick.color": NAVY, "ytick.color": NAVY})
    dec = int(row.get("decimals") or 1)
    ma50, ma200 = sma(close, 50), sma(close, 200)
    n = len(close)
    start = int(close.index.searchsorted(close.index[-1] - pd.DateOffset(years=5)))   # 5 calendar years
    idx = close.index[start:]
    x = np.arange(n - start)
    sl = slice(start, n)
    tags: list[dict] = []

    fig = plt.figure(figsize=(13.333, 7.5), dpi=150, facecolor="white")
    has_rs = benchmark is not None
    top = 0.80
    main_h = 0.50 if has_rs else 0.66
    ax = fig.add_axes([0.05, top - main_h, 0.84, main_h])
    if has_rs:
        rx = fig.add_axes([0.05, 0.10, 0.84, 0.15], sharex=ax)

    # price and averages
    ax.plot(x, close.iloc[sl], color=NAVY, lw=1.2, label="Close", zorder=3)
    ax.plot(x, ma50.iloc[sl], color=ma50_colour, lw=1.3, label="50-day MA", zorder=2)
    ax.plot(x, ma200.iloc[sl], color=ORANGE, lw=2.0, label="200-day MA", zorder=2)

    # drawn horizontal levels, value printed on the axis
    for key, colour in (("support", BLUEBERRY), ("resistance", BLUEBERRY)):
        v = row.get(key)
        origin = row.get(f"{key}_origin")
        if show_52w and isinstance(origin, str) and origin.startswith("52w"):
            continue                              # already shown by the 52-week range
        if v is not None and not pd.isna(v):
            ax.axhline(v, color=colour, lw=1.2, ls=(0, (6, 4)), zorder=1)
            _axis_tag(tags, v, num(v, dec), "#79D6FF", fg=NAVY)

    # 52-week range: band over the last 52 weeks, high and low tagged
    if show_52w:
        w0 = int(close.index.searchsorted(close.index[-1] - pd.Timedelta(weeks=52)))
        win = close.iloc[w0:]
        hi52, lo52 = float(win.max()), float(win.min())
        xa = max(w0 - start, 0)
        ax.fill_between([xa, x[-1]], lo52, hi52, color=GREY, alpha=0.16, lw=0, zorder=0, label="52-week range")
        for v, lab in ((hi52, "52w high"), (lo52, "52w low")):
            ax.plot([xa, x[-1]], [v, v], color="#8A93A6", lw=1.0, ls=(0, (1.5, 2.5)), zorder=1)
            _axis_tag(tags, v, f"{lab} {num(v, dec)}", "#E4E7EE", fg=NAVY)

    # trendlines: straight on the log chart, extended to the right edge
    for tl in trendlines or []:
        p0, p1 = _pos(close.index, tl.start[0]) - start, _pos(close.index, tl.end[0]) - start
        y0, y1 = np.log(tl.start[1]), np.log(tl.end[1])
        xs = np.array([max(p0, 0), x[-1]])
        ys = np.exp(y0 + (y1 - y0) * (xs - p0) / (p1 - p0))
        ax.plot(xs, ys, color=BLUEBERRY, lw=1.2, ls=(0, (6, 4)), zorder=1)
        _axis_tag(tags, ys[-1], num(ys[-1], dec), "#79D6FF", fg=NAVY)

    # last price, 200-day tags
    _axis_tag(tags, close.iloc[-1], num(close.iloc[-1], dec), NAVY)
    _axis_tag(tags, ma200.iloc[-1], num(ma200.iloc[-1], dec), ORANGE)

    ax.set_yscale("log")
    lo, hi = ax.get_ylim()
    ticks = [v for v in MaxNLocator(nbins=6, steps=[1, 2, 2.5, 5, 10]).tick_values(lo, hi) if lo <= v <= hi and v > 0]
    ax.set_yticks(ticks)
    ax.set_ylim(lo, hi)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: num(v, dec if hi < 1000 else 0)))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.yaxis.tick_left()
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color=GREY, alpha=0.35, lw=0.6)
    ax.set_xlim(0, x[-1] + 1)
    yr = [i for i in range(1, len(idx)) if idx[i].year != idx[i - 1].year]
    ax.set_xticks(yr)
    ax.set_xticklabels([str(idx[i].year) for i in yr])
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, fontsize=9, ncol=4, labelcolor=NAVY,
              borderaxespad=0.2)

    if has_rs:
        rs = relative_strength(close, benchmark).reindex(close.index)
        rs_ma = sma(rs.dropna(), 200).reindex(close.index)
        base = rs.iloc[start:].dropna().iloc[0]
        rs, rs_ma = rs / base * 100, rs_ma / base * 100      # rebased: 100 at the start of the chart
        rx.plot(x, rs.iloc[sl], color=MULBERRY, lw=1.1)
        rx.plot(x, rs_ma.iloc[sl], color=GREY, lw=1.2)
        rx.set_ylabel("")
        rx.yaxis.set_major_locator(plt.MaxNLocator(3))
        rx.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
        rx.axhline(100, color=GREY, lw=0.8, ls=":")
        for s in ("top", "right"):
            rx.spines[s].set_visible(False)
        rx.grid(axis="y", color=GREY, alpha=0.35, lw=0.6)
        rx.text(0.0, 1.08, f"Relative strength vs {benchmark_name}, rebased to 100 (grey: its 200-day)", transform=rx.transAxes,
                fontsize=9, color=NAVY, fontweight="bold")
        plt.setp(ax.get_xticklabels(), visible=False)
        rx.set_xticks(yr)
        rx.set_xticklabels([str(idx[i].year) for i in yr])

    # title block
    title = fig.text(0.05, 0.925, row["name"], fontsize=24, fontweight="bold", color=NAVY)
    rend = fig.canvas.get_renderer()
    size = 24
    while size > 13 and title.get_window_extent(rend).x1 > 0.68 * fig.bbox.width:   # keep clear of the badge
        size -= 1
        title.set_fontsize(size)
    fig.text(0.05, 0.875, f"{row['ticker']}  |  daily close, log scale, 5 years", fontsize=11, color=BLUEBERRY)
    fig.add_artist(plt.Line2D([0.05, 0.12], [0.862, 0.862], color=ORANGE, lw=3, transform=fig.transFigure))

    # badge top-right
    if badge:
        col = VERDICT_COLOUR.get(badge, BLUEBERRY)
        bx = fig.add_axes([0.70, 0.86, 0.25, 0.09]); bx.axis("off")
        bx.add_patch(FancyBboxPatch((0.02, 0.06), 0.96, 0.88, boxstyle="round,pad=0,rounding_size=0.2",
                                    fc=col, ec="none", transform=bx.transAxes))
        bx.text(0.5, 0.60, f"{VERDICT_GLYPH.get(badge, '')}  {BADGE_TEXT.get(badge, badge)}", ha="center", va="center",
                color="white", fontsize=13, fontweight="bold", transform=bx.transAxes)
        sub = {"published": "Syz Research view", "mechanical": "Rules-based reading (no published view)"}.get(badge_kind, badge_kind)
        bx.text(0.5, 0.25, sub,
                ha="center", va="center", color="white", fontsize=8.5, transform=bx.transAxes)

    _draw_tags(ax, tags)
    fig.text(0.05, 0.025, SOURCE_LINE, fontsize=9, color=BLUEBERRY)
    fig.text(0.89, 0.025, f"Data to {close.index[-1]:%d %b %Y}".replace(" 0", " "), fontsize=9, color=BLUEBERRY, ha="right")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out


def load_trendlines(path) -> dict[str, list[Trendline]]:
    """data/trendlines.csv: ticker,start_date,start_price,end_date,end_price[,label]. Missing file → none."""
    p = Path(path)
    if not p.exists():
        return {}
    df = pd.read_csv(p)
    out: dict[str, list[Trendline]] = {}
    for r in df.itertuples(index=False):
        out.setdefault(r.ticker, []).append(Trendline((str(r.start_date), float(r.start_price)),
                                                      (str(r.end_date), float(r.end_price)),
                                                      getattr(r, "label", "Trendline") or "Trendline"))
    return out
