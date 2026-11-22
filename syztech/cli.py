"""syztech command line (BUILD_SPEC §6)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from .fmt import EN_DASH
from .io.bloomberg_prices import load_prices
from .io.universe import COLUMNS, draft, guess_asset_class, load_universe, with_benchmarks
from .trend.rules import INSUFFICIENT
from .trend.score import score_universe

OUT = Path("output")


def _d(x):
    return x.strftime("%Y-%m-%d") if x is not None and pd.notna(x) else EN_DASH


def cmd_inspect(a) -> int:
    res = load_prices(a.prices)
    print(f"Price export: {a.prices}")
    for n in res.file_notes:
        print(f"  note: {n}")
    if not res.reports:
        print("No price series found.")
        return 1
    print(f"\n{'ticker':24} {'first':10} {'last':10} {'bars':>6}  issues")
    for t, r in res.reports.items():
        print(f"{t:24} {_d(r.first):10} {_d(r.last):10} {r.bars:>6}  {'; '.join(r.issues) or 'none'}")
    OUT.mkdir(exist_ok=True)
    pd.DataFrame([{k: v for k, v in vars(r).items() if k != "issues"} | {"issues": "; ".join(r.issues)}
                  for r in res.reports.values()]).to_csv(OUT / "inspect.csv", index=False)
    print(f"\nwritten: {OUT / 'inspect.csv'}")
    return 0


def cmd_universe_draft(a) -> int:
    res = load_prices(a.prices)
    out = Path(a.out)
    if out.exists() and not a.force:
        print(f"{out} exists – not overwritten (use --force).")
        return 1
    df = draft(res.tickers, {t: r.name for t, r in res.reports.items()})
    df.to_csv(out, index=False)
    print(f"written: {out} ({len(df)} tickers)")
    for t in res.tickers:
        note = guess_asset_class(t)[1]
        if note:
            print(f"  {t}: {note}")
    return 0


def cmd_price_template(a) -> int:
    from datetime import date
    from .io.template import build_template
    uni, problems = load_universe(a.universe)
    for p in problems:
        print(f"universe: {p}")
    sheets = with_benchmarks(uni)
    out = build_template(sheets, a.out, date.fromisoformat(a.start), date.fromisoformat(a.end), reference=a.reference)
    extra = len(sheets) - len(uni)
    print(f"written: {out} ({len(sheets)} ticker sheets incl. {extra} benchmark-only, {a.start} to {a.end})")
    return 0


def _lists_of(u) -> list[str]:
    """Syz list membership from the universe column syz_lists ('Master list; Focus List'), Focus List first."""
    v = getattr(u, "syz_lists", None)
    got = [x.strip() for x in v.split(";")] if isinstance(v, str) else []
    return sorted([x for x in got if x], key=lambda x: (x != "Focus List", x))


def cmd_deck_charts(a) -> int:
    from .charts.deck_chart import deck_chart, load_trendlines
    prices = load_prices(a.prices)
    uni, problems = load_universe(a.universe)
    for p in problems:
        print(f"universe: {p}")
    asof = a.asof or (prices.prices.date.max().date() if len(prices.prices) else None)
    scores = score_universe(prices, uni, asof).set_index("ticker")
    tls = load_trendlines(a.trendlines)
    out_dir = Path(a.out) / str(asof)
    done, skipped = 0, []
    breadth = None
    if a.breadth_for:                              # breadth of the other stocks in the universe, for the sector chart
        from .indicators.breadth import breadth_history
        bench_set = set(uni.benchmark.dropna())
        members = [t for t, ac in zip(uni.ticker, uni.asset_class) if t != a.breadth_for and t not in bench_set
                   and ac == "equity" and t in prices.reports and prices.reports[t].bars > 0]     # stocks only, not other indices
        sec = prices.series(a.breadth_for)
        sec = sec[sec.index <= pd.Timestamp(asof)]
        breadth = breadth_history({t: prices.series(t)[lambda z: z.index <= pd.Timestamp(asof)] for t in members}, sec.index)
        last = breadth.dropna().iloc[-1]
        print(f"breadth for {a.breadth_for}: {len(members)} stocks; today {last.rising:.0f}% with a rising 200-day, "
              f"{last.above:.0f}% above it ({int(last.n)} measurable)")
    for i, u in enumerate(uni.itertuples(index=False), start=1):
        t = u.ticker
        if t not in prices.reports or prices.reports[t].bars == 0:
            skipped.append(f"{t}: no prices"); continue
        s = prices.series(t)
        s = s[s.index <= pd.Timestamp(asof)]
        row = {"ticker": t, "name": u.name, "decimals": u.decimals, "support": u.support, "resistance": u.resistance,
               "support_origin": getattr(u, "support_origin", None), "resistance_origin": getattr(u, "resistance_origin", None)}
        badge, kind = (u.badge, "published") if isinstance(u.badge, str) and u.badge else (None, "mechanical")
        if badge is None:
            v = scores.loc[t, "verdict"]
            badge = v if v in ("Bullish", "Neutral+", "Neutral", "Neutral-", "Bearish_LM", "Bearish") else None
        bench = getattr(u, "benchmark", None)
        b = prices.series(bench) if isinstance(bench, str) and bench in prices.reports else None
        if b is not None:
            names = uni.set_index("ticker")["name"]
            if bench not in names.index and Path("data/universe.csv").exists():
                names = pd.read_csv("data/universe.csv").set_index("ticker")["name"]
            bname = {"SPI Swiss Performance Index": "SPI", "Stoxx Europe 600": "Stoxx 600"}.get(names.get(bench, bench), names.get(bench, bench))
        else:
            bname = None
        group = (u.group or "Other").replace(" – ", "_").replace(" & ", "_").replace(" ", "_")
        f = out_dir / group / f"{i:03d}_{t.replace(' ', '_').replace('/', '-')}.png"
        try:
            deck_chart(s, row, f, badge=badge, badge_kind=kind, trendlines=tls.get(t), benchmark=b, benchmark_name=bname,
                       page=a.page, breadth=breadth if t == a.breadth_for else None,
                       breadth_label=a.breadth_label, lists=_lists_of(u))
            done += 1
        except Exception as e:                      # one bad series must not stop the run
            skipped.append(f"{t}: {e}")
    print(f"deck charts: {done} written to {out_dir}")
    for s in skipped:
        print(f"  skipped – {s}")
    return 0


def cmd_weekly_doc(a) -> int:
    import json
    from PIL import Image
    from .charts.deck_chart import load_trendlines
    from .report.weekly import build, instrument_table
    prices = load_prices(a.prices)
    uni, _ = load_universe(a.universe)
    asof = a.asof or (prices.prices.date.max().date() if len(prices.prices) else None)
    scores = score_universe(prices, uni, asof)
    tls = load_trendlines(a.trendlines)
    df = instrument_table(scores, uni, prices, tls)
    chart_dir = Path(a.charts) / str(asof)
    if not chart_dir.exists():
        print(f"no charts in {chart_dir} – run syztech deck-charts first")
        return 1
    small = OUT / "doc_charts" / str(asof)
    small.mkdir(parents=True, exist_ok=True)
    charts = {}
    files = {f.stem.split("_", 1)[1]: f for f in chart_dir.glob("*/*.png")}
    for t in uni.ticker:
        f = files.get(t.replace(" ", "_").replace("/", "-"))
        if f is None:
            continue
        jp = small / (f.stem + ".jpg")
        if not jp.exists():
            with Image.open(f) as im:
                im.convert("RGB").resize((1800, int(1800 * im.height / im.width)), Image.LANCZOS).save(jp, quality=88)
        charts[t] = jp
    commentary = json.loads(Path(a.commentary).read_text(encoding="utf-8"))
    d = pd.Timestamp(asof)
    out = Path(a.out or OUT / f"Syz_Technicals_{commentary['edition'].replace(' ', '_')}.pptx")
    build(df, commentary, charts, out, Path(a.template), f"{d.day} {d:%B %Y}")
    print(f"written: {out} ({len(charts)} charts in the appendix)")
    return 0


def _jpg_charts(uni, chart_dir: Path, small: Path) -> dict:
    from PIL import Image
    small.mkdir(parents=True, exist_ok=True)
    files = {f.stem.split("_", 1)[1]: f for f in chart_dir.glob("*/*.png")}
    out = {}
    for t in uni.ticker:
        f = files.get(t.replace(" ", "_").replace("/", "-"))
        if f is None:
            continue
        jp = small / (f.stem + ".jpg")
        with Image.open(f) as im:
            im.convert("RGB").resize((1800, int(1800 * im.height / im.width)), Image.LANCZOS).save(jp, quality=88)
        out[t] = jp
    return out


def cmd_list_doc(a) -> int:
    from .charts.deck_chart import load_trendlines
    from .report.listdoc import build_list_doc
    from .report.weekly import instrument_table
    prices = load_prices(a.prices)
    uni, _ = load_universe(a.universe)
    asof = a.asof or (prices.prices.date.max().date() if len(prices.prices) else None)
    scores = score_universe(prices, uni, asof)
    df = instrument_table(scores, uni, prices, load_trendlines(a.trendlines))
    excluded = [n for t, n in zip(uni.ticker, uni.name) if t not in set(df.ticker)]
    if a.screen:
        scr = pd.read_csv(a.screen)
        df = df.merge(scr, on="ticker", how="left")
    focus = None
    if a.focus_universe:
        fu, _ = load_universe(a.focus_universe)
        focus = instrument_table(score_universe(prices, fu, asof), fu, prices, load_trendlines(a.trendlines))
        if a.focus_screen:
            focus = focus.merge(pd.read_csv(a.focus_screen), on="ticker", how="left")
    charts = _jpg_charts(uni, Path(a.charts) / str(asof), OUT / "doc_charts" / f"{Path(a.universe).stem}_{asof}")
    d = pd.Timestamp(asof)
    out = Path(a.out)
    build_list_doc(df, charts, out, Path(a.template), title=a.title, edition=a.edition, asof=f"{d.day} {d:%B %Y}",
                   benchmark_name=a.benchmark_name, excluded=excluded, draft=not a.final, screen_date=a.screen_date,
                   focus=focus)
    print(f"written: {out} ({len(df)} stocks, {len(charts)} charts; excluded: {', '.join(excluded) or 'none'})")
    return 0


def _layout(a, indices) -> dict:
    """Optional layout settings of sector-doc; omitted ones keep the S&P 500 IT defaults."""
    out = {}
    if a.buckets:
        out["buckets"] = [b.strip() for b in a.buckets.split(";") if b.strip()]
    if a.group_col:
        out["group_col"] = a.group_col
        out["group_label"] = a.group_label or a.group_col
        out["group_label_pl"] = a.group_label_pl or out["group_label"]
    if indices is not None:
        out["indices"] = indices
        out["index_heading"] = a.index_heading
    if a.bench_note:
        out["bench_note"] = a.bench_note
    if a.trigger_cap:
        out["trigger_cap"] = a.trigger_cap
    return out


def cmd_sector_doc(a) -> int:
    from .charts.deck_chart import load_trendlines
    from .report.sectordoc import add_momentum, build_sector_doc
    from .report.weekly import instrument_table
    prices = load_prices(a.prices)
    uni, _ = load_universe(a.universe)
    asof = a.asof or (prices.prices.date.max().date() if len(prices.prices) else None)
    scores = score_universe(prices, uni, asof)
    df = instrument_table(scores, uni, prices, load_trendlines(a.trendlines))
    df = df.merge(scores[["ticker", "rule"]], on="ticker", how="left")
    df = df.merge(uni[["ticker", "industry", "bucket"] + [c for c in ("syz_lists", "sector") if c in uni.columns]],
                  on="ticker", how="left")
    df = add_momentum(df, prices)
    sec = df[df.ticker == a.sector]
    if sec.empty:
        print(f"sector index {a.sector} has no prices")
        return 1
    idx_t = [t.strip() for t in (a.indices or "").split(",") if t.strip()]
    indices = df[df.ticker.isin(idx_t)].set_index("ticker").loc[[t for t in idx_t if t in set(df.ticker)]].reset_index() if idx_t else None
    stocks = df[(df.ticker != a.sector) & ~df.ticker.isin(idx_t)]
    insufficient = stocks[~stocks.verdict.isin(["Bullish", "Neutral+", "Neutral", "Neutral-", "Bearish_LM", "Bearish"])].name.tolist()
    for t, nm in zip(uni.ticker, uni.name):        # dropped for lack of a scored close: named, never filled
        if t not in set(df.ticker) and t in prices.reports:
            insufficient.append(f"{nm} ({prices.reports[t].bars} bars)")
    charts = _jpg_charts(uni, Path(a.charts) / str(asof), OUT / "doc_charts" / f"{Path(a.universe).stem}_{asof}")
    d = pd.Timestamp(asof)
    out = Path(a.out)
    work = OUT / "doc_charts" / f"{Path(a.universe).stem}_{asof}"
    build_sector_doc(stocks, sec.iloc[0], charts, out, Path(a.template), title=a.title, edition=a.edition,
                     asof=f"{d.day} {d:%B %Y}", bench=a.benchmark_name, sector_name=a.sector_name,
                     insufficient=insufficient, work=work, draft=not a.final, lists_asof=a.lists_asof or "", **_layout(a, indices))
    print(f"written: {out} ({len(stocks)} stocks, {len(charts)} charts; no verdict: {', '.join(insufficient) or 'none'})")
    if a.html_out:
        from .report.sector_html import build_sector_html
        h = build_sector_html(stocks, sec.iloc[0], charts, Path(a.html_out), title=a.title, edition=a.edition,
                              asof=f"{d.day} {d:%B %Y}", bench=a.benchmark_name, sector_name=a.sector_name,
                              insufficient=insufficient, draft=not a.final, lists_asof=a.lists_asof or "",
                              **{k: v for k, v in _layout(a, indices).items() if k in ("buckets", "group_col", "group_label", "indices",
                                                                                      "bench_note", "index_heading")})
        print(f"written: {h} (HTML, charts alongside)")
    return 0


def cmd_sector_style(a) -> int:
    """Sectors & style across four regions: universe (+ratios) -> charts -> rotation maps -> PowerPoint."""
    from PIL import Image
    from .charts.deck_chart import deck_chart
    from .report.sectordoc import add_momentum
    from .report.sectorstyle import BENCH_NAMES, REGIONS, build_sector_style, build_universe, rotation_map, rotation_points
    from .report.weekly import instrument_table
    prices = load_prices(a.prices)
    asof = pd.Timestamp(a.asof).date() if a.asof else prices.prices.date.max().date()
    base = pd.read_csv(a.universe)
    u, dropped = build_universe(base, prices, asof)
    work = OUT / "sector_style" / str(asof)
    work.mkdir(parents=True, exist_ok=True)
    u.to_csv(work / "universe_built.csv", index=False)
    uni, problems = load_universe(work / "universe_built.csv")
    for p in problems:
        print(f"universe: {p}")
    for d in dropped:
        print(f"left out: {d}")
    scores = score_universe(prices, uni, asof)
    verdict = scores.set_index("ticker").verdict
    charts, skipped = {}, []
    for i, r in enumerate(uni.itertuples(index=False), start=1):
        t = r.ticker
        s = prices.series(t)
        s = s[s.index <= pd.Timestamp(asof)]
        row = {"ticker": t, "name": r.name, "decimals": r.decimals, "support": r.support, "resistance": r.resistance,
               "support_origin": r.support_origin, "resistance_origin": r.resistance_origin}
        v = verdict.get(t)
        bench = r.benchmark if isinstance(r.benchmark, str) and r.benchmark in prices.reports else None
        slug = t.replace(" ÷ ", "_over_").replace(" ", "_").replace("/", "-")
        png = work / "charts" / f"{i:03d}_{slug}.png"
        try:
            deck_chart(s, row, png, badge=v if v in ("Bullish", "Neutral+", "Neutral", "Neutral-", "Bearish_LM", "Bearish") else None,
                       badge_kind="mechanical", benchmark=prices.series(bench) if bench else None,
                       benchmark_name=BENCH_NAMES.get(bench, bench) if bench else None, page="a4")
        except Exception as e:                      # one bad series must not stop the run
            skipped.append(f"{t}: {e}")
            continue
        jp = work / "jpg" / (png.stem + ".jpg")
        jp.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(png) as im:
            im.convert("RGB").resize((1800, int(1800 * im.height / im.width)), Image.LANCZOS).save(jp, quality=88)
        charts[t] = jp
    print(f"charts: {len(charts)}" + (f"; skipped: {skipped}" if skipped else ""))
    df = instrument_table(scores, uni, prices, {})
    df = df.merge(scores[["ticker", "rule"]], on="ticker", how="left").merge(uni[["ticker", "region", "sector_key"]], on="ticker", how="left")
    df = add_momentum(df, prices)
    vmap = dict(zip(df.ticker, df.verdict))
    short = lambda n: (n.replace("S&P 500 ", "").replace("Stoxx 600 ", "").replace("MSCI Europe ", "").replace("MSCI Japan ", "")
                       .replace("MSCI EM ", "").replace("MSCI ", ""))
    from .report.sectorstyle import MAP_LABELS
    labels = {t: MAP_LABELS.get(short(n), short(n)) for t, n in zip(df.ticker, df.name)}
    maps = {}
    sets = [("regions", ["MXUS Index", "MXEU Index", "MXJP Index", "MXEF Index"], "MXWD Index")]
    for reg, bench, bname, sg, ig, styg in REGIONS:
        sets.append((f"{reg}_sectors", list(df[df.group == sg].ticker), bench))
        if ig:
            sets.append((f"{reg}_industries", [t for t in df[df.group == ig].ticker if t != "SXXP Index"],
                         "SXXP Index" if reg == "Europe" else bench))
    for key, tickers, bench in sets:
        pts = rotation_points(prices, [t for t in tickers if t in prices.reports], bench)
        if len(pts):
            maps[key] = rotation_map(pts, labels, vmap, work / f"rotation_{key}.png", BENCH_NAMES.get(bench, bench))
    d = pd.Timestamp(asof)
    out = Path(a.out)
    build_sector_style(df, charts, maps, out, Path(a.template), edition=a.edition, asof=f"{d.day} {d:%B %Y}", dropped=dropped,
                       draft=not a.final)
    print(f"written: {out} ({len(df)} series, {len(charts)} charts, {len(maps)} rotation maps)")
    return 0


def cmd_trend(a) -> int:
    prices = load_prices(a.prices)
    uni, problems = load_universe(a.universe)
    for p in problems:
        print(f"universe: {p}")
    asof = a.asof or (prices.prices.date.max().date() if len(prices.prices) else None)
    df = score_universe(prices, uni, asof)
    OUT.mkdir(exist_ok=True)
    path = OUT / f"trend_scores_{asof}.csv"
    df.to_csv(path, index=False)
    counts = df.verdict.value_counts()
    print(f"Trend scores as of {asof}: {len(df)} instruments")
    for v, c in counts.items():
        print(f"  {v:18} {c}")
    print(f"written: {path}")
    from .trend.exceptions import classify_frame, render_markdown
    closes = {t: prices.series(t)[lambda s: s.index <= pd.Timestamp(asof)] for t in df.ticker if t in prices.reports}
    ex = classify_frame(df, closes, asof)
    ex.to_csv(path, index=False)
    md = OUT / f"exceptions_{asof}.md"
    md.write_text(render_markdown(ex, asof), encoding="utf-8")
    print("Exceptions:", ", ".join(f"{k} {v}" for k, v in ex.section.value_counts().items()))
    print(f"written: {md}")
    if a.charts:
        from .charts.trend_chart import trend_chart
        for _, r in ex[ex.section.isin(["conflict", "trigger_hit"])].iterrows():
            f = trend_chart(closes[r.ticker], r, OUT / "charts" / f"{asof}_{r.ticker.replace(' ', '_')}.png")
            print(f"chart: {f}")
    bad = df[df.verdict == INSUFFICIENT]
    for _, r in bad.iterrows():
        print(f"  insufficient_data – {r.ticker}: {r.missing}")
    return 1 if len(bad) and not a.allow_partial else 0


def cmd_later(phase):
    def f(a):
        print(f"Not started: {phase} begins only after Phase 1 is done (BUILD_SPEC §7).")
        return 1
    return f


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="syztech")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("inspect", help="tickers, first/last date, bar count, export defects")
    s.add_argument("--prices", default="data/prices")
    s.set_defaults(func=cmd_inspect)
    s = sub.add_parser("universe-draft", help="draft data/universe.csv from the tickers in the export")
    s.add_argument("--prices", default="data/prices")
    s.add_argument("--out", default="data/universe.csv")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_universe_draft)
    s = sub.add_parser("price-template", help="Excel template with one BDH sheet per universe ticker")
    s.add_argument("--universe", default="data/universe.csv")
    s.add_argument("--out", default="data/schema_examples/bloomberg_prices_template.xlsx")
    s.add_argument("--start", default="2019-01-01")
    s.add_argument("--end", required=True)
    s.add_argument("--reference", action="store_true", help="add a Reference sheet with Bloomberg name and GICS sub-industry")
    s.set_defaults(func=cmd_price_template)
    s = sub.add_parser("deck-charts", help="16:9 publication charts for every instrument in the universe")
    s.add_argument("--prices", default="data/prices")
    s.add_argument("--universe", default="data/universe.csv")
    s.add_argument("--trendlines", default="data/trendlines.csv")
    s.add_argument("--asof")
    s.add_argument("--out", default="output/deck")
    s.add_argument("--page", choices=["16x9", "a4"], default="16x9", help="a4: full-page charts for the A4 documents")
    s.add_argument("--breadth-for", help="ticker of a sector index: add a panel with the % of the other stocks in an uptrend")
    s.add_argument("--breadth-label", default="constituents", help="how the stocks are named in the breadth panel title")
    s.set_defaults(func=cmd_deck_charts)
    s = sub.add_parser("weekly-doc", help="weekly technical document (PowerPoint)")
    s.add_argument("--prices", default="data/prices")
    s.add_argument("--universe", default="data/universe.csv")
    s.add_argument("--trendlines", default="data/trendlines.csv")
    s.add_argument("--charts", default="output/deck")
    s.add_argument("--commentary", required=True)
    s.add_argument("--template", default=str(Path(__file__).parent / "report" / "assets" / "template_syz_a4.pptx"))
    s.add_argument("--asof")
    s.add_argument("--out")
    s.set_defaults(func=cmd_weekly_doc)
    s = sub.add_parser("list-doc", help="dashboard + all charts for a list of stocks (PowerPoint)")
    s.add_argument("--prices", default="data/prices")
    s.add_argument("--universe", required=True)
    s.add_argument("--trendlines", default="data/trendlines.csv")
    s.add_argument("--charts", required=True, help="folder written by deck-charts --out")
    s.add_argument("--title", required=True)
    s.add_argument("--edition", required=True)
    s.add_argument("--benchmark-name", default="SPI")
    s.add_argument("--template", default=str(Path(__file__).parent / "report" / "assets" / "template_syz_a4.pptx"))
    s.add_argument("--asof")
    s.add_argument("--out", required=True)
    s.add_argument("--final", action="store_true", help="drop the draft mark on the cover")
    s.add_argument("--screen", help="CSV by ticker: fundamental_screen, top75_spi, weight_spi, avg_daily_value_chf (display only)")
    s.add_argument("--screen-date", help="as-of date of the screen, shown in the footnote")
    s.add_argument("--focus-universe", help="universe CSV of a focus list, shown on its own slide after the dashboard")
    s.add_argument("--focus-screen", help="screen CSV for the focus list (industry, screen, liquidity)")
    s.set_defaults(func=cmd_list_doc)
    s = sub.add_parser("sector-doc", help="sector special report: sector vs market, momentum dashboards, all charts")
    s.add_argument("--prices", required=True)
    s.add_argument("--universe", required=True, help="universe CSV with industry and bucket columns")
    s.add_argument("--sector", required=True, help="ticker of the sector index, e.g. 'S5INFT Index'")
    s.add_argument("--sector-name", required=True)
    s.add_argument("--trendlines", default="data/trendlines.csv")
    s.add_argument("--charts", required=True)
    s.add_argument("--title", required=True)
    s.add_argument("--edition", required=True)
    s.add_argument("--benchmark-name", default="S&P 500")
    s.add_argument("--template", default=str(Path(__file__).parent / "report" / "assets" / "template_syz_a4.pptx"))
    s.add_argument("--asof")
    s.add_argument("--out", required=True)
    s.add_argument("--final", action="store_true")
    s.add_argument("--html-out", help="folder for the HTML version (index.html + charts/)")
    s.add_argument("--lists-asof", help="date of the Syz Focus List / Master list file, shown in the footnotes")
    s.add_argument("--indices", help="comma-separated index tickers shown with the market index on the opening page")
    s.add_argument("--index-heading", default="Indices", help="title prefix of that page")
    s.add_argument("--buckets", help="dashboard groups in order, separated by ';' (default: the S&P 500 IT sub-sectors)")
    s.add_argument("--group-col", help="universe column for the breadth table (default industry)")
    s.add_argument("--group-label", help="its label, singular (e.g. 'sector')")
    s.add_argument("--group-label-pl", help="its label for the subtitle (e.g. 'GICS sectors')")
    s.add_argument("--bench-note", help="sentence added to the relative-strength footnotes")
    s.add_argument("--trigger-cap", type=int, help="show at most this many trigger-watch rows")
    s.set_defaults(func=cmd_sector_doc)
    s = sub.add_parser("sector-style", help="sectors & style across four regions (PowerPoint)")
    s.add_argument("--prices", required=True)
    s.add_argument("--universe", required=True, help="universe CSV used for the Bloomberg template")
    s.add_argument("--edition", required=True)
    s.add_argument("--template", default=str(Path(__file__).parent / "report" / "assets" / "template_syz_a4.pptx"))
    s.add_argument("--asof")
    s.add_argument("--out", required=True)
    s.add_argument("--final", action="store_true")
    s.set_defaults(func=cmd_sector_style)
    s = sub.add_parser("trend", help="mechanical trend verdicts for the universe")
    s.add_argument("--prices", default="data/prices")
    s.add_argument("--universe", default="data/universe.csv")
    s.add_argument("--asof")
    s.add_argument("--charts", action="store_true")
    s.add_argument("--allow-partial", action="store_true")
    s.set_defaults(func=cmd_trend)
    s = sub.add_parser("ledger"); s.add_argument("--editions"); s.add_argument("--prices")
    s.set_defaults(func=cmd_later("Phase 2 (ledger)"))
    s = sub.add_parser("regime"); s.add_argument("--breadth"); s.add_argument("--prices"); s.add_argument("--backtest", action="store_true")
    s.set_defaults(func=cmd_later("Phase 3 (regime)"))
    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
