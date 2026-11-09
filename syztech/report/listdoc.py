"""Technical document for a list of single stocks: dashboard + every chart (e.g. the Swiss list).

Cover, summary with a relative-strength ranking, one-page dashboard, trend × relative-strength
grid, trigger watch, method, one chart per stock with a factual title, legal disclaimer.
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_TICK_LABEL_POSITION
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from ..fmt import EN_DASH, num
from .weekly import (AMBER, BLUEB, GREY, L_BLANK, L_COVER, L_DISCLAIMER, L_FINAL, MINT, MULB, NAVY, ORANGE, SKY, VGLYPH,
                     VLABEL, W, X0, Deck, box, chart_image, pct, rgb, source, table, text, triggers, verdict_style)

RS_ORDER = {"outperforming": 0, "mixed": 1, "underperforming": 2}
V_ORDER = {"Bullish": 0, "Neutral+": 1, "Neutral": 2, "Neutral-": 3, "Bearish_LM": 4, "Bearish": 5}


def _bucket(v):
    return "Bullish" if v == "Bullish" else "Bearish" if str(v).startswith("Bearish") else "Neutral"


def build_list_doc(df: pd.DataFrame, charts: dict, out: Path, template: Path, *, title: str, edition: str, asof: str,
                   benchmark_name: str, excluded: list[str], draft: bool = True) -> Path:
    deck = Deck(template)
    df = df.copy()
    df["vo"] = df.verdict.map(V_ORDER).fillna(9)
    df["ro"] = df.rs_trend.map(RS_ORDER).fillna(9)
    df = df.sort_values(["vo", "ro", "name"]).reset_index(drop=True)
    n = len(df)
    counts = df.verdict.map(_bucket).value_counts()
    out_n, under_n = int((df.rs_trend == "outperforming").sum()), int((df.rs_trend == "underperforming").sum())
    bull_lag = df[(df.verdict == "Bullish") & (df.rs_trend == "underperforming")]

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
    text(s, 6.45, 2.2, 4.6, 0.4, f"{n} STOCKS – TREND VERDICTS", size=11, color=AMBER, bold=True)
    for k, (lab, col) in enumerate((("Bullish", MINT), ("Neutral", SKY), ("Bearish", "E6A4AD"))):
        text(s, 6.45, 2.85 + k * 1.15, 1.6, 0.9, str(int(counts.get(lab, 0))), size=48, color=col, bold=True)
        text(s, 8.15, 3.15 + k * 1.15, 2.6, 0.5, lab, size=16, color="FFFFFF")
    text(s, 0.73, 7.45, 4.8, 0.3, "Florian Marini, CFA, CMT – Head of Research", size=10, color=BLUEB)
    if draft:
        text(s, 0.73, 4.75, 4.8, 0.3, "DRAFT – FOR INTERNAL REVIEW", size=10, color=ORANGE, bold=True)

    # summary: relative-strength ranking (native bar chart) + key numbers
    s = deck.titled(f"{int(counts.get('Bullish', 0))} of {n} stocks in an uptrend – {out_n} outperform the {benchmark_name}, {under_n} lag it",
                    f"Relative strength against the {benchmark_name} over 3 months, %")
    rk = df.dropna(subset=["rs_chg63"]).sort_values("rs_chg63")
    cd = CategoryChartData()
    cd.categories = list(rk.name)
    cd.add_series("RS 3m", [round(v * 100, 1) for v in rk.rs_chg63])
    gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(X0), Inches(2.5), Inches(6.6), Inches(5.0), cd)
    ch = gf.chart
    ch.has_legend = False
    ch.has_title = False
    ch.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW     # names left of the chart, clear of negative bars
    plot = ch.plots[0]
    plot.gap_width = 40
    plot.has_data_labels = True
    plot.data_labels.font.size = Pt(7)
    plot.data_labels.number_format = '+0.0;–0.0'
    plot.data_labels.number_format_is_linked = False
    ser = ch.series[0]
    for i, v in enumerate(rk.rs_chg63):
        pt = ser.points[i]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = rgb(MINT if v >= 0 else MULB)
    ch.category_axis.tick_labels.font.size = Pt(7.5)
    ch.value_axis.visible = False
    ch.value_axis.has_major_gridlines = False
    stats = [(str(int(counts.get("Bullish", 0))), "Bullish trend", MINT), (str(out_n), f"outperform the {benchmark_name}", MINT),
             (str(len(bull_lag)), "Bullish but lagging", ORANGE), (str(int(counts.get("Bearish", 0)) + int(counts.get("Neutral", 0))), "not Bullish", MULB)]
    for k, (big, lab, col) in enumerate(stats):
        y = 2.55 + k * 1.22
        box(s, 7.65, y, 3.36, 1.05, "F6F7F9")
        text(s, 7.85, y + 0.08, 1.2, 0.9, big, size=30, color=col, bold=True, anchor=MSO_ANCHOR.MIDDLE)
        text(s, 9.0, y + 0.08, 1.95, 0.9, lab, size=11, anchor=MSO_ANCHOR.MIDDLE)
    source(s, asof, f"Relative strength = price ÷ {benchmark_name}, both in CHF.")

    # dashboard
    s = deck.titled("Dashboard: trend, levels and relative strength for every stock",
                    "Sorted by verdict, then relative strength. Levels: 52-week low / high (no drawn levels yet)")
    rows, st = [], {}
    for i, r in enumerate(df.itertuples()):
        rows.append([r.name, num(r.close, r.decimals), r.slope200 or EN_DASH, pct(r.vs200), pct(r.dist_s), pct(r.dist_r),
                     pct(r.chg1w), pct(r.chg3m), pct(r.rs_chg63) if pd.notna(r.rs_chg63) else EN_DASH,
                     r.rs_trend if isinstance(r.rs_trend, str) else EN_DASH, f"{VGLYPH.get(r.verdict, '')} {VLABEL.get(r.verdict, r.verdict)}"])
        st[(i, 10)] = verdict_style(r.verdict)
        st[(i, 2)] = {"color": {"rising": MINT, "falling": MULB}.get(r.slope200, BLUEB), "align": PP_ALIGN.LEFT}
        st[(i, 9)] = {"color": {"outperforming": MINT, "underperforming": MULB}.get(r.rs_trend, BLUEB), "bold": True, "align": PP_ALIGN.LEFT}
    table(s, X0, 2.5, W, ["Stock", "Last", "200-day", "vs 200d", "to 52w low", "to 52w high", "1 week", "3 months", "RS 3m",
                          "Relative strength", "Trend"], rows,
          [2.15, 0.8, 0.65, 0.72, 0.8, 0.82, 0.68, 0.75, 0.68, 1.15, 1.08], row_h=min(0.2, 5.0 / (n + 1)), size=7.5, styles=st)
    source(s, asof, f"Relative strength against the {benchmark_name}." + (f" Not shown (no prices in the export): {', '.join(excluded)}." if excluded else ""))

    # trend × RS grid
    s = deck.titled(f"{len(bull_lag)} stocks are in an uptrend but lag the {benchmark_name}",
                    f"Trend verdict against relative strength versus the {benchmark_name}")
    cols = ["outperforming", "mixed", "underperforming"]
    rows, st = [], {}
    for i, v in enumerate(["Bullish", "Neutral+", "Neutral", "Neutral-", "Bearish"]):
        row = [f"{VGLYPH[v]} {VLABEL[v]}"]
        st[(i, 0)] = verdict_style(v)
        for j, ct in enumerate(cols, start=1):
            nm = df[(df.verdict.replace("Bearish_LM", "Bearish") == v) & (df.rs_trend == ct)].name.tolist()
            row.append(", ".join(nm) or EN_DASH)
            st[(i, j)] = {"fill": {"outperforming": "E3F4EF", "mixed": "F6F7F9", "underperforming": "F6E8EF"}[ct], "align": PP_ALIGN.LEFT}
        rows.append(row)
    table(s, X0, 2.5, W, ["Trend", f"Outperforming the {benchmark_name}", "Mixed", f"Underperforming the {benchmark_name}"], rows,
          [1.45, 3.4, 2.0, 3.43], row_h=0.85, size=9, styles=st)
    source(s, asof, "Outperforming: relative strength above its 200-day and up over 3 months; underperforming: below and down.")

    # trigger watch: 52-week levels and the 100-day band
    cand = df.copy()
    tw = triggers(cand)
    extra = []
    for r in df.itertuples():
        for lvl, lab in ((r.hi100, "100-day high"), (r.lo100, "100-day low")):
            if pd.notna(lvl) and abs(r.close / lvl - 1) <= 0.02:
                extra.append(dict(ticker=r.ticker, name=r.name, verdict=r.verdict, close=r.close, decimals=r.decimals,
                                  level=lvl, kind=lab, dist=r.close / lvl - 1, asset_class=r.asset_class))
    tw = pd.concat([tw, pd.DataFrame(extra)], ignore_index=True) if extra else tw
    if len(tw):
        tw = tw.sort_values("dist", key=lambda x: x.abs()).drop_duplicates("ticker")
    s = deck.titled(f"Trigger watch: {len(tw)} stocks within 2% of a 52-week or 100-day high or low",
                    "Where a breakout or a breakdown is closest")
    rows, st = [], {}
    for i, r in enumerate(tw.itertuples()):
        rows.append([r.name, num(r.close, r.decimals), r.kind, num(r.level, r.decimals), pct(r.dist, 2),
                     f"{VGLYPH.get(r.verdict, '')} {VLABEL.get(r.verdict, r.verdict)}"])
        st[(i, 5)] = verdict_style(r.verdict)
        st[(i, 4)] = {"color": MINT if r.dist >= 0 else MULB, "bold": True}
    if rows:
        table(s, X0, 2.5, W, ["Stock", "Last", "Level", "Value", "Distance", "Trend"], rows,
              [3.6, 1.3, 1.7, 1.3, 1.0, 1.38], row_h=min(0.3, 5.0 / (len(rows) + 1)), size=9.5, styles=st)
    source(s, asof, "100-day high / low: highest / lowest close of the prior 100 trading days.")

    # method
    s = deck.titled("How to read the verdicts", "One rule set, applied to every stock")
    items = [("Trend", "Direction of the 200-day moving average over the last 20 trading days: rising, flat or falling."),
             ("Structure", "A support break (here: a close below the 52-week low or the 100-day low) stands until a resistance break."),
             ("Verdict", "Rising trend + intact support = Bullish. Falling trend + broken support = Bearish. In between: Neutral, with a tilt."),
             ("Relative strength", f"Price against the {benchmark_name}: outperforming, mixed or underperforming. It informs, it does not change the verdict.")]
    for k, (lab, body) in enumerate(items):
        y = 2.65 + k * 1.1
        box(s, X0, y, 2.0, 0.85, NAVY if k % 2 else ORANGE)
        text(s, X0 + 0.12, y, 1.8, 0.85, lab, size=12, color="FFFFFF", bold=True, anchor=MSO_ANCHOR.MIDDLE)
        text(s, X0 + 2.2, y, 8.0, 0.85, body, size=11.5, anchor=MSO_ANCHOR.MIDDLE)
    source(s, asof)

    # one chart per stock, factual title
    for r in df.itertuples():
        if r.ticker not in charts:
            continue
        rs = {"outperforming": f"outperforming the {benchmark_name}", "underperforming": f"lagging the {benchmark_name}",
              "mixed": f"mixed against the {benchmark_name}"}.get(r.rs_trend, "")
        t = f"{r.name}: {VLABEL.get(r.verdict, r.verdict)} – {pct(r.vs200)} against a {r.slope200} 200-day" + (f", {rs}" if rs else "")
        s = deck.titled(t, "")
        chart_image(s, charts[r.ticker], X0 + 0.35, 2.15, W - 0.7)
    deck.slide(L_DISCLAIMER)
    deck.slide(L_FINAL)
    deck.save(out)
    return out
