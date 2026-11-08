# syz-technicals – BUILD_SPEC

Owner: Florian Marini, CFA, CMT – Head of Research, Syz Private Banking
Purpose: a maintained Python codebase for the quantitative layer of Syz Research technical analysis. Three modules are in scope (Tier 1): the **trend score engine**, the **verdict ledger** and the **regime score**. Build them in that order. The engine's job is to make the house doctrine mechanical, reproducible and testable; the discretionary verdict published in the Syz documents remains Florian's, and every disagreement between the two is reported, never hidden.

This document is the specification Claude Code builds against and the specification the claude.ai project will run against each week. Keep it current: when a rule changes, change it here first.

---

## 0. Principles (apply to every module)

1. **Pure technical analysis.** Inputs are price, volume, breadth and market-derived series only. No fundamentals, no macro series, no news.
2. **Bloomberg is authoritative.** All data arrives as Bloomberg exports (Excel) placed in `data/`. No external data fetching in the production path. A secondary feed may be added later behind a flag; it never overrides Bloomberg levels in anything that is published.
3. **Nothing invented.** If an input is missing for an instrument, the engine returns `insufficient_data` for that instrument and says which input is missing. It never fills, extrapolates or guesses.
4. **Deterministic and tested.** Every rule in §3 has at least one unit test. Tests are synthetic price series constructed to reproduce the documented corrections (§3.6). `pytest` must pass before any commit.
5. **Doctrine over indicators.** Oscillators and momentum (RSI, stochastics, MACD) never enter the verdict. They may be computed as informational overlays only.
6. **Syz conventions.** Nunito Sans in every chart; verdict colours Mint `#3BAF90` (bullish), Blueberry `#4B5F80` (neutral), Mulberry `#AC5D85` (bearish); orange accents `#FF6C0E → #FFA400`; navy `#202945`; en dashes only (U+2013), never em dashes; decimals: 1 for equities/commodities/crypto, 2 for FX and yields, 4 where the universe file says so. Source line on any standalone chart: `Sources : Syz Research, Bloomberg`. Never name an external research provider anywhere in an output.

---

## 1. Repository layout

```
syz-technicals/
  BUILD_SPEC.md              this file
  CLAUDE.md                  standing instructions for Claude Code
  README.md                  how to run, one page
  pyproject.toml             python >= 3.11; deps: pandas, numpy, openpyxl, matplotlib, pytest
  data/                      Bloomberg exports (git-ignored except the schema examples)
    universe.csv             instrument master (see §2.2)
    prices/                  one or more Bloomberg price exports (see §2.1)
    breadth/                 Lowry_XL.xlsx, Cross Asset Technical workbook (Market Breadth sheet)
    editions/                published Syz documents for the ledger (PPTX, HTML, PDF, CONFIG .py)
  syztech/                   the package
    io/                      loaders: bloomberg_prices.py, universe.py, editions.py
    indicators/              ma.py, bands.py, crosses.py, slope.py (pure functions on Series)
    trend/                   rules.py (the §3 logic), score.py, exceptions.py
    ledger/                  extract.py (verdicts from documents), returns.py, stats.py
    regime/                  components.py, composite.py, exposure.py, backtest.py
    charts/                  syz_style.py (fonts, colours), trend_chart.py, regime_chart.py
    cli.py                   entry points (see §6)
  tests/
    fixtures/                synthetic series builders
    test_indicators.py
    test_trend_rules.py      one test per documented correction (§3.6)
    test_ledger.py
    test_regime.py
  output/                    generated; git-ignored
```

Legacy scripts (`technical_takes.py`, `technical_takes_multi.py`, `build_cross_asset_pptx.py`, `build_focus_list_html.py`, `focus_list_config.py`) go in `legacy/` untouched. Do not refactor them in Phase 1; import from them only if a function is needed and already correct.

---

## 2. Data contracts

### 2.1 Price export (`data/prices/*.xlsx`)

Accept both Bloomberg shapes and normalise to one long table `date, ticker, close` (float, trading days only, ascending):

- **Wide**: first column `Date`, one column per ticker, header = Bloomberg ticker.
- **One sheet per ticker**: sheet name = ticker; columns include `Date` and `PX_LAST` (or `Last Price`).

