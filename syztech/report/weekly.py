"""Weekly technical document (PowerPoint, Syz A4 template).

Structure: cover, executive summary, verdict map, trigger watch, changes, one section per
asset class (dashboard table + key chart), Equity Focus List, method, appendix of every
chart, legal disclaimer. Figures come from the engine run; words come from the
commentary file the analyst approves.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from ..fmt import EN_DASH, num

NAVY, BLUEB, ORANGE, AMBER = "202945", "4B5F80", "FF6C0E", "FFA400"
MINT, MULB, SKY, GREY, LIGHT = "3BAF90", "AC5D85", "79D6FF", "8A93A6", "EEF0F4"
VCOL = {"Bullish": MINT, "Neutral+": BLUEB, "Neutral": BLUEB, "Neutral-": BLUEB, "Bearish_LM": MULB, "Bearish": MULB}
VGLYPH = {"Bullish": "▲", "Neutral+": "◆", "Neutral": "◆", "Neutral-": "◆", "Bearish_LM": "▼", "Bearish": "▼"}
VLABEL = {"Bullish": "Bullish", "Neutral+": "Neutral +", "Neutral": "Neutral", "Neutral-": "Neutral –",
          "Bearish_LM": "Bearish (LM)", "Bearish": "Bearish"}
SOURCE = "Sources : Syz Research, Bloomberg"
import re as _re
NUMERIC = _re.compile(r"^[+–-]?[\d,.]+(%|bp)?( \(52w\))?$")
L_COVER, L_GRADIENT, L_TITLE, L_DISCLAIMER, L_FINAL, L_BLANK = 1, 0, 21, 22, 24, 26
X0, W = 0.73, 10.28           # content left edge and width (inches), from the template's title placeholder


def rgb(h):
    return RGBColor.from_string(h)


# ---------------------------------------------------------------- data


def instrument_table(scores: pd.DataFrame, universe: pd.DataFrame, prices, trendlines: dict) -> pd.DataFrame:
    """One row per instrument with everything the document shows."""
    u = universe.set_index("ticker")
    rows = []
    for _, r in scores.iterrows():
        t = r.ticker
        if t not in prices.reports or prices.reports[t].bars == 0 or pd.isna(r.get("close")):
            continue
        s = prices.series(t)
        close = float(s.iloc[-1])
        end = s.index[-1]
        w = s[s.index > end - pd.Timedelta(weeks=52)]
        wk = s[s.index <= end - pd.Timedelta(days=7)]
        m3 = s[s.index <= end - pd.DateOffset(months=3)]
        tl_today = None
        for tl in trendlines.get(t, []):
            i0, i1 = s.index.searchsorted(pd.Timestamp(tl.start[0])), s.index.searchsorted(pd.Timestamp(tl.end[0]))
            if i1 <= i0:
                continue
            if (s > 0).all():
                k = (math.log(tl.end[1]) - math.log(tl.start[1])) / (i1 - i0)
                v = math.exp(math.log(tl.start[1]) + k * (len(s) - 1 - i0))
            else:
                v = tl.start[1] + (tl.end[1] - tl.start[1]) * (len(s) - 1 - i0) / (i1 - i0)
            if tl_today is None or abs(close / v - 1) < abs(close / tl_today - 1):
                tl_today = v
        ur = u.loc[t]
        badge = ur.get("badge")
        pub = badge if isinstance(badge, str) and badge else None
        rows.append(dict(
            ticker=t, name=ur["name"], group=ur.get("group"), asset_class=ur.get("asset_class"),
            decimals=int(ur.get("decimals") or 1), close=close, ma200=r.ma200, slope200=r.slope200,
            vs200=close / r.ma200 - 1 if r.ma200 else np.nan,
            support=r.support, s_origin=ur.get("support_origin"), resistance=r.resistance, r_origin=ur.get("resistance_origin"),
            dist_s=close / r.support - 1 if pd.notna(r.support) else np.nan,
            dist_r=close / r.resistance - 1 if pd.notna(r.resistance) else np.nan,
            trendline=tl_today, dist_tl=close / tl_today - 1 if tl_today else np.nan,
            hi52=float(w.max()), lo52=float(w.min()),
            chg1w=close / float(wk.iloc[-1]) - 1 if len(wk) else np.nan,
            chg3m=close / float(m3.iloc[-1]) - 1 if len(m3) else np.nan,
            published=pub, mechanical=r.verdict, lt_view=r.get("lt_view"),
            verdict=pub or r.verdict, verdict_kind="published" if pub else "rules-based",
            rs_trend=r.get("rs_trend"), rs_chg63=r.get("rs_chg63"), benchmark=ur.get("benchmark"),
            last_date=end,
        ))
    return pd.DataFrame(rows)


def triggers(df: pd.DataFrame, band: float = 0.02) -> pd.DataFrame:
    """Instruments within `band` of a level: drawn support / resistance, trendline, 52-week high / low."""
    out = []
    for _, r in df.iterrows():
        cands = []
        for lvl, kind, origin in ((r.support, "support", r.s_origin), (r.resistance, "resistance", r.r_origin)):
            if pd.notna(lvl):
                label = "52-week " + ("low" if kind == "support" else "high") if isinstance(origin, str) and origin.startswith("52w") else kind.capitalize()
                cands.append((lvl, label))
        if r.trendline:
            cands.append((r.trendline, "Trendline"))
        for lvl, label in cands:
            d = r.close / lvl - 1
            if abs(d) <= band:
                out.append(dict(ticker=r.ticker, name=r["name"], verdict=r.verdict, close=r.close, decimals=r.decimals,
                                level=lvl, kind=label, dist=d, asset_class=r.asset_class))
    t = pd.DataFrame(out)
    return t.sort_values("dist", key=lambda s: s.abs()).drop_duplicates("ticker") if len(t) else t


# ---------------------------------------------------------------- slide helpers


class Deck:
    def __init__(self, template: Path):
        self.p = Presentation(str(template))

    def slide(self, layout: int):
        return self.p.slides.add_slide(self.p.slide_layouts[layout])

    def titled(self, title: str, subtitle: str = ""):
        s = self.slide(L_TITLE)
        for ph in s.placeholders:
            i = ph.placeholder_format.idx
            if i == 0:
                ph.text = title
            elif i == 14:
                ph.text = subtitle
        return s

    def save(self, out: Path):
        self.p.save(str(out))


def text(slide, x, y, w, h, runs, size=11, color=NAVY, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    """runs: str or list of paragraphs; a paragraph is str or list of (text, {bold,color,size}) tuples."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    paras = [runs] if isinstance(runs, str) else runs
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        parts = [(para, {})] if isinstance(para, str) else para
        for txt, o in parts:
            r = p.add_run()
            r.text = txt
            r.font.size = Pt(o.get("size", size))
            r.font.bold = o.get("bold", bold)
            r.font.color.rgb = rgb(o.get("color", color))
    return tb


