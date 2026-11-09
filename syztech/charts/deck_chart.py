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
from ..indicators.bands import max_prior, min_prior
from ..indicators.ma import sma
from ..indicators.rs import relative_strength
from .syz_style import (AMBER, BLUEBERRY, GREY, MINT, MULBERRY, NAVY, ORANGE, SOURCE_LINE, VERDICT_COLOUR,
                        VERDICT_GLYPH, register_fonts)

BARS_5Y = 5 * 252
MA50_BLUE = "#2F6FDE"
PAGES = {"16x9": (13.333, 7.5), "a4": (10.45, 7.30)}   # a4: fills an A4 landscape slide, logo and page number kept clear     # agreed 8 Nov 2026 (outside the Syz palette)
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
               benchmark_name: str | None = None, ma50_colour: str = MA50_BLUE, show_52w: bool = False,
               show_band100: bool = True, page: str = "16x9") -> Path:
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

    FW, FH = PAGES[page]
    fig = plt.figure(figsize=(FW, FH), dpi=170 if page == "a4" else 150, facecolor="white")
    fr = lambda x, y, w, h: [x / FW, y / FH, w / FW, h / FH]          # inches → figure fractions
    has_rs = benchmark is not None
    LEFT, RIGHT_GAP, TOP_GAP = 0.62, 1.55, 1.30                         # room for y labels, value tags, title block
    plot_w = FW - LEFT - RIGHT_GAP
    main_bottom = 2.30 if has_rs else 0.50
    ax = fig.add_axes(fr(LEFT, main_bottom, plot_w, FH - TOP_GAP - main_bottom))
    if has_rs:
        rx = fig.add_axes(fr(LEFT, 0.50, plot_w, 1.40), sharex=ax)

    # price and averages
    ax.plot(x, close.iloc[sl], color=NAVY, lw=1.2, label="Close", zorder=3)
    ax.plot(x, ma50.iloc[sl], color=ma50_colour, lw=1.3, label="50-day MA", zorder=2)
    ax.plot(x, ma200.iloc[sl], color=ORANGE, lw=2.0, label="200-day MA", zorder=2)

    # drawn horizontal levels, value printed on the axis
    for key, colour in (("support", BLUEBERRY), ("resistance", BLUEBERRY)):
        v = row.get(key)
        origin = row.get(f"{key}_origin")
        is52 = isinstance(origin, str) and origin.startswith("52w")
        if show_52w and is52:
            continue                              # already shown by the 52-week range
        if v is not None and not pd.isna(v):
            if is52:                              # fallback level: grey, labelled, so it is never mistaken for a drawn line
                ax.axhline(v, color="#8A93A6", lw=1.0, ls=(0, (2, 3)), zorder=1)
                _axis_tag(tags, v, f"52w {'low' if key == 'support' else 'high'} {num(v, dec)}", "#E4E7EE", fg=NAVY)
            else:
                ax.axhline(v, color=colour, lw=1.2, ls=(0, (6, 4)), zorder=1)
                _axis_tag(tags, v, num(v, dec), "#79D6FF", fg=NAVY)

    # 100-day high / low band (prior 100 closes, as in the engine), today's values tagged
    if show_band100:
        hi100, lo100 = max_prior(close, 100), min_prior(close, 100)
        ax.fill_between(x, lo100.iloc[sl], hi100.iloc[sl], color=BLUEBERRY, alpha=0.08, lw=0, zorder=0,
                        step=None, label="100-day high / low band")
        ax.plot(x, hi100.iloc[sl], color=BLUEBERRY, lw=0.6, alpha=0.45, zorder=0)
        ax.plot(x, lo100.iloc[sl], color=BLUEBERRY, lw=0.6, alpha=0.45, zorder=0)
        for v, lab in ((hi100.iloc[-1], "100d high"), (lo100.iloc[-1], "100d low")):
            if pd.notna(v):
                _axis_tag(tags, v, f"{lab} {num(v, dec)}", "#E4E7EE", fg=NAVY)

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

    # scale fixed from price, averages, levels and bands – trendlines never stretch it
    window = close.iloc[sl]
    use_log = bool((window > 0).all())
    ax.set_yscale("log" if use_log else "linear")
    ax.relim(); ax.autoscale_view()
    ylo, yhi = ax.get_ylim()

    # trendlines: straight on the chart's scale, extended to the right edge, clipped to the price range
    for tl in trendlines or []:
        p0, p1 = _pos(close.index, tl.start[0]) - start, _pos(close.index, tl.end[0]) - start
        f, g = (np.log, np.exp) if use_log else (lambda v: v, lambda v: v)
        y0, y1 = f(tl.start[1]), f(tl.end[1])
        xs = np.linspace(max(p0, 0), x[-1], 200)
        ys = g(y0 + (y1 - y0) * (xs - p0) / (p1 - p0))
        ax.plot(xs, ys, color=BLUEBERRY, lw=1.2, ls=(0, (6, 4)), zorder=1, clip_on=True)
        if ylo <= ys[-1] <= yhi:
            _axis_tag(tags, ys[-1], num(ys[-1], dec), "#79D6FF", fg=NAVY)
    ax.set_ylim(ylo, yhi)

    # last price, 200-day tags
    _axis_tag(tags, close.iloc[-1], num(close.iloc[-1], dec), NAVY)
    _axis_tag(tags, ma200.iloc[-1], num(ma200.iloc[-1], dec), ORANGE)

    lo, hi = ax.get_ylim()
    ticks = [v for v in MaxNLocator(nbins=6, steps=[1, 2, 2.5, 5, 10]).tick_values(lo, hi) if lo <= v <= hi and (v > 0 or not use_log)]
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
    title = fig.text(LEFT / FW, (FH - 0.50) / FH, row["name"], fontsize=22, fontweight="bold", color=NAVY)
    rend = fig.canvas.get_renderer()
    size = 22
    while size > 13 and title.get_window_extent(rend).x1 > (FW - 3.0) / FW * fig.bbox.width:   # keep clear of the badge
        size -= 1
        title.set_fontsize(size)
    fig.text(LEFT / FW, (FH - 0.80) / FH, f"{row['ticker']}  |  daily close, {'log' if use_log else 'linear'} scale, 5 years",
             fontsize=10.5, color=BLUEBERRY)
    fig.add_artist(plt.Line2D([LEFT / FW, (LEFT + 0.9) / FW], [(FH - 0.90) / FH] * 2, color=ORANGE, lw=3, transform=fig.transFigure))

    # badge top-right
    if badge:
        col = VERDICT_COLOUR.get(badge, BLUEBERRY)
        bx = fig.add_axes(fr(FW - 2.95, FH - 0.95, 2.85, 0.80)); bx.axis("off")
        bx.add_patch(FancyBboxPatch((0.02, 0.06), 0.96, 0.88, boxstyle="round,pad=0,rounding_size=0.2",
                                    fc=col, ec="none", transform=bx.transAxes))
        bx.text(0.5, 0.60, f"{VERDICT_GLYPH.get(badge, '')}  {BADGE_TEXT.get(badge, badge)}", ha="center", va="center",
                color="white", fontsize=13, fontweight="bold", transform=bx.transAxes)
        sub = {"published": "Syz Research view", "mechanical": "Rules-based reading (no published view)"}.get(badge_kind, badge_kind)
        bx.text(0.5, 0.25, sub,
                ha="center", va="center", color="white", fontsize=8.5, transform=bx.transAxes)

    _draw_tags(ax, tags)
    fig.text(LEFT / FW, 0.10 / FH, SOURCE_LINE, fontsize=9, color=BLUEBERRY)
    fig.text((LEFT + plot_w) / FW, 0.10 / FH, f"Data to {close.index[-1]:%d %b %Y}".replace(" 0", " "), fontsize=9,
             color=BLUEBERRY, ha="right")
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
