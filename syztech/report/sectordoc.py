"""Sector special report: one sector index against its market, and every constituent.

Cover, sector against the market, breadth by sub-industry, momentum map, momentum dashboards
(absolute and relative to the market) grouped by sub-sector, relative-strength ranking,
trend × relative-strength grid, trigger watch, method, one chart per stock, legal disclaimer.
Facts and the rule that fired only – no interpretation prose.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_TICK_LABEL_POSITION
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from ..charts.syz_style import FONT, register_fonts
from ..fmt import EN_DASH, num
from .listdoc import RS_ORDER, V_ORDER, _bucket
from .weekly import (AMBER, BLUEB, GREY, L_COVER, L_DISCLAIMER, L_FINAL, MINT, MULB, NAVY, ORANGE, SKY, VGLYPH, VLABEL, W, X0,
                     Deck, box, chart_image, full_page_chart, pct, rgb, source, table, text, triggers, verdict_style)

MINUS = "−"
SHORT_IND = {"Technology Hardware, Storage & Peripherals": "Hardware, storage & periph.",
             "Semiconductor Materials & Equipment": "Semi materials & equipment",
             "Internet Services & Infrastructure": "Internet services & infra.",
             "Electronic Equipment & Instruments": "Electronic equipment",
             "Electronic Manufacturing Services": "Electronic manufacturing",
             "IT Consulting & Other Services": "IT consulting & services",
             # broader universes (Swiss equities, 19 Nov 2026)
             "Electrical Components & Equipment": "Electrical components",
             "Apparel, Accessories & Luxury Goods": "Apparel & luxury",
             "Integrated Telecommunication Services": "Integrated telecoms",
             "Asset Management & Custody Banks": "Asset management",
             "Industrial Machinery & Supplies & Components": "Industrial machinery",
             "Real Estate Operating Companies": "Real estate operating",
             "Human Resource & Employment Services": "HR & employment services",
             "Paper & Plastic Packaging Products & Materials": "Paper & plastic packaging",
             "Diversified Real Estate Activities": "Diversified real estate",
             "Trading Companies & Distributors": "Trading & distribution",
             "Construction Machinery & Heavy Transportation Equipment": "Construction machinery",
             "Investment Banking & Brokerage": "Investment banking",
             "Life Sciences Tools & Services": "Life sciences tools",
             "Interactive Media & Services": "Interactive media"}
BUCKETS = ["Semiconductors & equipment", "Software", "Hardware & equipment", "IT services & internet"]


def add_momentum(df: pd.DataFrame, prices) -> pd.DataFrame:
    """1-month and 12-month price change, distance from the 52-week high (closes only)."""
    df = df.copy()
    c1, c12, fh = [], [], []
    for r in df.itertuples():
        s = prices.series(r.ticker).dropna()
        s = s[s.index <= r.last_date]
        end, close = s.index[-1], float(s.iloc[-1])
        m1 = s[s.index <= end - pd.DateOffset(months=1)]
        m12 = s[s.index <= end - pd.DateOffset(months=12)]
        c1.append(close / float(m1.iloc[-1]) - 1 if len(m1) else np.nan)
        c12.append(close / float(m12.iloc[-1]) - 1 if len(m12) else np.nan)
        fh.append(close / r.hi52 - 1 if pd.notna(r.hi52) and r.hi52 else np.nan)
    df["chg1m"], df["chg12m"], df["from_hi52"] = c1, c12, fh
    return df


def trigger_watch(df: pd.DataFrame, band: float = 0.02) -> pd.DataFrame:
    """Nearest level within `band`: 52-week high / low (or drawn levels) and the 100-day band, one row per stock."""
    tw = triggers(df, band)
    extra = []
    for r in df.itertuples():
        for lvl, lab in ((r.hi100, "100-day high"), (r.lo100, "100-day low")):
            if pd.notna(lvl) and abs(r.close / lvl - 1) <= band:
                extra.append(dict(ticker=r.ticker, name=r.name, verdict=r.verdict, close=r.close, decimals=r.decimals,
                                  level=lvl, kind=lab, dist=r.close / lvl - 1, asset_class=r.asset_class))
    tw = pd.concat([tw, pd.DataFrame(extra)], ignore_index=True) if extra else tw
    if len(tw):
        tw = tw.sort_values("dist", key=lambda x: x.abs()).drop_duplicates("ticker")
    return tw


def list_tag(v) -> str:
    """'★ Focus', '★ Master', '★ Focus + M.' from the universe column syz_lists; '' when on no list."""
    got = [x.strip() for x in v.split(";")] if isinstance(v, str) else []
    f, m = "Focus List" in got, "Master list" in got
    return "★ Focus + M." if f and m else "★ Focus" if f else "★ Master" if m else ""


def _vtxt(v):
    return f"{VGLYPH[v]} {VLABEL[v]}" if v in VGLYPH else "n/a – history"


def _vstyle(v):
    return verdict_style(v) if v in VGLYPH else {"fill": "E9ECF1", "color": GREY, "align": PP_ALIGN.CENTER}


def _rs(v):
    return {"outperforming": "+", "underperforming": MINUS}.get(v, EN_DASH)


def _p(x, d=1):
    return pct(x, d) if pd.notna(x) else EN_DASH


def _posneg(x):
    return {"color": MINT if (pd.notna(x) and x >= 0) else (MULB if pd.notna(x) else GREY), "align": PP_ALIGN.RIGHT}


def _sort(df):
    df = df.copy()
    df["vo"] = df.verdict.map(V_ORDER).fillna(9)
    df["ro"] = df.rs_trend.map(RS_ORDER).fillna(9)
    return df.sort_values(["vo", "ro", "rs_chg63"], ascending=[True, True, False])


def momentum_dashboard(deck, df, title, bench, asof, footnote):
    s = deck.titled(title, "")
    hdr = ["Stock", "Syz list", "Sub-industry", "Last", "200-day", "vs 200d", "1m", "3m", "12m", "vs 52w high", "RS Mom", "RS 3m",
           "Trend"]
    col_w = [1.6, 0.66, 1.62, 0.64, 0.6, 0.6, 0.56, 0.56, 0.6, 0.68, 0.55, 0.6, 1.01]
    xs = [X0 + sum(col_w[:j]) for j in range(len(col_w) + 1)]
    for lab, a_, b_, col in (("Absolute momentum", 3, 9, NAVY), (f"vs {bench}", 10, 11, ORANGE), ("Verdict", 12, 12, BLUEB)):
        box(s, xs[a_] + 0.02, 2.2, xs[b_ + 1] - xs[a_] - 0.04, 0.24, col, radius=0.25)
        text(s, xs[a_], 2.2, xs[b_ + 1] - xs[a_], 0.24, lab, size=9, color="FFFFFF", bold=True,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    rows, st = [], {}
    for i, r in enumerate(df.itertuples()):
        lt = list_tag(getattr(r, "syz_lists", ""))
        rows.append([r.name, lt or EN_DASH, SHORT_IND.get(r.industry, r.industry or ""), num(r.close, r.decimals), r.slope200 or EN_DASH,
                     _p(r.vs200), _p(r.chg1m), _p(r.chg3m), _p(r.chg12m), _p(r.from_hi52), _rs(r.rs_trend), _p(r.rs_chg63),
                     _vtxt(r.verdict)])
        if lt:
            st[(i, 1)] = {"fill": "FFE9D6" if "Master" in lt else "E4E8F0", "color": ORANGE if lt == "★ Master" else NAVY,
                          "bold": True, "align": PP_ALIGN.CENTER}
        else:
            st[(i, 1)] = {"color": "D5DAE3", "align": PP_ALIGN.CENTER}
        st[(i, 2)] = {"color": BLUEB, "align": PP_ALIGN.LEFT}
        st[(i, 4)] = {"color": {"rising": MINT, "falling": MULB}.get(r.slope200, BLUEB), "align": PP_ALIGN.LEFT}
        for j, v in ((5, r.vs200), (6, r.chg1m), (7, r.chg3m), (8, r.chg12m), (11, r.rs_chg63)):
            st[(i, j)] = _posneg(v)
        st[(i, 9)] = {"color": MINT if (pd.notna(r.from_hi52) and r.from_hi52 >= -0.05) else NAVY, "align": PP_ALIGN.RIGHT}
        st[(i, 10)] = {"color": {"outperforming": MINT, "underperforming": MULB}.get(r.rs_trend, GREY), "bold": True,
                       "align": PP_ALIGN.CENTER}
        st[(i, 12)] = _vstyle(r.verdict)
    n = len(rows)
    rh = min(0.30, 5.0 / (n + 1))
    table(s, X0, 2.5, W, hdr, rows, col_w, row_h=rh, size=8 if rh >= 0.24 else 7.5, styles=st)
    source(s, asof, footnote)
    return s


def momentum_map(df, out: Path, bench: str):
    """Scatter: price vs 200-day (x) against 3-month change in relative strength (y), coloured by verdict."""
    register_fonts()
    plt.rcParams["font.family"] = FONT
    d = df.dropna(subset=["vs200", "rs_chg63"])
    fig, ax = plt.subplots(figsize=(10.28, 5.0), dpi=200)
    col = {"Bullish": "#3BAF90", "Bearish": "#AC5D85", "Bearish_LM": "#AC5D85"}
    ax.axhline(0, color="#B8BFCC", lw=0.8)
    ax.axvline(0, color="#B8BFCC", lw=0.8)
    xs, ys = d.vs200 * 100, d.rs_chg63 * 100
    ax.scatter(xs, ys, s=34, c=[col.get(v, "#4B5F80") for v in d.verdict], edgecolors="white", linewidths=0.6, zorder=3)
    for x, y, t in zip(xs, ys, d.ticker):
        ax.annotate(t.split()[0], (x, y), xytext=(3, 3), textcoords="offset points", fontsize=6.2, color="#202945")
    xl, yl = ax.get_xlim(), ax.get_ylim()
    kw = dict(fontsize=8, fontweight="bold", alpha=0.85)
    ax.text(xl[1], yl[1], "Above 200-day, gaining on " + bench, ha="right", va="top", color="#3BAF90", **kw)
    ax.text(xl[0], yl[0], "Below 200-day, losing to " + bench, ha="left", va="bottom", color="#AC5D85", **kw)
    ax.text(xl[1], yl[0], "Above 200-day, losing to " + bench, ha="right", va="bottom", color="#4B5F80", **kw)
    ax.text(xl[0], yl[1], "Below 200-day, gaining on " + bench, ha="left", va="top", color="#4B5F80", **kw)
    ax.set_xlabel("Price vs 200-day moving average, %", fontsize=8.5, color="#202945")
    ax.set_ylabel(f"Relative strength vs {bench}, 3-month change, %", fontsize=8.5, color="#202945")
    ax.tick_params(labelsize=7.5, colors="#4B5F80")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("#B8BFCC")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    return out


def build_sector_doc(df: pd.DataFrame, sector: pd.Series, charts: dict, out: Path, template: Path, *, title: str, edition: str,
                     asof: str, bench: str, sector_name: str, insufficient: list[str], work: Path, draft: bool = True, lists_asof: str = "",
                     buckets: list[str] | None = None, group_col: str = "industry", group_label: str = "sub-industry",
                     group_label_pl: str = "GICS sub-industries", indices: pd.DataFrame | None = None, bench_note: str = "",
                     max_rows: int = 25, trigger_cap: int | None = None, index_heading: str = "Indices") -> Path:
    """IT defaults reproduce the 18 Nov 2026 edition. `indices` (other index rows with RS against the benchmark) replaces
    the sector-tile page with an index table followed by every index chart; `group_col` sets the breadth table level."""
    lists_asof = f" ({lists_asof})" if lists_asof else ""
    bench_note = f" {bench_note}" if bench_note else ""
    buckets = buckets or BUCKETS
    deck = Deck(template)
    df = _sort(df).reset_index(drop=True)
    ok = df[df.verdict.isin(VGLYPH)]
    n, n_ok = len(df), len(ok)
    counts = ok.verdict.map(_bucket).value_counts()
    nb = int(counts.get("Bullish", 0))
    above = int((df.vs200 > 0).sum())
    out_n = int((df.rs_trend == "outperforming").sum())
    under_n = int((df.rs_trend == "underperforming").sum())
    near_hi = int((df.from_hi52 >= -0.05).sum())
    insuf_note = (f" Insufficient history for a verdict: {', '.join(insufficient)}." if insufficient else "")

    # cover
    s = deck.slide(L_COVER)
    for ph in list(s.placeholders):
        i = ph.placeholder_format.idx
        if i == 0:
            ph.text = title
        elif i == 13:
            ph.text = edition.upper()
        else:
            ph._element.getparent().remove(ph._element)
    box(s, 5.85, 0, 5.85, 8.27, NAVY, radius=0)
    text(s, 6.45, 2.2, 4.8, 0.4, f"{n} STOCKS – TREND VERDICTS", size=11, color=AMBER, bold=True)
    for k, (lab, col) in enumerate((("Bullish", MINT), ("Neutral", SKY), ("Bearish", "E6A4AD"))):
        text(s, 6.45, 2.85 + k * 1.15, 1.6, 0.9, str(int(counts.get(lab, 0))), size=48, color=col, bold=True)
        text(s, 8.15, 3.15 + k * 1.15, 2.6, 0.5, lab, size=16, color="FFFFFF")
    if insufficient:
        text(s, 6.45, 6.35, 4.6, 0.3, f"{len(insufficient)} without enough history for a verdict", size=10, color=GREY)
    text(s, 0.73, 7.45, 4.8, 0.3, "Florian Marini, CFA, CMT – Head of Research", size=10, color=BLUEB)
    if draft:
        text(s, 0.73, 4.75, 4.8, 0.3, "DRAFT – FOR INTERNAL REVIEW", size=10, color=ORANGE, bold=True)

    if indices is not None and len(indices):
        index_page(deck, sector, indices, charts, bench, asof, bench_note, index_heading)
    else:
        sector_page(deck, sector, charts, bench, asof, sector_name)
    _rest(deck, df, ok, n, n_ok, counts, nb, above, out_n, near_hi, insuf_note, charts, asof, bench, sector_name, insufficient,
          work, lists_asof, buckets, group_col, group_label, group_label_pl, bench_note, max_rows, trigger_cap)
    deck.slide(L_DISCLAIMER)
    deck.slide(L_FINAL)
    deck.save(out)
    return out


def sector_page(deck, sector, charts, bench, asof, sector_name):
    # sector against the market
    sv = sector.verdict
    s = deck.titled(f"{sector_name}: {VLABEL.get(sv, sv)} trend, RS Mom {_rs(sector.rs_trend)} against the {bench}",
                    f"Sector index: absolute momentum and relative strength against the {bench}")
    tiles = [("Trend verdict", _vtxt(sv), MINT if sv == "Bullish" else MULB if str(sv).startswith("Bearish") else BLUEB),
             ("200-day average", sector.slope200 or EN_DASH, {"rising": MINT, "falling": MULB}.get(sector.slope200, BLUEB)),
             ("Price vs 200-day", _p(sector.vs200), MINT if sector.vs200 >= 0 else MULB),
             ("vs 52-week high", _p(sector.from_hi52), NAVY),
             ("1-month change", _p(sector.chg1m), MINT if sector.chg1m >= 0 else MULB),
             ("3-month change", _p(sector.chg3m), MINT if sector.chg3m >= 0 else MULB),
             ("12-month change", _p(sector.chg12m), MINT if sector.chg12m >= 0 else MULB),
             (f"RS Mom vs {bench}", _rs(sector.rs_trend), {"outperforming": MINT, "underperforming": MULB}.get(sector.rs_trend, GREY)),
             (f"RS 3m vs {bench}", _p(sector.rs_chg63), MINT if sector.rs_chg63 >= 0 else MULB)]
    for k, (lab, val, col) in enumerate(tiles):
        cx, cy = X0 + (k % 3) * 3.47, 2.55 + (k // 3) * 1.6
        box(s, cx, cy, 3.3, 1.38, "F6F7F9")
        box(s, cx, cy, 0.09, 1.38, ORANGE if k % 2 == 0 else BLUEB, radius=0)
        text(s, cx + 0.25, cy + 0.14, 2.9, 0.3, lab, size=10, color=BLUEB)
        text(s, cx + 0.25, cy + 0.5, 2.9, 0.7, val, size=24, color=col, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    source(s, asof, f"Last close {num(sector.close, sector.decimals)}. 52-week low {num(sector.lo52, sector.decimals)}, "
                    f"high {num(sector.hi52, sector.decimals)}. Rule fired: {sector.rule}. Chart on the next page; its lower panel: share of "
                    f"today's constituents with a rising 200-day average, each counted once it has 220 closes (survivorship applies).")
    if sector.ticker in charts:
        full_page_chart(deck, charts[sector.ticker])


def index_page(deck, sector, indices, charts, bench, asof, bench_note="", heading="Indices"):
    """The market index and the other indices against it: one table, then every index chart."""
    rows_df = pd.concat([sector.to_frame().T, indices], ignore_index=True)
    parts = [f"{VLABEL.get(sector.verdict, sector.verdict)} trend for the {sector['name']}"]
    parts += [f"{r.name} RS Mom {_rs(r.rs_trend)}" for r in indices.itertuples()]
    s = deck.titled(f"{heading}: {parts[0]}; " + ", ".join(parts[1:]) + f" against the {bench}",
                    f"Absolute momentum of each index and relative strength against the {bench}")
    hdr = ["Index", "Last", "200-day", "vs 200d", "1m", "3m", "12m", "vs 52w high", f"RS Mom vs {bench}", f"RS 3m vs {bench}", "Trend"]
    col_w = [1.6, 0.95, 0.75, 0.8, 0.75, 0.75, 0.8, 0.95, 1.05, 1.0, 0.88]
    rows, st = [], {}
    for i, r in enumerate(rows_df.itertuples()):
        rows.append([r.name, num(r.close, r.decimals), r.slope200 or EN_DASH, _p(r.vs200), _p(r.chg1m), _p(r.chg3m), _p(r.chg12m),
                     _p(r.from_hi52), _rs(r.rs_trend) if i else EN_DASH, _p(r.rs_chg63) if i else EN_DASH, _vtxt(r.verdict)])
        st[(i, 0)] = {"bold": True}
        st[(i, 2)] = {"color": {"rising": MINT, "falling": MULB}.get(r.slope200, BLUEB), "align": PP_ALIGN.LEFT}
        for j, v in ((3, r.vs200), (4, r.chg1m), (5, r.chg3m), (6, r.chg12m)):
            st[(i, j)] = _posneg(v)
        st[(i, 7)] = {"color": MINT if (pd.notna(r.from_hi52) and r.from_hi52 >= -0.05) else NAVY, "align": PP_ALIGN.RIGHT}
        if i:
            st[(i, 8)] = {"color": {"outperforming": MINT, "underperforming": MULB}.get(r.rs_trend, GREY), "bold": True,
                          "align": PP_ALIGN.CENTER}
            st[(i, 9)] = _posneg(r.rs_chg63)
        st[(i, 10)] = _vstyle(r.verdict)
    table(s, X0, 2.6, W, hdr, rows, col_w, row_h=0.42, size=10, styles=st)
    notes = [f"{r.name}: last close {num(r.close, r.decimals)}, 52-week low {num(r.lo52, r.decimals)}, high {num(r.hi52, r.decimals)}; "
             f"rule fired: {r.rule}." for r in rows_df.itertuples()]
    text(s, X0, 2.6 + 0.42 * (len(rows) + 1) + 0.3, W, 1.6, notes, size=9, color=BLUEB)
    source(s, asof, f"The {sector['name']} chart carries a third panel: share of today's constituents with a rising 200-day average, "
                    f"each counted once it has 220 closes (survivorship applies).{bench_note}")
    for r in rows_df.itertuples():
        if r.ticker in charts:
            full_page_chart(deck, charts[r.ticker])


def _rest(deck, df, ok, n, n_ok, counts, nb, above, out_n, near_hi, insuf_note, charts, asof, bench, sector_name, insufficient,
          work, lists_asof, buckets, group_col, group_label, group_label_pl, bench_note, max_rows, trigger_cap):
    # breadth: four numbers + share by sub-sector (native chart)
    s = deck.titled(f"Breadth: {nb} of {n_ok} stocks Bullish, {above} of {n} above their 200-day, {out_n} with RS Mom +",
                    "Share of stocks by " + ("sub-sector" if buckets == BUCKETS else "group") + ", %")
    stats = [(f"{nb}/{n_ok}", "Bullish trend verdict", MINT), (f"{above}/{n}", "above the 200-day average", NAVY),
             (f"{out_n}/{n}", f"RS Mom + against the {bench}", ORANGE), (f"{near_hi}/{n}", "within 5% of the 52-week high", BLUEB)]
    for k, (big, lab, col) in enumerate(stats):
        y = 2.55 + k * 1.22
        box(s, X0, y, 3.2, 1.05, "F6F7F9")
        text(s, X0 + 0.18, y + 0.08, 1.5, 0.9, big, size=24, color=col, bold=True, anchor=MSO_ANCHOR.MIDDLE)
        text(s, X0 + 1.6, y + 0.08, 1.55, 0.9, lab, size=10, anchor=MSO_ANCHOR.MIDDLE)
    cd = CategoryChartData()
    bk = [b for b in buckets if b in set(df.bucket)]
    g = {b: df[df.bucket == b] for b in bk}
    cd.categories = [f"{b} ({len(g[b])})" for b in bk]
    cd.add_series("Bullish", [round(100 * (g[b].verdict == "Bullish").mean(), 0) for b in bk])
    cd.add_series("Above 200-day", [round(100 * (g[b].vs200 > 0).mean(), 0) for b in bk])
    cd.add_series(f"RS Mom +", [round(100 * (g[b].rs_trend == "outperforming").mean(), 0) for b in bk])
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(X0 + 3.45), Inches(2.45), Inches(6.85), Inches(4.95), cd)
    ch = gf.chart
    ch.has_title = False
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.TOP
    ch.legend.include_in_layout = False
    ch.legend.font.size = Pt(9)
    pl = ch.plots[0]
    pl.gap_width = 60
    pl.overlap = -10
    pl.has_data_labels = True
    pl.data_labels.font.size = Pt(8)
    pl.data_labels.number_format = '0'
    pl.data_labels.number_format_is_linked = False
    for ser, c in zip(ch.series, (MINT, NAVY, ORANGE)):
        ser.format.fill.solid()
        ser.format.fill.fore_color.rgb = rgb(c)
    ch.category_axis.tick_labels.font.size = Pt(8.5)
    ch.value_axis.visible = False
    ch.value_axis.has_major_gridlines = False
    ch.value_axis.maximum_scale = 100
    ch.value_axis.minimum_scale = 0
    source(s, asof, f"RS Mom: direction of the 200-day average of relative strength (stock ÷ {bench}) over 20 trading days." + insuf_note)

    # breadth by GICS sub-industry
    rows, st = [], {}
    agg = []
    for ind, x in df.groupby(group_col):
        agg.append((ind, len(x), int((x.verdict == "Bullish").sum()), int((x.vs200 > 0).sum()),
                    int((x.rs_trend == "outperforming").sum()), x.chg3m.median(), x.rs_chg63.median()))
    agg.sort(key=lambda a: -(a[6] if pd.notna(a[6]) else -9))
    agg.append((f"{sector_name} constituents", n, nb, above, out_n, df.chg3m.median(), df.rs_chg63.median()))
    for i, (ind, k, b, a, o, c3, r3) in enumerate(agg):
        rows.append([ind, str(k), f"{b}", f"{a}", f"{o}", _p(c3), _p(r3)])
        st[(i, 5)] = _posneg(c3)
        st[(i, 6)] = _posneg(r3)
        for j, v in ((2, b), (3, a), (4, o)):
            st[(i, j)] = {"align": PP_ALIGN.CENTER, "color": MINT if v / k > 0.5 else (MULB if v / k < 0.5 else NAVY), "bold": True}
        st[(i, 1)] = {"align": PP_ALIGN.CENTER}
        if i == len(agg) - 1:
            for j in range(7):
                st.setdefault((i, j), {})
                st[(i, j)] = {**st[(i, j)], "fill": "FFE9D6", "bold": True}
    best = agg[0][0]
    s = deck.titled(f"By {group_label}: {best} leads on relative strength over 3 months",
                    f"{group_label_pl}, ranked by median 3-month change in relative strength")
    table(s, X0, 2.5, W, [group_label[0].upper() + group_label[1:], "Stocks", "Bullish", "Above 200-day", "RS Mom +", "Median 3m", f"Median RS 3m vs {bench}"],
          rows, [3.6, 0.9, 0.9, 1.2, 1.1, 1.1, 1.48], row_h=min(0.34, 5.0 / (len(rows) + 1)), size=9.5, styles=st)
    source(s, asof, f"Counts of stocks; medians of the stock values. RS 3m: 3-month change of price ÷ {bench}.{bench_note}" + insuf_note)

    # momentum map
    s = deck.titled(f"Momentum map: {int(((df.vs200 > 0) & (df.rs_chg63 > 0)).sum())} stocks above their 200-day and gaining on the {bench}",
                    f"Absolute trend (x) against relative momentum (y); colour = trend verdict")
    mp = momentum_map(df, work / "momentum_map.png", bench)
    chart_image(s, mp, X0, 2.4, W)
    source(s, asof, "Green: Bullish. Purple: Bearish. Blue: Neutral or no verdict. Labels: Bloomberg tickers.")

    # dashboards by sub-sector
    for b in bk:
        x = _sort(g[b])
        xb = int((x.verdict == "Bullish").sum())
        xo = int((x.rs_trend == "outperforming").sum())
        pages = max(1, -(-len(x) // max_rows))
        per = -(-len(x) // pages)
        for p in range(pages):
            part = x.iloc[p * per:(p + 1) * per]
            sfx = f" ({p + 1}/{pages})" if pages > 1 else ""
            momentum_dashboard(deck, part, f"{b}: {xb} of {len(x)} Bullish, {xo} with RS Mom + against the {bench}{sfx}", bench, asof,
                               f"Sorted by trend verdict, then RS Mom, then RS 3m. Changes on closing prices, total return not included. "
                               f"vs 52w high in green when within 5%. Syz list: Focus List / Master list{lists_asof}, shown for information, "
                               f"not part of the verdict.{bench_note}" + (insuf_note if set(insufficient) & set(part.name) else ""))

    # relative-strength ranking: 15 leaders and 15 laggards
    rk = df.dropna(subset=["rs_chg63"]).sort_values("rs_chg63")
    sel = pd.concat([rk.head(15), rk.tail(15)])
    s = deck.titled(f"Relative strength: the 15 leaders and the 15 laggards against the {bench}",
                    f"3-month change in relative strength (price ÷ {bench}), %")
    for k, (part, lab) in enumerate(((rk.tail(15), "Leaders"), (rk.head(15).iloc[::-1], "Laggards"))):
        part = part.sort_values("rs_chg63")
        cd = CategoryChartData()
        cd.categories = list(part.name)
        cd.add_series("RS 3m", [round(v * 100, 1) for v in part.rs_chg63])
        gx = X0 + k * 5.2
        text(s, gx, 2.4, 5.0, 0.3, lab, size=11, color=MINT if k == 0 else MULB, bold=True)
        gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(gx), Inches(2.7), Inches(5.0), Inches(4.75), cd)
        ch = gf.chart
        ch.has_legend = False
        ch.has_title = False
        ch.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW
        ch.category_axis.tick_labels.font.size = Pt(8)
        pl = ch.plots[0]
        pl.gap_width = 40
        pl.has_data_labels = True
        pl.data_labels.font.size = Pt(7.5)
        pl.data_labels.number_format = '+0.0;–0.0'
        pl.data_labels.number_format_is_linked = False
        for i, v in enumerate(part.rs_chg63):
            pt = ch.series[0].points[i]
            pt.format.fill.solid()
            pt.format.fill.fore_color.rgb = rgb(MINT if v >= 0 else MULB)
        ch.value_axis.visible = False
        ch.value_axis.has_major_gridlines = False
    source(s, asof, f"Median of all constituents: {_p(rk.rs_chg63.median())}.{bench_note}")

    # trend × RS grid
    bull_lag = ok[(ok.verdict == "Bullish") & (ok.rs_trend == "underperforming")]
    s = deck.titled(f"{len(bull_lag)} stocks are in an uptrend while their relative-strength trend points down",
                    f"Trend verdict against relative strength versus the {bench}")
    rows, st = [], {}
    cols = ["outperforming", "underperforming"]
    for i, v in enumerate(["Bullish", "Neutral+", "Neutral", "Neutral-", "Bearish"]):
        row = [f"{VGLYPH[v]} {VLABEL[v]}"]
        st[(i, 0)] = verdict_style(v)
        for j, ct in enumerate(cols, start=1):
            nm = ok[(ok.verdict.replace("Bearish_LM", "Bearish") == v) & (ok.rs_trend == ct)].sort_values("name").name.tolist()
            row.append(", ".join(nm) or EN_DASH)
            st[(i, j)] = {"fill": {"outperforming": "E3F4EF", "underperforming": "F6E8EF"}[ct], "align": PP_ALIGN.LEFT}
        rows.append(row)
    # row height follows the longest cell (about 95 characters per line at 8 pt in 4.4 in), 4.95 in in total
    lines = [max(1, max(-(-len(c) // 95) for c in r[1:])) for r in rows]
    unit = min(0.2, (4.95 - 0.3) / sum(l + 1 for l in lines))
    gt = table(s, X0, 2.5, W, ["Trend", f"RS Mom + (gaining on the {bench})", f"RS Mom − (losing to the {bench})"], rows,
               [1.45, 4.4, 4.43], row_h=0.3, size=8, styles=st)
    for i, l in enumerate(lines, start=1):
        gt.rows[i].height = Inches(unit * (l + 1))
    source(s, asof, f"RS Mom: direction of the 200-day average of relative strength (stock ÷ {bench}) over 20 trading days." + insuf_note)

    # trigger watch
    tw = trigger_watch(df)
    n_tw = len(tw)
    if trigger_cap and n_tw > trigger_cap:
        tw = tw.iloc[:trigger_cap]
    s = deck.titled(f"Trigger watch: {n_tw} stocks within 2% of a 52-week or 100-day high or low",
                    "Where a breakout or a breakdown is closest" + (f" – the {len(tw)} nearest shown" if len(tw) < n_tw else ""))
    rows, st = [], {}
    for i, r in enumerate(tw.itertuples()):
        rows.append([r.name, num(r.close, r.decimals), r.kind, num(r.level, r.decimals), pct(r.dist, 2), _vtxt(r.verdict)])
        st[(i, 5)] = _vstyle(r.verdict)
        st[(i, 4)] = {"color": MINT if r.dist >= 0 else MULB, "bold": True}
    if rows:
        table(s, X0, 2.5, W, ["Stock", "Last", "Level", "Value", "Distance", "Trend"], rows,
              [3.6, 1.3, 1.7, 1.3, 1.0, 1.38], row_h=min(0.3, 5.0 / (len(rows) + 1)), size=9.5 if len(rows) < 18 else 8, styles=st)
    source(s, asof, "52-week levels: prior 52 weeks, last close excluded. 100-day high / low: highest / lowest close of the prior 100 trading days.")

    # method
    s = deck.titled("How to read the verdicts", "One rule set, applied to every stock")
    items = [("Trend", "Direction of the 200-day moving average over the last 20 trading days: rising, flat or falling."),
             ("Structure", "A support break (a close below the 52-week low or the 100-day low) stands until a resistance break."),
             ("Verdict", "Rising trend + intact support = Bullish. Falling trend + broken support = Bearish. In between: Neutral, with a tilt."),
             ("Absolute momentum", "Price against its 200-day average; 1-, 3- and 12-month price change; distance from the 52-week high."),
             ("Relative strength", f"RS Mom: is the 200-day average of price ÷ {bench} rising (+) or falling (−)? The 3-month change is the early warning. It informs, it does not change the verdict.")]
    for k, (lab, body) in enumerate(items):
        y = 2.55 + k * 0.98
        box(s, X0, y, 2.2, 0.8, NAVY if k % 2 else ORANGE)
        text(s, X0 + 0.12, y, 2.0, 0.8, lab, size=12, color="FFFFFF", bold=True, anchor=MSO_ANCHOR.MIDDLE)
        text(s, X0 + 2.4, y, 7.85, 0.8, body, size=11, anchor=MSO_ANCHOR.MIDDLE)
    source(s, asof)

    # charts: by sub-sector, in dashboard order
    for b in bk:
        for r in _sort(g[b]).itertuples():
            if r.ticker in charts:
                full_page_chart(deck, charts[r.ticker])
