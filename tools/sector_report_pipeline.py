
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PIPELINE – step 1 (template) and step 2 (build). Mirrors the syztech CLI: deck-charts + sector-doc --html-out.
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
UNIVERSE_COLUMNS = ["ticker", "name", "asset_class", "group", "benchmark", "decimals", "support", "resistance",
                    "levels_asof", "badge", "badge_asof", "standing_position", "override_reason",
                    "support_origin", "resistance_origin", "industry", "bucket", "syz_lists"]
VERDICTS = ("Bullish", "Neutral+", "Neutral", "Neutral-", "Bearish_LM", "Bearish")


def _slug(t: str) -> str:
    return t.replace(" ", "_").replace("/", "-")


def _gics_full(truncated) -> str:
    """Full GICS sub-industry from Bloomberg's 30-character text; stops the run if it is unknown."""
    if not isinstance(truncated, str) or not truncated.strip():
        return ""
    hits = [g for g in GICS_IT if g.startswith(truncated.strip())]
    if len(hits) != 1:
        raise SystemExit(f"GICS sub-industry '{truncated}' not recognised – add it to GICS_IT")
    return hits[0]


def make_template() -> Path:
    """Step 1: the Bloomberg workbook (Settings, Reference, one BDH sheet per ticker incl. the benchmark)."""
    from datetime import date
    rows = [dict(ticker=SECTOR_TICKER, name=DISPLAY_NAMES.get(SECTOR_TICKER, SECTOR_TICKER), asset_class="sector",
                 group="Sector index", benchmark=BENCH_TICKER, decimals=1)]
    rows += [dict(ticker=t, name=DISPLAY_NAMES.get(t, ""), asset_class="equity", group=GROUP, benchmark=BENCH_TICKER,
                  decimals=1) for t in TICKERS]
    uni = pd.DataFrame(rows, columns=COLUMNS)
    out = INPUT_DIR / "Bloomberg_template_SPX_IT.xlsx"
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    end = date.fromisoformat(TEMPLATE_END) if TEMPLATE_END else date.today()
    build_template(with_benchmarks(uni), out, date.fromisoformat(TEMPLATE_START), end, reference=True)
    print(f"written: {out} – open in Excel with the Bloomberg add-in, refresh, save, then run: build")
    return out


def prepare_universe(prices, asof, work: Path) -> Path:
    """Universe CSV: names, GICS sub-industry and bucket, 52-week levels, Syz list tags. Nothing is invented."""
    ref = load_reference(PRICES_XLSX).set_index("ticker") if PRICES_XLSX else pd.DataFrame()
    missing_px = [t for t in [SECTOR_TICKER, BENCH_TICKER] + TICKERS if t not in prices.reports or prices.reports[t].bars == 0]
    if missing_px:
        print(f"no prices (left out, never filled): {', '.join(missing_px)}")
    if SECTOR_TICKER in missing_px or BENCH_TICKER in missing_px:
        raise SystemExit("insufficient_data: the sector index and the benchmark must both have prices")
    no_name = [t for t in [SECTOR_TICKER] + TICKERS if t not in DISPLAY_NAMES]
    if no_name:
        raise SystemExit(f"add a display name in DISPLAY_NAMES for: {', '.join(no_name)}")
    rows = []
    for t in [SECTOR_TICKER] + TICKERS:
        if t in missing_px:
            continue
        is_sector = t == SECTOR_TICKER
        ind = "" if is_sector else _gics_full(ref["industry"].get(t) if "industry" in ref else None)
        if not is_sector and not ind:
            raise SystemExit(f"insufficient_data: GICS sub-industry missing for {t} (Reference sheet)")
        s = prices.series(t).dropna()
        end = s.index[-1]
        w = s[(s.index > end - pd.Timedelta(weeks=52)) & (s.index < end)]     # prior 52 weeks, last bar excluded
        rows.append(dict(ticker=t, name=DISPLAY_NAMES[t], asset_class="sector" if is_sector else "equity",
                         group="Sector index" if is_sector else GROUP, benchmark=BENCH_TICKER, decimals=1,
                         support=float(w.min()), resistance=float(w.max()), levels_asof=str(asof),
                         support_origin=f"52w low ({w.idxmin().date()})", resistance_origin=f"52w high ({w.idxmax().date()})",
                         industry=ind or None, bucket=(BUCKET.get(ind, "Hardware & equipment") if ind else None)))
    u = pd.DataFrame(rows).reindex(columns=UNIVERSE_COLUMNS).astype(object)
    if MASTERLIST_XLSX:
        tags, issues = tag_universe(u, load_lists(MASTERLIST_XLSX), aliases=LIST_ALIASES)
        for i in issues:
            print(f"Syz lists: {i}")
        u["syz_lists"] = u.ticker.map(tags).fillna("")
    else:
        u["syz_lists"] = ""
    work.mkdir(parents=True, exist_ok=True)
    path = work / "universe_spx_it.csv"
    u.to_csv(path, index=False)
    return path


def _lists_of(u) -> list[str]:
    v = getattr(u, "syz_lists", None)
    got = [x.strip() for x in v.split(";")] if isinstance(v, str) else []
    return sorted([x for x in got if x], key=lambda x: (x != "Focus List", x))