Rules: drop non-trading rows (NaN close); de-duplicate dates (keep last); never forward-fill across missing days; keep a trading-day integer index for all computations (a calendar-date axis produces a weekly kink). Minimum history for a verdict: 320 trading days (200 for the MA + 100 for the band + 20 for the slope). Below that: `insufficient_data`.

Known Bloomberg export defects to handle: sheets where price/MA columns are rounded to whole units (rebuild everything from unrounded closes, never use exported MA columns); a hidden helper block on the Cross Asset Technical workbook sheet "Momentum Equities, Forex, Commo" (columns R/S) that holds **200-day MAs, not prices** – never read it as price.

### 2.2 Universe master (`data/universe.csv`)

| column | type | notes |
|---|---|---|
| ticker | str | Bloomberg ticker, key |
| name | str | full name as printed in Syz documents |
| asset_class | enum | equity, index, sector, fx, rate, commodity, crypto |
| group | str | publication grouping (e.g. Focus List sector, Cross-Asset block) |
| benchmark | str | ticker for relative strength; blank for fx, rates, commodities |
| decimals | int | 1, 2 or 4 |
| support | float | Florian's drawn key support (blue dashed line), optional |
| resistance | float | Florian's drawn key resistance, optional |
| levels_asof | date | date the support/resistance were last confirmed from a chart |
| badge | enum | current published verdict: Bullish, Neutral+, Neutral, Neutral-, Bearish, Bearish_LM |
| badge_asof | date | edition date of that badge |
| standing_position | str | optional editorial prior (e.g. "Bullish"); a prior, never an override |

Optional columns `support_origin` / `resistance_origin` record where each level came from: `text` (named in the commentary), `chart` (value tag of a horizontal line on the published chart), `52w low` / `52w high` (fallback, 8 Nov 2026: when neither text nor chart gives the level, the lowest / highest close of the 52 weeks before the data date, excluding the last bar). Priority: text, then chart (closest line on that side), then 52-week. A level named as a broken support in the text stays the support even when price is below it. A horizontal chart line above price that price closed above within the last 100 trading days is a broken support and is entered as the support (Florian, 8 Nov 2026 – Asian indices); the resistance is then the next line above, else the 52-week high.

`Neutral+` / `Neutral-` = Neutral with explicitly stated positive / negative tilt. `Bearish_LM` = "Bearish, but losing momentum".

Drawn levels are inputs, not outputs: the engine cannot draw Florian's lines. When `support`/`resistance` are blank the engine falls back to the 100-day band structure (§3.2) and flags `levels: band-fallback` in the output.

### 2.3 Breadth extract (`data/breadth/`)

