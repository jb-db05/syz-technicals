# CLAUDE.md – syz-technicals

Read `BUILD_SPEC.md` before any change. It is the specification; this file only sets working rules.

## Who you work for
Florian Marini, CFA, CMT – Head of Research, Syz Private Banking. Senior technical analyst, not a developer. Explain decisions in analyst terms, keep code explanations short, never assume he will debug Python himself.

## Working rules
- Build in the order of the spec: Module 1 (trend engine) to its Definition of done, then Module 2, then Module 3. Do not start a later module early.
- Pure technical analysis: no fundamentals, macro series or news enter any rule or output.
- Bloomberg exports in `data/` are the only data source in the production path. Never fetch external data without being asked; never fill, extrapolate or invent values – return `insufficient_data` with the missing input named.
- Every verdict rule in §3 of the spec has a test in `tests/test_trend_rules.py`. Change a rule and its test together. `pytest` must pass before every commit.
- When a result contradicts the spec, or the spec is silent, stop and ask one precise question – do not pick a default silently. The known open decision is the flat-200-day branch (§3.3); implement the default and flag it.
- Keep `legacy/` untouched. Do not refactor it.
- Commit small, descriptive commits. Branch names `feat/trend-engine`, `feat/ledger`, `feat/regime`.

## Trend rule in force (adopted 22 Nov 2026 – BUILD_SPEC §2.2 / §3.2, code `syztech/trend/swing_levels.py`)
- **Hierarchy (24 Nov 2026)**: (1) the 200-day slope sets the regime and caps the verdict on its side – a falling 200-day is never Bullish; (2) price structure confirms or denies – a denial alone gives Neutral with a tilt; (3) the 50-day vs the 200-day arbitrates – going against the regime needs both a structure break and the 50-day on the wrong side. One signal never overturns the slope, two confirmations do; the override works downward only. Full slope dominance was rejected (the 200-day lags after parabolas).
- **Direction**: 200-day average over 20 trading days – rising / flat / falling (0.20% band). Unchanged.
- **Support / resistance**, per side, in priority order: (1) Florian's drawn levels (text, then chart); (2) **swing levels** – last confirmed swing low / swing high; (3) 52-week low / high only where no swing is confirmed yet or the series has values ≤ 0 (negative yields).
- **Swing**: confirmed when the close reverses **k = 1.5 × the median one-month move of the past year** from the extreme (one-month move = stdev of daily log returns over 100 days × √20; median over 252 bars – robust threshold adopted 23 Nov 2026 so a parabola or crash cannot inflate it). Closes only, nothing filled.
- **A broken level stands**: after a lower low, the broken prior swing low stays the support until the resistance breaks; after a higher high, the prior swing high stays the resistance. Swing-level breaks count from the earlier of the two swing points; drawn levels keep their `levels_asof − 100 bars` window.
- **Verdict table (§3.3)**: rising + support intact + **50-day above the 200-day** = Bullish (variant B, 23 Nov 2026 – with the 50-day below it: Neutral+); falling + support broken = Bearish; in between Neutral with a tilt (Neutral+ / Neutral−), plus the death-cross and losing-momentum cases.
- Levels with a `52w` or `swing` origin in a universe file are recomputed at every run, never treated as drawn. Charts label them `swing low / swing high` (grey dashed); the trigger watch uses them.
- Basis: side-by-side study (`syztech/research/`, 436 series 2019–2026): robust k = 1.5 matches 68 / 80 published calls (drawn levels 67, 52-week 57), 14 / 17 Bearish calls caught, 2.85 verdict changes a year; variant B keeps 68 / 80 and 14 / 17 at 2.96 changes a year. No rule separated forward 1–3-month returns – the verdict describes the trend, it does not forecast.
- **Relative trend (adopted 24 Nov 2026)**: the same rule applied to the relative-strength line (price ÷ benchmark × 100) – **Outperform** (Bullish on the line) / **Neutral** (every Neutral shade) / **Underperform** (Bearish, Bearish losing momentum). Swing levels only (no drawn levels on RS lines), k = 1.5, variant B. Code `score.relative_verdict` → `rel_state`, `rel_verdict`, `rel_rule`. It replaces RS Mom + / − in the sector reports and the Sectors & Style document (dashboards, grids, heatmap, HTML); RS 3m stays as the early-warning number; RS Mom (`rs_trend`) stays in the data. Informational: it never changes the absolute verdict. Basis (`syztech/research/study_rs.py`, 342 RS lines, 110,963 weekly samples): 3.15 changes a year vs 1.67 for RS Mom; 13-week forward relative spread 0.84 pt vs 0.58 pt; Outperform always coincides with RS Mom +. Weekly cross-asset and Swiss list documents still print RS Mom – to be switched when they are next rebuilt.
- Never change the trend rule or k without a new study and Florian's decision.

## Style conventions (outputs, charts, text)
- Nunito Sans everywhere; Syz colours: Mint `#3BAF90` bullish, Blueberry `#4B5F80` neutral, Mulberry `#AC5D85` bearish, orange `#FF6C0E → #FFA400`, navy `#202945`.
- En dashes only (U+2013). Decimals: 1 for equities/commodities/crypto, 2 for FX and yields, 4 where `universe.csv` says so.
- Chart verdict badges: only the three reference badges in `syztech/charts/assets/verdict_badges_reference.pptx` (19 Nov 2026) – ▲ BULLISH on Mint, ◆ NEUTRAL on Blueberry, ▼ BEARISH on Mulberry; rounded 1.18 × 0.34 in, white bold capitals, letter-spaced. Drawn only by `syz_style.draw_verdict_badge`. No other badge text (no tilt, no "losing momentum", no subtitle inside the badge): Neutral+/Neutral- show NEUTRAL, Bearish_LM shows BEARISH; the shade stays in tables.
- Sectors & Style tables (24 Nov 2026): no `Last` column; the 200-day direction and the relative trend are shown as badges like the verdict – ▲ Rising / ◆ Flat / ▼ Falling and ▲ Outperform / ◆ Neutral / ▼ Underperform, white bold on Mint / Blueberry / Mulberry. The global sector map has three readings – momentum (200-day direction), relative trend, verdict: three pages in the PowerPoint, a three-way switch in the HTML. Sector reports (S&P 500 IT, Swiss) still use the earlier table layout.
- Chart source line: `Sources : Syz Research, Bloomberg`. Never name any external research provider in any output.
- Reports state facts and the rule that fired; no interpretation prose – the analyst writes that.

## Environment
Python 3.11+, pandas, numpy, openpyxl, matplotlib, pytest. Trading-day integer axis for all computations and charts.