def make_charts(prices, uni, asof, out_dir: Path) -> None:
    """One A4 chart per instrument; the sector chart carries the breadth panel."""
    scores = score_universe(prices, uni, asof).set_index("ticker")
    bench_set = set(uni.benchmark.dropna())
    members = [t for t in uni.ticker if t != SECTOR_TICKER and t not in bench_set and t in prices.reports
               and prices.reports[t].bars > 0]
    sec = prices.series(SECTOR_TICKER)
    sec = sec[sec.index <= pd.Timestamp(asof)]
    breadth = breadth_history({t: prices.series(t)[lambda z: z.index <= pd.Timestamp(asof)] for t in members}, sec.index)
    last = breadth.dropna().iloc[-1]
    print(f"breadth: {len(members)} stocks; {last.rising:.0f}% with a rising 200-day, {last.above:.0f}% above it")
    done, skipped = 0, []
    for i, u in enumerate(uni.itertuples(index=False), start=1):
        t = u.ticker
        s = prices.series(t)
        s = s[s.index <= pd.Timestamp(asof)]
        sc = scores.loc[t]                                            # levels as resolved by the engine (swing levels)
        row = {"ticker": t, "name": u.name, "decimals": u.decimals, "support": sc.get("support"), "resistance": sc.get("resistance"),
               "support_origin": sc.get("support_origin"), "resistance_origin": sc.get("resistance_origin")}
        v = sc["verdict"]
        badge = v if v in VERDICTS else None                                  # no published views: rules-based reading
        group = (u.group or "Other").replace(" – ", "_").replace(" & ", "_").replace(" ", "_")
        f = out_dir / group / f"{i:03d}_{_slug(t)}.png"
        try:
            deck_chart(s, row, f, badge=badge, badge_kind="mechanical", trendlines=None, benchmark=prices.series(BENCH_TICKER),
                       benchmark_name=BENCH_NAME, page="a4", breadth=breadth if t == SECTOR_TICKER else None,
                       breadth_label=BREADTH_LABEL, lists=_lists_of(u))
            done += 1
        except Exception as e:                      # one bad series must not stop the run
            skipped.append(f"{t}: {e}")
    print(f"charts: {done} written to {out_dir}")
    for s_ in skipped:
        print(f"  skipped – {s_}")


def _jpg_charts(uni, chart_dir: Path, small: Path) -> dict:
    small.mkdir(parents=True, exist_ok=True)
    files = {f.stem.split("_", 1)[1]: f for f in chart_dir.glob("*/*.png")}
    out = {}
    for t in uni.ticker:
        f = files.get(_slug(t))
        if f is None:
            continue
        jp = small / (f.stem + ".jpg")
        with Image.open(f) as im:
            im.convert("RGB").resize((1800, int(1800 * im.height / im.width)), Image.LANCZOS).save(jp, quality=88)
        out[t] = jp
    return out


def build() -> None:
    """Step 2: universe -> charts -> PowerPoint -> HTML."""
    for p in (PRICES_XLSX, ASSET_DIR / "template_syz_a4.pptx", ASSET_DIR / "syz_logo.png"):
        if not Path(p).exists():
            raise SystemExit(f"missing input: {p}")
    prices = load_prices(PRICES_XLSX)
    for e in prices.file_notes:
        print(f"prices: {e}")
    asof = pd.Timestamp(ASOF).date() if ASOF else prices.prices.date.max().date()
    work = OUT_DIR / "work"
    uni, problems = load_universe(prepare_universe(prices, asof, work))
    for p in problems:
        print(f"universe: {p}")
    chart_dir = OUT_DIR / "charts_a4" / str(asof)
    make_charts(prices, uni, asof, chart_dir)

    scores = score_universe(prices, uni, asof)
    df = instrument_table(scores, uni, prices, {})
    df = df.merge(scores[["ticker", "rule"]], on="ticker", how="left")
    df = df.merge(uni[["ticker", "industry", "bucket", "syz_lists"]], on="ticker", how="left")
    df = add_momentum(df, prices)
    sec = df[df.ticker == SECTOR_TICKER]
    stocks = df[df.ticker != SECTOR_TICKER]
    insufficient = stocks[~stocks.verdict.isin(VERDICTS)].name.tolist()
    for t, nm in zip(uni.ticker, uni.name):        # dropped for lack of a scored close: named, never filled
        if t not in set(df.ticker) and t in prices.reports:
            insufficient.append(f"{nm} ({prices.reports[t].bars} bars)")
    small = work / f"doc_charts_{asof}"
    charts = _jpg_charts(uni, chart_dir, small)
    d = pd.Timestamp(asof)
    asof_txt = f"{d.day} {d:%B %Y}"
    stem = f"Syz_SP500_IT_Technicals_{EDITION.replace(' ', '_')}"
    out = OUT_DIR / f"{stem}.pptx"
    build_sector_doc(stocks, sec.iloc[0], charts, out, ASSET_DIR / "template_syz_a4.pptx", title=TITLE, edition=EDITION,
                     asof=asof_txt, bench=BENCH_NAME, sector_name=SECTOR_SHORT, insufficient=insufficient, work=small,
                     draft=DRAFT, lists_asof=LISTS_ASOF)
    print(f"written: {out} ({len(stocks)} stocks, {len(charts)} charts; no verdict: {', '.join(insufficient) or 'none'})")
    h = build_sector_html(stocks, sec.iloc[0], charts, OUT_DIR / f"html_{EDITION.replace(' ', '_')}", title=TITLE,
                          edition=EDITION, asof=asof_txt, bench=BENCH_NAME, sector_name=SECTOR_SHORT,
                          insufficient=insufficient, draft=DRAFT, lists_asof=LISTS_ASOF)
    print(f"written: {h} (HTML; publish the folder with its charts/ and syz_logo.png)")


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "build"
    if mode == "template":
        make_template()
    elif mode == "build":
        build()
    else:
        raise SystemExit("usage: build_sector_report.py [template|build]")
