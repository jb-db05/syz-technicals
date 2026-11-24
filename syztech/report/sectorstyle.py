"""Sectors & style across four regions (US, Europe, Japan, Emerging Markets): technical review.

Cover · key readings · regions against the MSCI ACWI · global sector heatmap · style & size ratios ·
one section per region (dashboard, rotation map, industries for the US and Europe) · method ·
every chart · legal disclaimer. Facts and the rule that fired only – no interpretation prose.

Style and size are read as ratios (e.g. S&P 500 Growth ÷ Value, rebased to 100): the trend engine is applied
to the ratio itself, so a Bullish ratio means the numerator leads by the same rules as any price.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

from ..charts.syz_style import FONT, register_fonts
from ..fmt import EN_DASH, num
from ..indicators.ma import sma
from ..indicators.rs import relative_strength
from ..io.bloomberg_prices import SeriesReport
from .listdoc import V_ORDER
from .sectordoc import REL_ORDER, _p, _posneg, _rel, _relstyle, _vstyle, _vtxt
from .weekly import (AMBER, BLUEB, GREY, L_COVER, L_DISCLAIMER, L_FINAL, MINT, MULB, NAVY, ORANGE, SKY, VGLYPH, VLABEL, W, X0,
                     Deck, box, chart_image, full_page_chart, source, table, text, verdict_style)

SECTOR_KEYS = [("EN", "Energy"), ("MT", "Materials"), ("IN", "Industrials"), ("CD", "Consumer Discretionary"),
               ("CS", "Consumer Staples"), ("HC", "Health Care"), ("FN", "Financials"), ("IT", "Information Technology"),
               ("TC", "Communication Services"), ("UT", "Utilities"), ("RE", "Real Estate")]
S5_KEYS = {"S5ENRS": "EN", "S5MATR": "MT", "S5INDU": "IN", "S5COND": "CD", "S5CONS": "CS", "S5HLTH": "HC", "S5FINL": "FN",
           "S5INFT": "IT", "S5TELS": "TC", "S5UTIL": "UT", "S5RLST": "RE"}
# (region, benchmark ticker, benchmark display name, sector group, industry group or None, style group)
REGIONS = [("US", "SPX Index", "S&P 500", "US – Sectors", "US – Industry groups", "US – Style & size"),
           ("Europe", "MXEU Index", "MSCI Europe", "Europe – Sectors (MSCI)", "Europe – Stoxx 600 supersectors", "Europe – Style & size"),
           ("Japan", "MXJP Index", "MSCI Japan", "Japan – Sectors (MSCI)", None, "Japan – Style & size"),
           ("EM", "MXEF Index", "MSCI EM", "EM – Sectors (MSCI)", None, "EM – Style & size")]
REGION_NAME = {"US": "United States", "Europe": "Europe", "Japan": "Japan", "EM": "Emerging markets"}
# style & size ratios: (region, numerator, denominator, display name, numerator label, denominator label)
RATIOS = [("US", "SGX Index", "SVX Index", "US Growth ÷ Value", "Growth", "Value"),
          ("US", "RTY Index", "SPX Index", "US Small ÷ Large caps", "Small caps", "Large caps"),
          ("US", "MID Index", "SPX Index", "US Mid ÷ Large caps", "Mid caps", "Large caps"),
          ("US", "SPW Index", "SPX Index", "US Equal ÷ Cap weight", "Equal weight", "Cap weight"),
          ("US", "NDX Index", "SPX Index", "Nasdaq 100 ÷ S&P 500", "Nasdaq 100", "S&P 500"),
          ("US", "QUAL US Equity", "SPX Index", "US Quality ÷ S&P 500", "Quality", "S&P 500"),
          ("US", "MTUM US Equity", "SPX Index", "US Momentum ÷ S&P 500", "Momentum", "S&P 500"),
          ("US", "USMV US Equity", "SPX Index", "US Min Vol ÷ S&P 500", "Min Vol", "S&P 500"),
          ("Europe", "MXEU000G Index", "MXEU000V Index", "Europe Growth ÷ Value", "Growth", "Value"),
          ("Europe", "SCXP Index", "SXXP Index", "Europe Small ÷ Stoxx 600", "Small caps", "Large caps"),
          ("Europe", "MCXP Index", "SXXP Index", "Europe Mid ÷ Stoxx 600", "Mid caps", "Large caps"),
          ("Japan", "MXJP000G Index", "MXJP000V Index", "Japan Growth ÷ Value", "Growth", "Value"),
          ("Japan", "TPXSM Index", "TPXC30 Index", "Japan Small ÷ Core 30", "Small caps", "Large caps"),
          ("Japan", "NKY Index", "TPX Index", "Nikkei 225 ÷ TOPIX", "Nikkei 225", "TOPIX"),
          ("EM", "MXEF000G Index", "MXEF000V Index", "EM Growth ÷ Value", "Growth", "Value")]
BENCH_NAMES = {"MXWD Index": "MSCI ACWI", "SPX Index": "S&P 500", "MXEU Index": "MSCI Europe", "MXJP Index": "MSCI Japan",
               "MXEF Index": "MSCI EM", "SXXP Index": "Stoxx 600", "TPX Index": "TOPIX"}
MAP_LABELS = {"Capital Goods": "Capital goods", "Commercial & Professional Services": "Comm. & prof. services",
              "Transportation": "Transport", "Automobiles & Components": "Autos", "Consumer Durables & Apparel": "Cons. durables",
              "Consumer Services": "Cons. services", "Consumer Discretionary Distribution & Retail": "Discretionary retail",
              "Consumer Staples Distribution & Retail": "Staples retail", "Food, Beverage & Tobacco": "Food & bev.",
              "Household & Personal Products": "Household prod.", "Health Care Equipment & Services": "HC equip. & serv.",
              "Pharmaceuticals, Biotechnology & Life Sciences": "Pharma & biotech", "Financial Services": "Fin. services",
              "Software & Services": "Software", "Technology Hardware & Equipment": "Tech hardware",
              "Semiconductors & Semiconductor Equipment": "Semis", "Telecommunication Services": "Telecom",
              "Media & Entertainment": "Media & ent.", "Personal Care, Drug & Grocery Stores": "Personal care & grocery",
              "Industrial Goods & Services": "Industrial goods", "Construction & Materials": "Construction",
              "Consumer Discretionary": "Cons. discretionary", "Consumer Staples": "Cons. staples",
              "Information Technology": "IT", "Communication Services": "Comm. services", "Emerging Markets": "EM"}
STALE_DAYS = 10            # a series whose last close is older than this (vs the export's last date) is left out


def ratio_key(num_t: str, den_t: str) -> str:
    return f"{num_t} ÷ {den_t}"


def add_ratio(prices, num_t: str, den_t: str) -> str | None:
    """Append num ÷ den (common dates only, rebased to 100 at the first common date) as a series. None if missing."""
    if num_t not in prices.reports or den_t not in prices.reports:
        return None
    a, b = prices.series(num_t), prices.series(den_t)
    both = pd.concat([a, b], axis=1, join="inner").dropna()
    if both.empty:
        return None
    r = both.iloc[:, 0] / both.iloc[:, 1]
    r = r / r.iloc[0] * 100.0
    key = ratio_key(num_t, den_t)
    add = pd.DataFrame({"date": r.index, "ticker": key, "close": r.to_numpy()})
    prices.prices = pd.concat([prices.prices[prices.prices.ticker != key], add], ignore_index=True)
    prices.reports[key] = SeriesReport(ticker=key, source="ratio of two export series", name=key, raw_rows=len(r),
                                       first=r.index[0], last=r.index[-1], bars=len(r))
    return key


def build_universe(base: pd.DataFrame, prices, asof) -> tuple[pd.DataFrame, list[str]]:
    """Base template universe + 52-week levels + region / sector keys + ratio rows. Stale series are left out."""
    end_all = pd.Timestamp(asof)
    rows, dropped = [], []
    region_of = {}
    for reg, bench, _, sg, ig, styg in REGIONS:
        for g in (sg, ig, styg):
            if g:
                region_of[g] = reg
    for r in base.to_dict("records"):
        t = r["ticker"]
        if t not in prices.reports or prices.reports[t].bars == 0:
            dropped.append(f"{r['name']} ({t}): no prices")
            continue
        s = prices.series(t).dropna()
        if (end_all - s.index[-1]).days > STALE_DAYS:
            dropped.append(f"{r['name'].replace(' (ticker to confirm)', '')} ({t}): last close {s.index[-1].date()}, series discontinued")
            continue
        r = dict(r)
        r["name"] = str(r["name"]).replace(" (ticker to confirm)", "")
        r["region"] = "Global" if r["group"] == "Regions" else region_of.get(r["group"], "")
        code = t.split()[0]
        r["sector_key"] = S5_KEYS.get(code) or (code[5:7] if code.startswith("MX") and len(code) == 7 and code[4] == "0" else None)
        if t == "SPX Index":                     # the S&P 500 also reads against the ACWI (both USD)
            r["benchmark"] = "MXWD Index"
        rows.append(r)
    for reg, n_t, d_t, name, _, _ in RATIOS:
        key = add_ratio(prices, n_t, d_t)
        if key is None:
            dropped.append(f"{name}: a leg has no prices")
            continue
        rows.append(dict(ticker=key, name=name, asset_class="index", group=f"{reg} – Ratios", benchmark=None, decimals=1,
                         region=reg, sector_key=None))
    u = pd.DataFrame(rows)
    for c in ("support", "resistance", "support_origin", "resistance_origin", "levels_asof"):
        u[c] = None
    u = u.astype(object)
    for i, r in u.iterrows():
        s = prices.series(r.ticker).dropna()
        s = s[s.index <= end_all]
        end = s.index[-1]
        w = s[(s.index > end - pd.Timedelta(weeks=52)) & (s.index < end)]
        if float(s.iloc[-1]) < 10:                # e.g. MSCI Japan sectors in USD (about 2.0): two decimals
            u.loc[i, "decimals"] = 2
        u.loc[i, ["support", "resistance", "support_origin", "resistance_origin", "levels_asof"]] = [
            float(w.min()), float(w.max()), f"52w low ({w.idxmin().date()})", f"52w high ({w.idxmax().date()})", str(end.date())]
    return u, dropped


def rotation_points(prices, tickers: list[str], bench: str, tail: int = 4, step: int = 5) -> pd.DataFrame:
    """x = RS vs its 200-day average (%), y = 3-month change in RS (%), now and `tail` weekly steps back."""
    out = []
    b = prices.series(bench)
    for t in tickers:
        rs = relative_strength(prices.series(t), b)
        if len(rs) < 200 + 63 + tail * step + 1:
            continue
        ma = sma(rs, 200)
        for k in range(tail, -1, -1):
            i = len(rs) - 1 - k * step
            out.append(dict(ticker=t, k=k, x=(rs.iloc[i] / ma.iloc[i] - 1) * 100, y=(rs.iloc[i] / rs.iloc[i - 63] - 1) * 100))
    return pd.DataFrame(out)


def rotation_map(pts: pd.DataFrame, labels: dict, verdicts: dict, out: Path, bench_name: str, size=(10.28, 4.95)) -> Path:
    """Rotation map: relative trend (x) against relative momentum (y), with a four-week tail."""
    register_fonts()
    plt.rcParams["font.family"] = FONT
    col = {"Bullish": "#3BAF90", "Bearish": "#AC5D85", "Bearish_LM": "#AC5D85"}
    fig, ax = plt.subplots(figsize=size, dpi=200)
    ax.axhline(0, color="#B8BFCC", lw=0.9)
    ax.axvline(0, color="#B8BFCC", lw=0.9)
    for t, g in pts.groupby("ticker"):
        g = g.sort_values("k", ascending=False)
        c = col.get(verdicts.get(t), "#4B5F80")
        ax.plot(g.x, g.y, color=c, lw=1.0, alpha=0.45, zorder=2)
        ax.scatter(g.x.iloc[:-1], g.y.iloc[:-1], s=8, color=c, alpha=0.35, zorder=2)
        ax.scatter(g.x.iloc[-1:], g.y.iloc[-1:], s=46, color=c, edgecolors="white", linewidths=0.8, zorder=3)
        ax.annotate(labels.get(t, t), (g.x.iloc[-1], g.y.iloc[-1]), xytext=(4, 4), textcoords="offset points", fontsize=7,
                    color="#202945")
    xl, yl = ax.get_xlim(), ax.get_ylim()
    m = max(abs(xl[0]), abs(xl[1])) * 1.05, max(abs(yl[0]), abs(yl[1])) * 1.05
    ax.set_xlim(-m[0], m[0])
    ax.set_ylim(-m[1], m[1])
    kw = dict(fontsize=9, fontweight="bold", alpha=0.9)
    ax.text(m[0], m[1], "Leading", ha="right", va="top", color="#3BAF90", **kw)
    ax.text(m[0], -m[1], "Weakening", ha="right", va="bottom", color="#4B5F80", **kw)
    ax.text(-m[0], -m[1], "Lagging", ha="left", va="bottom", color="#AC5D85", **kw)
    ax.text(-m[0], m[1], "Improving", ha="left", va="top", color="#4B5F80", **kw)
    ax.set_xlabel(f"Relative strength vs its 200-day average, % (against the {bench_name})", fontsize=8.5, color="#202945")
    ax.set_ylabel("Relative strength, 3-month change, %", fontsize=8.5, color="#202945")
    ax.tick_params(labelsize=7.5, colors="#4B5F80")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("#B8BFCC")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    return out


def _sort(df):
    df = df.copy()
    df["vo"] = df.verdict.map(V_ORDER).fillna(9)
    df["ro"] = df.rel_state.map(REL_ORDER).fillna(9)
    return df.sort_values(["vo", "ro", "rs_chg63"], ascending=[True, True, False])


PREFIXES = ("S&P 500 ", "Stoxx 600 ", "MSCI Europe ", "MSCI Japan ", "MSCI EM ")


def short_name(n: str) -> str:
    for p in PREFIXES:
        if n.startswith(p):
            return n[len(p):]
    return n


SLOPE_TXT = {"rising": "▲ Rising", "flat": "◆ Flat", "falling": "▼ Falling"}
SLOPE_COL = {"rising": MINT, "flat": BLUEB, "falling": MULB}
REL_TXT = {"Outperform": "▲ Outperform", "Neutral": "◆ Neutral", "Underperform": "▼ Underperform"}
REL_COLOUR = {"Outperform": MINT, "Neutral": BLUEB, "Underperform": MULB}
_NA = {"fill": "E9ECF1", "color": GREY, "align": PP_ALIGN.CENTER}


def _badge(colour):
    """Same look as the trend verdict cell: white bold text on the Syz colour."""
    return {"fill": colour, "color": "FFFFFF", "bold": True, "align": PP_ALIGN.CENTER}


def _slope_cell(v):
    return (SLOPE_TXT[v], _badge(SLOPE_COL[v])) if v in SLOPE_TXT else (EN_DASH, _NA)


def _rel_cell(v):
    return (REL_TXT[v], _badge(REL_COLOUR[v])) if v in REL_TXT else (EN_DASH, _NA)


def index_table(deck, df, title, subtitle, bench, asof, note, rs=True, first_is_bench=False, strip=True):
    """Index dashboard: absolute momentum, relative strength against `bench`, trend verdict. The subtitle goes to the
    footnote (the column-group labels sit where a subtitle would)."""
    s = deck.titled(title, "")
    note = f"{subtitle}. {note}" if subtitle else note
    hdr = ["Index", "200-day", "vs 200d", "1m", "3m", "12m", "vs 52w high"] + (["Rel. trend", "RS 3m"] if rs else []) + ["Trend"]
    col_w = [2.6, 1.0, 0.75, 0.7, 0.7, 0.75, 0.9] + ([1.3, 0.75] if rs else []) + [1.15]
    k = sum(col_w)
    col_w = [w_ * W / k for w_ in col_w]
    xs = [X0 + sum(col_w[:j]) for j in range(len(col_w) + 1)]
    groups = [("Absolute momentum", 1, 6, NAVY)] + ([(f"vs {bench}", 7, 8, ORANGE)] if rs else []) + [("Verdict", len(hdr) - 1, len(hdr) - 1, BLUEB)]
    for lab, a_, b_, col in groups:
        box(s, xs[a_] + 0.02, 2.2, xs[b_ + 1] - xs[a_] - 0.04, 0.24, col, radius=0.25)
        text(s, xs[a_], 2.2, xs[b_ + 1] - xs[a_], 0.24, lab, size=9, color="FFFFFF", bold=True, align=PP_ALIGN.CENTER,
             anchor=MSO_ANCHOR.MIDDLE)
    rows, st = [], {}
    for i, r in enumerate(df.itertuples()):
        is_b = first_is_bench and i == 0
        stxt, sst = _slope_cell(r.slope200)
        rtxt, rst = _rel_cell(r.rel_state)
        row = [r.name if (is_b or not strip) else short_name(r.name), stxt, _p(r.vs200), _p(r.chg1m), _p(r.chg3m), _p(r.chg12m),
               _p(r.from_hi52)]
        if rs:
            row += [EN_DASH if is_b else rtxt, EN_DASH if is_b else _p(r.rs_chg63)]
        row.append(_vtxt(r.verdict))
        rows.append(row)
        st[(i, 0)] = {"bold": is_b, "align": PP_ALIGN.LEFT}
        for j, v in ((2, r.vs200), (3, r.chg1m), (4, r.chg3m), (5, r.chg12m)):
            st[(i, j)] = _posneg(v)
        st[(i, 6)] = {"color": MINT if (pd.notna(r.from_hi52) and r.from_hi52 >= -0.05) else NAVY, "align": PP_ALIGN.RIGHT}
        if rs and not is_b:
            st[(i, 7)] = rst
            st[(i, 8)] = _posneg(r.rs_chg63)
        if is_b:
            for j in range(len(hdr) - 1):
                st[(i, j)] = {**st.get((i, j), {}), "fill": "FFE9D6"}
        st[(i, 1)] = sst
        st[(i, len(hdr) - 1)] = _vstyle(r.verdict)
    rh = min(0.32, 5.0 / (len(rows) + 1))
    table(s, X0, 2.5, W, hdr, rows, col_w, row_h=rh, size=9.5 if rh >= 0.26 else 8, styles=st)
    source(s, asof, note)
    return s


def _family(v):
    return "Bullish" if v == "Bullish" else "Bearish" if str(v).startswith("Bearish") else "Neutral" if v in VGLYPH else None


def key_readings(df: pd.DataFrame):
    """Facts for the key-readings page: Bullish regions, regions that Outperform, and three columns of bullet lines."""
    by_t = df.set_index("ticker")
    sect = df[df.sector_key.notna() & df.group.str.contains("Sectors", na=False)]
    ratios = df[df.group.str.endswith("Ratios", na=False)]
    acwi = by_t.loc["MXWD Index"] if "MXWD Index" in by_t.index else None
    reg_t = (("US", "MXUS Index"), ("Europe", "MXEU Index"), ("Japan", "MXJP Index"), ("EM", "MXEF Index"))
    nb_reg = [REGION_NAME[r] for r, t in reg_t if t in by_t.index and by_t.loc[t].verdict == "Bullish"]
    out_reg = [REGION_NAME[r] for r, t in reg_t if t in by_t.index and by_t.loc[t].rel_state == "Outperform"]
    cols = [("Regions", [f"Bullish: {', '.join(nb_reg) or 'none'}.", f"Outperform against the ACWI: {', '.join(out_reg) or 'none'}."]
             + ([f"MSCI ACWI: {VLABEL.get(acwi.verdict, acwi.verdict)}, {_p(acwi.vs200)} vs its 200-day."] if acwi is not None else []))]
    lines = []
    for reg, bench, bname, sg, *_ in REGIONS:
        x = sect[sect.group == sg]
        if len(x):
            lead = x.sort_values("rs_chg63", ascending=False).iloc[0]
            lines.append(f"{REGION_NAME[reg]}: {int((x.verdict == 'Bullish').sum())} of {len(x)} Bullish; "
                         f"RS 3m leader {short_name(lead['name'])} ({_p(lead.rs_chg63)}).")
    cols.append(("Sectors", lines))
    lines = []
    for r in ratios.itertuples():
        spec = next(x for x in RATIOS if x[3] == r.name)
        fam = _family(r.verdict)
        if fam == "Bullish":
            lines.append(f"{r.name}: uptrend – {spec[4]} leads.")
        elif fam == "Bearish":
            lines.append(f"{r.name}: downtrend – {spec[5]} leads.")
    cols.append(("Style & size (ratio trends)", lines or ["No ratio in a Bullish or Bearish trend."]))
    return nb_reg, out_reg, cols


def build_sector_style(df: pd.DataFrame, charts: dict, maps: dict, out: Path, template: Path, *, edition: str, asof: str,
                       dropped: list[str], draft: bool = True) -> Path:
    """df: one row per universe ticker with instrument_table + add_momentum columns and region / sector_key / group."""
    deck = Deck(template)
    by_t = df.set_index("ticker")
    gl = lambda g: df[df.group == g]
    regions = gl("Regions")
    acwi = by_t.loc["MXWD Index"] if "MXWD Index" in by_t.index else None
    sect = df[df.sector_key.notna() & df.group.str.contains("Sectors", na=False)]
    ratios = df[df.group.str.endswith("Ratios", na=False)]
    drop_note = (" Left out: " + "; ".join(dropped) + ".") if dropped else ""
    rs_note = "Rel. trend: the trend rule applied to index ÷ benchmark (Outperform / Neutral / Underperform); RS 3m: 3-month change in relative strength."

    # ── cover
    s = deck.slide(L_COVER)
    for ph in list(s.placeholders):
        i = ph.placeholder_format.idx
        if i == 0:
            ph.text = "Sectors & Style – Technical review"
        elif i == 13:
            ph.text = edition.upper()
        else:
            ph._element.getparent().remove(ph._element)
    box(s, 5.85, 0, 5.85, 8.27, NAVY, radius=0)
    text(s, 6.45, 1.7, 4.8, 0.4, "FOUR REGIONS AGAINST THE MSCI ACWI", size=11, color=AMBER, bold=True)
    for k, (reg, bench, bname, *_rest) in enumerate(REGIONS):
        t = {"US": "MXUS Index", "Europe": "MXEU Index", "Japan": "MXJP Index", "EM": "MXEF Index"}[reg]
        if t not in by_t.index:
            continue
        r = by_t.loc[t]
        fam = _family(r.verdict)
        col = {"Bullish": MINT, "Bearish": "E6A4AD"}.get(fam, SKY)
        y = 2.35 + k * 1.05
        text(s, 6.45, y, 2.6, 0.5, REGION_NAME[reg], size=16, color="FFFFFF", bold=True)
        text(s, 6.45, y + 0.42, 4.6, 0.4, [[(f"{VGLYPH.get(r.verdict, '')} {VLABEL.get(r.verdict, r.verdict)}", {"color": col, "bold": True}),
                                           (f"   {_rel(r.rel_state)} · RS 3m {_p(r.rs_chg63)}", {"color": "C9D1E2"})]], size=11)
    text(s, 6.45, 6.75, 4.6, 0.3, f"{len(sect)} sector indices · {len(ratios)} style & size ratios", size=10, color=GREY)
    text(s, 0.73, 7.45, 4.8, 0.3, "Florian Marini, CFA, CMT – Head of Research", size=10, color=BLUEB)
    if draft:
        text(s, 0.73, 4.75, 4.8, 0.3, "DRAFT – FOR INTERNAL REVIEW", size=10, color=ORANGE, bold=True)

    # ── key readings (facts only)
    nb_reg, out_reg, cols = key_readings(df)
    s = deck.titled(f"Key readings: {len(nb_reg)} of 4 regions Bullish, {len(out_reg)} Outperform against the MSCI ACWI",
                    "Rules-based facts from the trend engine; no published view")
    est = max(sum(-(-len(l) // 44) for l in ls) for _, ls in cols)        # wrapped lines at 10 pt in 3.0 in
    bh = min(4.45, 0.3 + est * 0.19)
    for k, (lab, ls) in enumerate(cols):
        x0 = X0 + k * 3.47
        box(s, x0, 2.45, 3.3, 0.42, NAVY if k % 2 else ORANGE)
        text(s, x0 + 0.15, 2.45, 3.0, 0.42, lab, size=11.5, color="FFFFFF", bold=True, anchor=MSO_ANCHOR.MIDDLE)
        box(s, x0, 2.95, 3.3, bh, "F6F7F9")
        text(s, x0 + 0.15, 3.07, 3.0, bh - 0.15, [[("• " + l, {})] for l in ls], size=10 if est < 20 else 9)
    source(s, asof, "Ratio trends: the trend rules applied to the ratio of the two indices; Neutral ratios are not listed." + drop_note)

    # ── regions against the ACWI
    reg_df = pd.concat([regions[regions.ticker == "MXWD Index"], _sort(regions[regions.ticker != "MXWD Index"])])
    index_table(deck, reg_df, f"Regions: {len(out_reg)} of 4 Outperform against the MSCI ACWI",
                "MSCI indices in USD; relative strength against the MSCI ACWI", "MSCI ACWI", asof, rs_note, first_is_bench=True)
    if "regions" in maps:
        s = deck.titled("Rotation of the regions against the MSCI ACWI", "Relative trend (x) against relative momentum (y); tails: last four weeks")
        chart_image(s, maps["regions"], X0, 2.4, W)
        source(s, asof, "x: relative strength vs its own 200-day average. y: 3-month change of relative strength. Dots: weekly positions. "
                        "Colour: trend verdict of the index.")

    # ── global sector map: three readings (200-day momentum, relative trend, verdict), one page each
    hdr = ["Sector"] + [REGION_NAME[r[0]] for r in REGIONS]
    n_sect = len(sect)
    views = [
        ("momentum", lambda r: (f"{SLOPE_TXT[r.slope200]}\nvs 200d {_p(r.vs200)}", _badge(SLOPE_COL[r.slope200])) if r.slope200 in SLOPE_TXT else (EN_DASH, _NA),
         f"Global sector map – momentum: {int((sect.slope200 == 'rising').sum())} of {n_sect} sector indices with a rising 200-day average",
         "Direction of the 200-day average over 20 trading days (cell colour); second line: price against its 200-day average",
         "Rising / flat / falling: 20-day change of the 200-day average above +0.20%, within ±0.20%, below −0.20%.".replace("−", EN_DASH)),
        ("relative", lambda r: (f"{REL_TXT[r.rel_state]}\nRS 3m {_p(r.rs_chg63)}", _badge(REL_COLOUR[r.rel_state])) if r.rel_state in REL_TXT else (EN_DASH, _NA),
         f"Global sector map – relative trend: {int((sect.rel_state == 'Outperform').sum())} of {n_sect} sector indices Outperform their regional benchmark",
         "Relative trend against the regional benchmark (cell colour); second line: 3-month change in relative strength",
         rs_note),
        ("verdict", lambda r: (_vtxt(r.verdict), verdict_style(r.verdict)) if _family(r.verdict) else ("n/a – history", _NA),
         f"Global sector map – verdict: {int((sect.verdict == 'Bullish').sum())} of {n_sect} sector indices Bullish",
         "Trend verdict per sector and region",
         "Verdict: rising 200-day + intact support + 50-day above the 200-day = Bullish; falling 200-day + broken support = Bearish; in between Neutral with a tilt."),
    ]
    for _, cell, title_, sub_, note_ in views:
        rows, st = [], {}
        for i, (key, sname) in enumerate(SECTOR_KEYS):
            row = [sname]
            st[(i, 0)] = {"bold": True, "align": PP_ALIGN.LEFT}
            for j, (reg, bench, bname, sg, *_r) in enumerate(REGIONS, start=1):
                x = sect[(sect.group == sg) & (sect.sector_key == key)]
                if not len(x):
                    row.append("n/a – series discontinued")
                    st[(i, j)] = dict(_NA)
                    continue
                txt, sty = cell(x.iloc[0])
                row.append(txt)
                st[(i, j)] = sty
            rows.append(row)
        s = deck.titled(title_, sub_)
        table(s, X0, 2.5, W, hdr, rows, [2.28, 2.0, 2.0, 2.0, 2.0], row_h=0.41, size=9, styles=st)
        source(s, asof, "Benchmarks: US – S&P 500 sectors vs S&P 500; Europe, Japan, EM – MSCI sector indices vs the regional MSCI index "
                        "(USD). " + note_ + drop_note)

    # ── style & size ratios
    hdr = ["Ratio", "Ratio trend", "200-day", "vs 200d", "3m", "12m", "Leads (trend rule)"]
    rows, st = [], {}
    rt = ratios.copy()
    rt["ord"] = rt.region.map({r[0]: i for i, r in enumerate(REGIONS)})
    rt = rt.sort_values(["ord"], kind="stable")
    for i, r in enumerate(rt.itertuples()):
        spec = next(x for x in RATIOS if x[3] == r.name)
        fam = _family(r.verdict)
        lead = spec[4] if fam == "Bullish" else spec[5] if fam == "Bearish" else "No trend lead"
        stxt, sst = _slope_cell(r.slope200)
        rows.append([r.name, _vtxt(r.verdict), stxt, _p(r.vs200), _p(r.chg3m), _p(r.chg12m), lead])
        st[(i, 1)] = _vstyle(r.verdict)
        st[(i, 2)] = sst
        for j, v in ((3, r.vs200), (4, r.chg3m), (5, r.chg12m)):
            st[(i, j)] = _posneg(v)
        st[(i, 6)] = {"bold": fam in ("Bullish", "Bearish"), "color": NAVY if fam in ("Bullish", "Bearish") else GREY}
    s = deck.titled(f"Style & size: {sum(1 for r in rt.itertuples() if _family(r.verdict) in ('Bullish', 'Bearish'))} of {len(rt)} "
                    f"ratios in a defined trend", "The trend rules applied to each ratio (numerator ÷ denominator, rebased to 100)")
    table(s, X0, 2.5, W, hdr, rows, [2.9, 1.4, 0.95, 1.0, 0.95, 0.95, 2.13], row_h=min(0.3, 5.0 / (len(rows) + 1)), size=9, styles=st)
    source(s, asof, "Bullish ratio: the numerator leads; Bearish: the denominator leads; Neutral: no trend lead. Quality, Momentum and "
                    "Min Vol: iShares MSCI USA factor ETFs (prices). Ratio charts follow at the end of the document.")

    # ── regions
    for reg, bench, bname, sg, ig, styg in REGIONS:
        b = by_t.loc[bench] if bench in by_t.index else None
        x = _sort(gl(sg))
        if b is not None:
            x = pd.concat([df[df.ticker == bench], x])
        nb = int((gl(sg).verdict == "Bullish").sum())
        no = int((gl(sg).rel_state == "Outperform").sum())
        index_table(deck, x, f"{REGION_NAME[reg]}: {nb} of {len(gl(sg))} sectors Bullish, {no} Outperform against the {bname}",
                    f"{bname} and its sectors{' (USD)' if reg != 'US' else ''}", bname, asof, rs_note + drop_note, first_is_bench=b is not None)
        if f"{reg}_sectors" in maps:
            s = deck.titled(f"{REGION_NAME[reg]}: sector rotation against the {bname}",
                            "Relative trend (x) against relative momentum (y); tails: last four weeks")
            chart_image(s, maps[f"{reg}_sectors"], X0, 2.4, W)
            source(s, asof, "x: relative strength vs its own 200-day average. y: 3-month change of relative strength. Colour: trend verdict.")
        if ig and len(gl(ig)):
            ib = "SXXP Index" if reg == "Europe" else bench
            ibn = BENCH_NAMES.get(ib, ib)
            y = _sort(gl(ig))
            y = y[y.ticker != ib]
            head = df[df.ticker == ib] if reg == "Europe" else pd.DataFrame()
            label = "Stoxx 600 supersectors" if reg == "Europe" else "S&P 500 industry groups"
            index_table(deck, pd.concat([head, y]) if len(head) else y,
                        f"{label}: {int((y.verdict == 'Bullish').sum())} of {len(y)} Bullish, "
                        f"{int((y.rel_state == 'Outperform').sum())} Outperform against the {ibn}",
                        f"{'EUR' if reg == 'Europe' else 'USD'}; sorted by trend verdict, then relative trend, then RS 3m", ibn, asof, rs_note,
                        first_is_bench=len(head) > 0)
            if f"{reg}_industries" in maps:
                s = deck.titled(f"{label}: rotation against the {ibn}", "Relative trend (x) against relative momentum (y); tails: last four weeks")
                chart_image(s, maps[f"{reg}_industries"], X0, 2.4, W)
                source(s, asof, "x: relative strength vs its own 200-day average. y: 3-month change of relative strength. Colour: trend verdict.")
        z = gl(styg)
        z = z[~z.ticker.isin([bench])]
        if len(z):
            index_table(deck, _sort(z), f"{REGION_NAME[reg]} style & size: {int((z.verdict == 'Bullish').sum())} of {len(z)} Bullish",
                        "Each against its own benchmark (shown in the chart); ratios on the style & size page", "benchmark", asof,
                        rs_note + " Benchmarks: " + ", ".join(sorted({BENCH_NAMES.get(v, v) for v in z.benchmark.dropna()})) + ".")

    # ── method
    s = deck.titled("How to read this document", "One rule set, applied to every index and ratio")
    items = [("Trend", "Direction of the 200-day average over 20 trading days; support / resistance = last confirmed swing low / high "
                       "(1.5 × one-month-move reversal); a broken swing low stays the level until the resistance breaks."),
             ("Verdict", "Rising trend + intact support + 50-day above the 200-day = Bullish. Falling trend + broken support = Bearish. In between: Neutral, with a tilt."),
             ("Relative strength", "The same rule applied to index ÷ benchmark: Outperform, Neutral or Underperform. RS 3m: its 3-month change. It informs, it does not change the absolute verdict."),
             ("Ratios", "Style and size as ratios (e.g. Growth ÷ Value, rebased to 100), read with the same trend rules: Bullish = numerator leads."),
             ("Rotation map", "x: relative strength vs its 200-day average; y: its 3-month change. Leading = above and rising; Weakening = above, falling; "
                              "Lagging = below, falling; Improving = below, rising.")]
    for k, (lab, body) in enumerate(items):
        y = 2.5 + k * 0.98
        box(s, X0, y, 2.2, 0.8, NAVY if k % 2 else ORANGE)
        text(s, X0 + 0.12, y, 2.0, 0.8, lab, size=12, color="FFFFFF", bold=True, anchor=MSO_ANCHOR.MIDDLE)
        text(s, X0 + 2.4, y, 7.85, 0.8, body, size=10.5, anchor=MSO_ANCHOR.MIDDLE)
    source(s, asof, "MSCI indices converted to USD by Bloomberg; S&P, Stoxx and TOPIX / Nikkei in local currency." + drop_note)

    # ── charts: regions, then each region (benchmark, sectors, industries, style), then ratios
    order = list(regions.ticker)
    for reg, bench, bname, sg, ig, styg in REGIONS:
        order += [bench] + list(_sort(gl(sg)).ticker) + (list(_sort(gl(ig)).ticker) if ig else []) + list(_sort(gl(styg)).ticker)
    order += list(rt.ticker)
    seen = set()
    for t in order:
        if t in charts and t not in seen:
            seen.add(t)
            full_page_chart(deck, charts[t])
    deck.slide(L_DISCLAIMER)
    deck.slide(L_FINAL)
    deck.save(out)
    return out