def box(slide, x, y, w, h, fill, line=None, radius=0.08):
    sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.adjustments[0] = radius
    sh.fill.solid()
    sh.fill.fore_color.rgb = rgb(fill)
    if line:
        sh.line.color.rgb = rgb(line)
        sh.line.width = Pt(0.75)
    else:
        sh.line.fill.background()
    sh.shadow.inherit = False
    return sh


def source(slide, asof: str, note: str = ""):
    text(slide, X0, 7.62, 8.5, 0.2, f"{SOURCE}. Data to {asof}.{(' ' + note) if note else ''}", size=7, color=GREY)


def dist(r, level, d=1):
    """Distance of the last close to a level: % for prices, basis points for yields."""
    if level is None or (isinstance(level, float) and math.isnan(level)):
        return EN_DASH
    if r.asset_class == "rate":
        return f"{(r.close - level) * 100:+.0f}bp".replace("-", "–")
    return pct(r.close / level - 1, d)


def pct(x, d=1):
    return EN_DASH if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x * 100:+.{d}f}%".replace("-", "–")


def table(slide, x, y, w, header, rows, col_w, row_h=0.24, size=8.5, styles=None):
    """rows: list of lists of str; styles: dict (row, col) -> {fill, color, bold, align}."""
    styles = styles or {}
    n, m = len(rows) + 1, len(header)
    gt = slide.shapes.add_table(n, m, Inches(x), Inches(y), Inches(w), Inches(row_h * n)).table
    for j, cw in enumerate(col_w):
        gt.columns[j].width = Inches(cw)
    for i in range(n):
        gt.rows[i].height = Inches(row_h)
        for j in range(m):
            c = gt.cell(i, j)
            c.margin_left = c.margin_right = Inches(0.05)
            c.margin_top = c.margin_bottom = Inches(0.01)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            val = header[j] if i == 0 else rows[i - 1][j]
            st = {} if i == 0 else styles.get((i - 1, j), {})
            tf = c.text_frame
            tf.text = ""
            p = tf.paragraphs[0]
            r = p.add_run()
            r.text = str(val)
            r.font.size = Pt(size)
            r.font.bold = (i == 0) or st.get("bold", False)
            r.font.color.rgb = rgb("FFFFFF" if i == 0 else st.get("color", NAVY))
            p.alignment = st.get("align", PP_ALIGN.RIGHT if (i > 0 and j > 0 and NUMERIC.match(str(val))) else PP_ALIGN.LEFT)
            c.fill.solid()
            c.fill.fore_color.rgb = rgb(NAVY if i == 0 else st.get("fill", "FFFFFF" if i % 2 else "F6F7F9"))
    return gt