`Lowry_XL.xlsx`: SPX, NYSE advances (NYAADV), declines (NYADCL), up volume, down volume, daily. Cross Asset Technical workbook, sheet "Market Breadth": % of S&P 500 members above 200d / 50d and any other breadth columns present – the sheet is the only valid source for those figures (they cannot be read off the deck's charts). Loader records the first available date of each series so the regime backtest knows its true history.

---

## 3. Module 1 – Trend score engine

### 3.1 Indicators (computed, never read from exports)

- `MA200`, `MA50`: simple moving averages of close.
- `slope200`: sign of `MA200[t] / MA200[t−20] − 1`, read at the right edge (last bar). Rising if > `+flat_band`, falling if < `−flat_band`, else flat. Default `flat_band = 0.0020` (0.20% over 20 trading days); a config parameter, to be calibrated against Florian's calls, never hard-coded elsewhere. A MA that fell for months but has hooked up over the last 20 days is **rising**.
- `MAX100`, `MIN100`: highest/lowest close of the prior 100 trading days (excluding the current bar).
- `last_band`: `upper` if the most recent event was a close above `MAX100`; `lower` if a close below `MIN100`; `none` if neither in the available history. Also record `last_band_date` and `last_band_level`. The breakout bar is the **first close** beyond the level; intraday pokes do not exist in close-only data by construction.
- `cross`: `golden` if `MA50` crossed above `MA200` within the last `cross_lookback` (default 40) trading days **and** `slope200` was rising on the cross date; `death` symmetrically with a falling slope. A cross without the matching slope is recorded as `cross_unqualified` and does not count. Record `cross_date`.
- `price_vs_200`: above / below.
- `bbw100`: Bollinger(100, 2) bandwidth `(UBB − LBB) / ((UBB + LBB)/2)` on the last band-break bar, for the implied target: `target = level × (1 ± bbw100)`. Reported only when `last_band` is set.
- `rs`: `close / benchmark × 100` with its own `MA200` and 63-day slope sign, when a benchmark exists. Informational; does not enter the verdict. `rs_trend`: `outperforming` (RS above its 200d and up over 63 days), `underperforming` (below and down), else `mixed`. Benchmarks for single stocks (8 Nov 2026): US → SPX Index, Europe/Switzerland/UK/Nordics → SXXP Index, Asia → MSCI Asia, Japan → Japanese index; TSMC → MSCI World (MXWO Index). Benchmarks that are not instruments themselves are added to the Bloomberg template automatically. Prices are in local currency, so a European stock's RS against SXXP (EUR) includes its currency move.

### 3.2 Structure inputs

Two sources, in priority order:

1. **Drawn levels** (`support`, `resistance` from the universe file). `support_broken = close < support`; `resistance_broken = close > resistance`. A close exactly at the trigger counts as **not** broken; a stated trigger "turn negative below X" means `close < X`, and when it is met the engine acts – it never waits for a "decisive" or "confirmed" break.
2. **Band fallback** when no drawn level exists: `support_broken ≡ last_band == lower`, `resistance_broken ≡ last_band == upper`.

HH/HL structure is read on the 100-day band events, not on minor intermediate swing lows (SMFG rule): losing a minor low without a `MIN100` break does not change the structure state.

### 3.3 Verdict rules (apply in order; first match wins)

```
insufficient_data            if history < 320 bars

# Rising 200-day
Bullish                      if slope200 == rising and not support_broken      # also covers rising + resistance_broken (golden cross / hooked-up MA + resistance break → straight to Bullish, may skip a step)
Bearish (ST), LT Neutral     if slope200 == rising and support_broken and MA50 < MA200   # death cross complete with a still-rising 200d (KOSPI, 8 Nov 2026)
Neutral+                     if slope200 == rising and support_broken        # broken higher-low → Neutral with positive tilt

# Falling 200-day
Bearish_LM                   if slope200 == falling and support_broken and price_vs_200 == above and MA50 slope > 0   # "losing momentum"
Bearish                      if slope200 == falling and support_broken
Neutral                      if slope200 == falling and resistance_broken   # upgrade from Bearish needs the resistance break
Neutral-                     if slope200 == falling and not support_broken  # declining MA does not override an intact range

# Flat 200-day
Bearish                      if slope200 == flat and support_broken and (MA50 < MA200 or MA50 slope < 0)   # 50d below or rolling over (EUR/CHF, 8 Nov 2026)
Neutral-                     if slope200 == flat and (support_broken or cross == death or price_vs_200 == below)
Neutral+                     if slope200 == flat and (resistance_broken or cross == golden or price_vs_200 == above)
Neutral                      otherwise
```

Notes that the implementation must respect:

- `support_broken` is a **state**, not an event: once a drawn support (or `MIN100`) has been broken, it stays broken until `resistance_broken` (a `MAX100` break or a close above the drawn resistance) resets the structure. Symmetrically for `resistance_broken`. Implement as a small state machine over the history, not as a look at the last bar only.
- A golden cross **together with** a resistance break is sufficient for Bullish even when the 200-day slope has only just hooked up; do not hold at Neutral waiting for the slope to become "decisive" (crypto correction, 27 Sep 2026).
- A death cross confirms Bearish only once the support has actually broken; with support intact the verdict is Neutral- and the level is the trigger (CAC 40, 1 Nov 2026). This outranks the cross.
- `standing_position` is a tie-break prior only: if the mechanical verdict is Neutral (no tilt) and a standing position exists, report the standing position in a separate column `prior`; never change the mechanical verdict.
- Score mapping: Bullish +2, Neutral+ +1, Neutral 0, Neutral- −1, Bearish_LM −1, Bearish −2.

Decisions confirmed by Florian (8 Nov 2026):

- **Rule order.** `support_broken` and `resistance_broken` are mutually exclusive states, so Bearish_LM is tested before Bearish, and falling + `resistance_broken` (Neutral) before falling + intact (Neutral-). This is the order above.
- **Flat 200-day branch.** `flat + support_broken + MA50 < MA200` → **Bearish**. No minimum break size: a close below the trigger is a break (EUR/CHF, 25 Oct 2026, would mechanically have been Bearish; an analyst hold at Neutral- is a discretionary override, recorded in `override_reason`).
- **Drawn level and band on the same side.** When a drawn support exists, a `MIN100` break does not by itself set `support_broken` (the drawn level has priority), but it resets an older `resistance_broken` state to intact. Symmetrically, with a drawn resistance a `MAX100` break resets an older `support_broken` state without setting `resistance_broken`.
- **Drawn levels are dated.** A close beyond a drawn level counts from `levels_asof` minus `levels_lookback` (default 100 trading days, one band window) onward; a blank `levels_asof` means the whole history. The 100-day lookback was added after the first real run (KOSPI broke 5,275 in the week before the level was dated 8 Nov 2026); confirmed 8 Nov 2026.
- **A broken support stands until the resistance breaks** (8 Nov 2026). A close back above a broken support does not repair the structure; only a resistance break (drawn, or MAX100 when none is drawn) resets it (GBP/USD, aluminium, gold).
- **Rising 200d + support broken + MA50 < MA200 → Bearish short term, with long term Neutral stated** (8 Nov 2026). The verdict is Bearish (score −2) and the column `lt_view` reads "Neutral – 200d rising"; the report and chart carry both.
- **Flat 200d + support broken + MA50 below or rolling over (20-bar MA50 slope < 0) → Bearish** (8 Nov 2026, EUR/CHF).
- **A downgrade may skip a step** (8 Nov 2026), as an upgrade may: Bullish → Bearish / Bearish_LM directly when the rules say so (BGCI).
- **MA50 slope** in the Bearish_LM and flat rules: `MA50[t] / MA50[t−20] − 1 > 0`, same 20-bar window as `slope200`, no flat band.

### 3.4 Exceptions report

For each instrument compare `mechanical_verdict` with `badge` from the universe file and classify:

- `agree`
- `tilt_only` – same side, tilt differs (Neutral vs Neutral+/−)
- `one_step` – adjacent verdicts (e.g. Neutral- vs Bearish)
- `conflict` – opposite sides or two steps apart
- `trigger_hit` – a drawn level was crossed since `badge_asof` (the verdict must change under the doctrine)
- `levels_stale` – `levels_asof` older than 28 days

Grading ladder (confirmed 8 Nov 2026): Bearish (incl. Bearish_LM) | Neutral- | Neutral | Neutral+ | Bullish. Same side → `tilt_only`; one rung apart across sides → `one_step` (Bullish vs Neutral+, Neutral- vs Bearish); two rungs or more → `conflict` (Bullish vs Neutral). Each instrument is listed once, in the first section that applies in the order above.

Output a Markdown report ordered: `trigger_hit`, `conflict`, `one_step`, `tilt_only`, `levels_stale`, then `agree` as a count. Each row: ticker, name, last close (correct decimals), MA200 and its slope, last band event with date and level, drawn support / resistance, mechanical verdict, badge, classification, one-line reason built from the rule that fired (e.g. "200d rising, support 7,500.0 intact → Bullish; badge Neutral-"). No prose beyond that line – the interpretation is written by the analyst.

### 3.5 Weekly run output

`output/trend_scores_<date>.csv` (all columns above plus score) and `output/exceptions_<date>.md`. Optional `--charts` writes one PNG per `conflict`/`trigger_hit` instrument: close, MA50, MA200, MAX100/MIN100 bands, drawn levels, verdict badge top-right, Syz style, 5 years, log scale, trading-day axis.

### 3.5b Publication charts (`syztech deck-charts`, agreed 8 Nov 2026)

One 16:9 chart per instrument, Syz style: close, MA50 (blue #2F6FDE), MA200 (orange), 100-day high/low band with today's values tagged (8 Nov 2026, replaces the 52-week range; 52-week fallback levels drawn grey and labelled `52w`), drawn levels and trendlines with their current value tagged on the axis, last price and MA200 tagged, published verdict as the badge (rules-based reading, labelled as such, where nothing is published), relative-strength panel for single stocks. 5 calendar years; log scale, linear when the window holds values ≤ 0 (negative yields). Trendlines are inputs in `data/trendlines.csv` (two anchor points each, snapped to the actual swing high/low close); they are drawn only and do not enter the verdict. The y-scale is set by price, averages and levels, so a distant trendline never stretches it.

### 3.6 Required tests (synthetic fixtures; names are the historical corrections)

Each fixture builds a 400-bar close series by concatenating segments (trend, range, break) so that the stated conditions hold at the last bar. Assert the verdict and the rule id that fired.

| test | construction | expected |
|---|---|---|
| `csi300_falling_ma_intact_structure` | long decline then range above drawn support; MA200 falling; no `MIN100` break | Neutral- |
| `csi300_death_cross_after_support_break` | as above, then close below drawn support, MA50 < MA200 | Bearish |
| `jpm_adxy_falling_ma_broken_support` | falling MA200, `MIN100` break, no drawn levels | Bearish (levels: band-fallback) |
| `unicaja_rising_ma_minor_low_lost` | rising MA200, `MAX100` break recent, then a dip below a minor swing low without `MIN100` break | Bullish |
| `smfg_rising_ma_minor_low_lost` | same construction, equity with benchmark | Bullish |
| `alphabet_rising_ma_lower_highs` | rising MA200, lower highs after a peak, no `MIN100` break, RS negative | Bullish |
| `gold_rising_ma_below_price_support_holds` | rising MA200, price below MA200, drawn support intact | Bullish |
| `usdbrl_falling_ma_price_above_higher_lows` | falling MA200, prior `MIN100` break, price back above MA200, MA50 rising, drawn resistance not broken | Bearish_LM |
| `usdbrl_resistance_break_slope_still_falling` | as above plus close above drawn resistance, MA200 still falling | Neutral |
| `crypto_golden_cross_hooked_ma_resistance_break` | MA200 fell for months, hooked up over last 20 bars, golden cross, `MAX100` break | Bullish |
| `eurusd_falling_ma_support_intact` | falling MA200, price below MA200, drawn support intact | Neutral- |
| `dxy_flat_or_rising_ma_below_resistance` | rising MA200, price below drawn resistance, support intact | Bullish |
| `silver_close_below_trigger` | MA200 rolled over, death cross, close one tick below drawn support | Bearish |
| `gold_close_above_floor` | same date construction, close above drawn support | Neutral- |
| `cac40_declining_ma_death_cross_range_intact` | MA200 falling, death cross, price 6% above drawn support | Neutral- |
| `eurchf_flat_ma_small_support_loss` | flat MA200, close ~0.4% below drawn support, MA50 < MA200 | Bearish (§3.3 flat branch, confirmed) |
| `slope_reads_right_edge` | MA200 falling for 150 bars then rising for 25 | slope200 == rising |
| `insufficient_history` | 250 bars | insufficient_data |

Also: `test_indicators.py` checks MA/band/cross arithmetic against hand-computed values on a 30-bar series, and that the golden cross without a rising slope is `cross_unqualified`.

---

## 4. Module 2 – Verdict ledger

### 4.1 Extraction (`syztech/ledger/extract.py`)

Parse every document in `data/editions/`:

- Cross-Asset Technicals PPTX: one verdict per chart slide. Match text runs with `<a:t[^>]*>` (some runs are `<a:t xml:space="preserve">`); detect the verdict from the ▲/◆/▼ glyph first, fall back to the words BULLISH/BEARISH/NEUTRAL only when no glyph exists (the word appears in prose). Review-table badges on slides 2–3 are entity-based and are **not** ledger entries; chart-slide verdicts are.
- Cross-Asset Technicals / Focus List HTML: cards with verdict chips; tilt words ("negative tilt", "positive tilt") set Neutral−/Neutral+.
- Technical Takes CONFIG `.py` files: `CONFIG["verdict"]`, levels, invalidation, target.
- FX Monthly PPTX: "Technical View – <verdict>" headings; labels "Bullish, but upside capped" map to Bullish with flag `capped`.

Ledger row: `edition_date, publication, ticker, name, verdict, tilt, trigger_level (support/resistance named in text, if any), invalidation, target, source_file, slide_or_card`.

A **verdict change** is a row whose verdict differs from the previous row for the same ticker and publication. Store the full ledger (`output/ledger.csv`) and the change log (`output/ledger_changes.csv`).

### 4.2 Forward returns (`returns.py`)

For each change: close on `edition_date` (or the first trading day after), then returns at +21, +63, +126 trading days, signed by direction (Bullish +, Bearish −, Neutral 0 → report raw). Two measures: own buy-and-hold return, and excess over the instrument's benchmark where one exists. If the horizon is not yet reached, the cell is blank, never estimated.

### 4.3 Statistics (`stats.py`)

Hit rate, mean and median signed return, by: publication, asset class, transition type (Bearish→Neutral-, Neutral-→Bearish, Neutral→Bullish, Bearish→Bullish …), and tilt. Compare with a mechanical baseline: the §3 engine run historically on the same dates (requires the drawn levels as of each edition – when unavailable, run the band-fallback and label the baseline `band-fallback`). Report sample sizes next to every statistic; below 10 observations print the number and no percentage.

Tests: a fixture PPTX/HTML pair with known verdicts; a change log built from three synthetic editions; return arithmetic on a hand-built series.

---

## 5. Module 3 – Regime score

### 5.1 Components (each a daily series scored −1 / 0 / +1 on its own **trend**, not level)

| component | series | rule |
|---|---|---|
| participation_vd | Volume Demand − Volume Supply (existing replica, from up/down volume) | sign of spread, with the existing regime definition reused exactly |
| participation_bp | Buying Power − Selling Pressure (existing replica) | sign of spread |
| breadth_200 | % S&P 500 above 200d (Market Breadth sheet) | +1 above its 50-day MA and > 50%; −1 below its 50-day MA and < 50%; else 0 |
| breadth_ad | NYSE cumulative A/D line | +1 above a rising 200d; −1 below a falling 200d; else 0 |
| vol | VIX | +1 below its 200d and 3-month VIX > spot (contango); −1 above 200d and backwardation; else 0 |
| risk_small_large | Russell 2000 / S&P 500 | sign of 63-day change of the ratio relative to its 200d |
| risk_cyc_def | S&P cyclicals / defensives (or equal-weight sector proxies) | same |
| risk_hb_lv | S&P high-beta / low-vol | same |
| risk_cu_au | Copper / Gold | same |
| credit | HY / IG price ratio (or inverted OAS spread) | same |

Components whose series are not present in `data/breadth/` are reported as `missing` and excluded from the composite with the weight renormalised – and the report says which were excluded. The first date of the composite is the latest first-available date among the components actually used.

### 5.2 Composite and exposure

Composite = equal-weighted mean of available components, rescaled to 0–100, smoothed by a 5-day mean. Regimes: `Risk-on ≥ 70`, `Constructive 55–70`, `Fragile 40–55`, `Risk-off < 40`. Exposure mapping reuses the existing beta-dial logic: 130 / 100 / 70 / T-bill by regime, weekly rebalance on Friday close, 1-week execution lag. No parameter fitting: thresholds are rule-based and fixed before the backtest; the backtest only **reports** regime statistics (time in regime, S&P 500 annualised return, volatility, max drawdown, hit rate of the following 63 days) and the dial's equity curve versus buy-and-hold with the statistics table inside the chart.

Tests: component scoring on hand-built series; renormalisation when a component is missing; regime assignment at the boundaries; lag correctness (no same-day execution).

---

## 6. CLI

```
syztech trend   --prices data/prices --universe data/universe.csv --asof 2026-11-07 [--charts]
syztech ledger  --editions data/editions --prices data/prices
syztech regime  --breadth data/breadth --prices data/prices [--backtest]
syztech inspect --prices data/prices            # prints tickers, first/last date, bar count, gaps
```

Every command prints a one-screen summary and writes to `output/`. Exit non-zero on `insufficient_data` for any instrument unless `--allow-partial`.

---

## 7. Definition of done – Phase 1 (trend engine)

- `syztech inspect` runs on the real Bloomberg export without manual edits.
- All §3.6 tests pass.
- `syztech trend` on the Focus List + Cross-Asset universe produces `trend_scores` and `exceptions`; the exceptions report has been reviewed by Florian once and every `conflict` is either a doctrine clarification (then added to §3 and to a test) or an accepted discretionary override (then recorded in the universe file column `override_reason`).
- `README.md` documents the run, the §3.3 decisions, and the `flat_band` / `cross_lookback` parameters.

Phase 2 (ledger) and Phase 3 (regime) start only after Phase 1 is done.