def verdict_style(v):
    return {"fill": VCOL.get(v, BLUEB), "color": "FFFFFF", "bold": True, "align": PP_ALIGN.CENTER}


def chart_image(slide, path: Path, x, y, w):
    with Image.open(path) as im:
        ratio = im.height / im.width
    slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w), Inches(w * ratio))


# ---------------------------------------------------------------- sections


def dashboard_slide(deck, df, title, subtitle, asof):
    s = deck.titled(title, subtitle)
    hdr = ["Instrument", "Last", "200-day", "vs 200d", "Support", "dist.", "Resistance", "dist.", "1 week", "Verdict"]
    rows, styles = [], {}
    for i, r in enumerate(df.itertuples()):
        d = r.decimals
        s_tag = " (52w)" if isinstance(r.s_origin, str) and r.s_origin.startswith("52w") else ""
        r_tag = " (52w)" if isinstance(r.r_origin, str) and r.r_origin.startswith("52w") else ""
        rows.append([r.name, num(r.close, d), {"rising": "rising", "falling": "falling", "flat": "flat"}.get(r.slope200, EN_DASH),
                     dist(r, r.ma200), num(r.support, d) + s_tag, dist(r, r.support), num(r.resistance, d) + r_tag, dist(r, r.resistance),
                     pct(r.chg1w), f"{VGLYPH.get(r.verdict, '')} {VLABEL.get(r.verdict, r.verdict)}"])
        styles[(i, 9)] = verdict_style(r.verdict)
        if pd.notna(r.dist_s) and r.dist_s < 0:
            styles[(i, 5)] = {"color": MULB, "bold": True}
        if pd.notna(r.dist_r) and r.dist_r > 0:
            styles[(i, 7)] = {"color": MINT, "bold": True}
        styles[(i, 2)] = {"color": {"rising": MINT, "falling": MULB}.get(r.slope200, BLUEB), "align": PP_ALIGN.LEFT}
    n = len(rows)
    rh = min(0.26, 5.0 / (n + 1))
    table(s, X0, 2.55, W, hdr, rows, [2.75, 0.95, 0.7, 0.75, 1.15, 0.65, 1.15, 0.65, 0.68, 1.6],
          row_h=rh, size=8.5 if n <= 16 else 7.5, styles=styles)
    source(s, asof, "Support / resistance: drawn levels; (52w) = 52-week low / high where none is drawn. dist. = last close against the level.")
    return s


def hero_slide(deck, chart: Path, title, asof):
    s = deck.titled(title, "")
    chart_image(s, chart, X0 + 0.2, 2.25, W - 0.4)
    return s


def build(table_df: pd.DataFrame, commentary: dict, charts: dict, out: Path, template: Path, asof: str):
    deck = Deck(template)
    c = commentary
    xa = table_df[~table_df.group.fillna("").str.startswith("Focus List")]
    fl = table_df[table_df.group.fillna("").str.startswith("Focus List")]

    # 1 cover
    s = deck.slide(L_COVER)
    for ph in list(s.placeholders):
        i = ph.placeholder_format.idx
        if i == 0:
            ph.text = "Cross-Asset & Focus List Technicals"
        elif i == 13:
            ph.text = c["edition"].upper()
        else:
            ph._element.getparent().remove(ph._element)          # empty picture placeholder
    box(s, 5.85, 0, 5.85, 8.27, NAVY, radius=0)
    counts = xa.verdict.map(lambda v: "Bullish" if v == "Bullish" else "Bearish" if v.startswith("Bearish") else "Neutral").value_counts()
    text(s, 6.45, 2.2, 4.6, 0.4, "THIS WEEK ACROSS 80 MARKETS", size=11, color=AMBER, bold=True)
    for k, (lab, col) in enumerate((("Bullish", MINT), ("Neutral", SKY), ("Bearish", "E6A4AD"))):
        text(s, 6.45, 2.85 + k * 1.15, 1.6, 0.9, str(int(counts.get(lab, 0))), size=48, color=col, bold=True)
        text(s, 8.15, 3.15 + k * 1.15, 2.6, 0.5, lab, size=16, color="FFFFFF")
    text(s, 0.73, 7.45, 4.8, 0.3, "Florian Marini, CFA, CMT – Head of Research", size=10, color=BLUEB)
    if c.get("draft"):
        text(s, 0.73, 4.75, 4.8, 0.3, "DRAFT – FOR INTERNAL REVIEW", size=10, color=ORANGE, bold=True)

    # 2 executive summary
    s = deck.titled(c["headline"], f"Executive summary – {c['edition']}")
    for k, (lab, body) in enumerate(c["key_messages"]):
        y = 2.6 + k * 0.98
        box(s, X0, y, 1.7, 0.82, ORANGE if k % 2 == 0 else NAVY)
        text(s, X0 + 0.12, y, 1.5, 0.82, lab, size=12, color="FFFFFF", bold=True, anchor=MSO_ANCHOR.MIDDLE)
        text(s, X0 + 1.9, y + 0.04, 8.3, 0.8, body, size=11, anchor=MSO_ANCHOR.MIDDLE)
    source(s, asof)

    # 3 verdict map (native chart)
    order = [("Equities", ["index", "sector"]), ("Rates", ["rate"]), ("FX", ["fx"]), ("Commodities", ["commodity"]), ("Crypto", ["crypto"])]
    cd = CategoryChartData()
    cd.categories = [o[0] for o in order]
    def bucket(v):
        return "Bullish" if v == "Bullish" else "Bearish" if str(v).startswith("Bearish") else "Neutral"
    for lab in ("Bullish", "Neutral", "Bearish"):
        cd.add_series(lab, [(int((xa[xa.asset_class.isin(ac)].verdict.map(bucket) == lab).sum()) or None) for _, ac in order])
    s = deck.titled(f"{int(counts.get('Bullish', 0))} of {len(xa)} markets in an uptrend – Asia and precious metals are the weak spots",
                    "Published verdicts by asset class, number of instruments")
    gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_STACKED, Inches(X0), Inches(2.55), Inches(W), Inches(4.8), cd)
    ch = gf.chart
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.TOP
    ch.legend.include_in_layout = False
    ch.legend.font.size = Pt(10)
    for ser, col in zip(ch.series, (MINT, BLUEB, MULB)):
        ser.format.fill.solid()
        ser.format.fill.fore_color.rgb = rgb(col)
        ser.data_labels.show_value = True
        ser.data_labels.font.size = Pt(10)
        ser.data_labels.font.color.rgb = rgb("FFFFFF")
        ser.data_labels.font.bold = True
    ch.plots[0].gap_width = 60
    ch.category_axis.tick_labels.font.size = Pt(11)
    ch.category_axis.reverse_order = True
    ch.value_axis.visible = False
    ch.value_axis.has_major_gridlines = False
    source(s, asof)

    # 4 trigger watch
    tw = triggers(xa)
    s = deck.titled(f"Trigger watch: {len(tw)} markets within 2% of a decisive level",
                    "Where the next verdict changes are most likely – level, distance and current verdict")
    rows, styles = [], {}
    for i, r in enumerate(tw.head(18).itertuples()):
        rows.append([r.name, num(r.close, r.decimals), r.kind, num(r.level, r.decimals),
                     dist(r, r.level, 2),
                     f"{VGLYPH.get(r.verdict, '')} {VLABEL.get(r.verdict, r.verdict)}"])
        styles[(i, 5)] = verdict_style(r.verdict)
        styles[(i, 4)] = {"color": MINT if r.dist >= 0 else MULB, "bold": True}
    table(s, X0, 2.55, W, ["Instrument", "Last", "Level", "Value", "Distance", "Verdict"], rows,
          [3.6, 1.3, 1.7, 1.3, 1.0, 1.38], row_h=min(0.27, 5.0 / (len(rows) + 1)), size=9, styles=styles)
    source(s, asof, "Distance = last close against the level; negative = below it.")

    # 5 changes
    s = deck.titled(f"{len(c['changes'])} verdict changes this week – eight of them downgrades",
                    f"Changes against the previous edition ({c.get('previous_edition', 'previous week')})")
    rows, styles = [], {}
    names = table_df.set_index("ticker")["name"]
    for i, (t, a, b, why) in enumerate(c["changes"]):
        rows.append([names.get(t, t), f"{VGLYPH[a]} {a}", "→", f"{VGLYPH[b]} {b}", why])
        styles[(i, 1)] = verdict_style(a)
        styles[(i, 3)] = verdict_style(b)
        styles[(i, 2)] = {"align": PP_ALIGN.CENTER, "color": GREY}
    table(s, X0, 2.55, W, ["Instrument", "From", "", "To", "Why"], rows, [2.4, 1.1, 0.35, 1.1, 5.33], row_h=0.38, size=9.5, styles=styles)
    source(s, asof)
    for pair in (("KOSPI Index", "AUDUSD Curncy"), ("NKY Index", "TWSE Index")):
        s = deck.titled("Changes this week: " + " and ".join(names.get(t, t) for t in pair), "")
        why = {t_: (a_, b_, w_) for t_, a_, b_, w_ in c["changes"]}
        for k, t in enumerate(pair):
            if t in charts:
                chart_image(s, charts[t], X0 + k * 5.2, 2.75, 5.05)
            if t in why:
                a_, b_, w_ = why[t]
                text(s, X0 + k * 5.2, 5.75, 5.05, 1.2,
                     [[(f"{VGLYPH[a_]} {a_}  →  {VGLYPH[b_]} {b_}", {"bold": True, "color": VCOL[b_], "size": 12})], w_],
                     size=11)
        source(s, asof)

    # asset-class sections
    sec = c["sections"]
    eq = xa[xa.asset_class.isin(["index", "sector"])]
    dm = eq[eq.group.isin(["Equities – US", "Equities – Europe", "Equities – Switzerland", "Equities – Global"])]
    asia = eq[~eq.index.isin(dm.index)]
    blocks = [
        ("equities_dm", dm, "Equities – US, Europe and Switzerland"),
        ("equities_asia", asia, "Equities – Asia and emerging markets"),
        ("rates", xa[xa.asset_class == "rate"], "Government bond yields"),
        ("fx", xa[xa.asset_class == "fx"], "Currencies"),
        ("commodities", xa[xa.asset_class == "commodity"], "Commodities"),
        ("crypto", xa[xa.asset_class == "crypto"], "Crypto assets"),
    ]
    for key, d, sub in blocks:
        cfg = sec[key]
        dashboard_slide(deck, d, cfg["title"], sub, asof)
        if cfg.get("hero") and cfg["hero"] in charts:
            s = hero_slide(deck, charts[cfg["hero"]], cfg["hero_title"], asof)

    # Focus List
    st = fl[fl.group == "Focus List – Stocks"]
    s = deck.titled(sec["focus"]["title"], "Equity Focus List – 48 single stocks: rules-based trend verdict against relative strength versus the regional index")
    cols = ["outperforming", "mixed", "underperforming"]
    vrows = ["Bullish", "Neutral+", "Neutral", "Neutral-", "Bearish"]
    rows, styles = [], {}
    for i, v in enumerate(vrows):
        row = [f"{VGLYPH[v]} {VLABEL[v]}"]
        styles[(i, 0)] = verdict_style(v)
        for j, ct in enumerate(cols, start=1):
            names_ = st[(st.verdict.replace("Bearish_LM", "Bearish") == v) & (st.rs_trend == ct)].name.tolist()
            row.append(", ".join(n.replace(" Inc", "").replace(" SA", "").replace(" AG", "").replace(" PLC", "").replace(" Corp", "")
                                 .replace(" NV", "").replace(" Ltd", "").replace(" AB", "") for n in names_) or EN_DASH)
            styles[(i, j)] = {"fill": {"outperforming": "E3F4EF", "mixed": "F6F7F9", "underperforming": "F6E8EF"}[ct],
                              "align": PP_ALIGN.LEFT}
        rows.append(row)
    table(s, X0, 2.55, W, ["Trend", "Outperforming its region", "Mixed", "Underperforming its region"], rows,
          [1.45, 3.4, 2.0, 3.43], row_h=0.8, size=8.5, styles=styles)
    source(s, asof, "Relative strength against S&P 500 (US), Stoxx 600 (Europe), MSCI World (TSMC), Ibovespa (Embraer); prices in local currency.")
    for part, d in enumerate((st.iloc[:24], st.iloc[24:]), start=1):
        s = deck.titled(f"Focus List stocks ({part}/2): trend, levels and relative strength", "Rules-based verdicts – the Focus List carries no published verdict")
        rows, styles = [], {}
        for i, r in enumerate(d.itertuples()):
            rows.append([r.name, num(r.close, r.decimals), r.slope200 or EN_DASH, pct(r.vs200), pct(r.dist_s), pct(r.dist_r),
                         pct(r.rs_chg63) if pd.notna(r.rs_chg63) else EN_DASH, (r.rs_trend if isinstance(r.rs_trend, str) else "pending"),
                         f"{VGLYPH.get(r.verdict, '')} {VLABEL.get(r.verdict, r.verdict)}"])
            styles[(i, 8)] = verdict_style(r.verdict)
            styles[(i, 7)] = {"color": {"outperforming": MINT, "underperforming": MULB}.get(r.rs_trend, BLUEB), "bold": True, "align": PP_ALIGN.LEFT}
            styles[(i, 2)] = {"color": {"rising": MINT, "falling": MULB}.get(r.slope200, BLUEB), "align": PP_ALIGN.LEFT}
        table(s, X0, 2.55, W, ["Stock", "Last", "200-day", "vs 200d", "to support", "to resist.", "RS 3m", "Relative strength", "Trend"],
              rows, [2.9, 0.9, 0.7, 0.75, 0.8, 0.8, 0.75, 1.3, 1.38], row_h=0.2, size=7.5, styles=styles)
        source(s, asof)
    fu = fl[fl.group != "Focus List – Stocks"]
    s = deck.titled("Focus List funds, ETFs and indices: trend verdicts", "Rules-based verdicts")
    rows, styles = [], {}
    for i, r in enumerate(fu.itertuples()):
        rows.append([r.name[:62], num(r.close, r.decimals), r.slope200 or EN_DASH, pct(r.vs200), pct(r.dist_s), pct(r.dist_r), pct(r.chg3m),
                     f"{VGLYPH.get(r.verdict, '')} {VLABEL.get(r.verdict, r.verdict)}"])
        styles[(i, 7)] = verdict_style(r.verdict)
        styles[(i, 2)] = {"color": {"rising": MINT, "falling": MULB}.get(r.slope200, BLUEB), "align": PP_ALIGN.LEFT}
    table(s, X0, 2.55, W, ["Fund / ETF / index", "Last", "200-day", "vs 200d", "to support", "to resist.", "3 months", "Trend"],
          rows, [4.3, 0.9, 0.7, 0.75, 0.85, 0.85, 0.8, 1.13], row_h=0.19, size=7.5, styles=styles)
    source(s, asof)

    # method
    s = deck.titled("How to read the verdicts", "One rule set, applied to every market every week")
    items = [
        ("Trend", "The direction of the 200-day moving average over the last 20 trading days: rising, flat or falling."),
        ("Structure", "Whether the key support or resistance drawn on the chart has broken. A broken support stands until the resistance breaks."),
        ("Verdict", "Rising trend + intact support = Bullish. Falling trend + broken support = Bearish. Everything in between is Neutral, with a tilt."),
        ("Levels", "Drawn supports and resistances; where none is drawn, the 52-week low and high."),
        ("Relative strength", "For single stocks, price against the regional index: outperforming, mixed or underperforming. It informs, it does not change the verdict."),
    ]
    for k, (lab, body) in enumerate(items):
        y = 2.6 + k * 0.95
        box(s, X0, y, 2.0, 0.78, NAVY if k % 2 else ORANGE)
        text(s, X0 + 0.12, y, 1.8, 0.78, lab, size=12, color="FFFFFF", bold=True, anchor=MSO_ANCHOR.MIDDLE)
        text(s, X0 + 2.2, y, 8.0, 0.78, body, size=11.5, anchor=MSO_ANCHOR.MIDDLE)
    source(s, asof)

    # appendix
    s = deck.slide(L_GRADIENT)
    for ph in s.placeholders:
        if ph.placeholder_format.idx == 0:
            ph.text = "Appendix – all charts"
    for t, path in charts.items():
        s = deck.slide(L_BLANK)
        chart_image(s, path, 0.45, 0.6, 10.8)

    deck.slide(L_DISCLAIMER)
    deck.slide(L_FINAL)
    deck.save(out)
    return out
