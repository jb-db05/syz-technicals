# syz-technicals

Quantitative layer of Syz Research technical analysis. The specification is `BUILD_SPEC.md`; working rules are in `CLAUDE.md`.
Status: **Phase 1 (trend engine)** – indicators (§3.1), structure and verdict rules (§3.2–3.3) and all §3.6 tests are in place. Exceptions report (§3.4) and conflict / trigger charts (§3.5) are built; first real run 8 Nov 2026.

## Run

```bash
pip install -e ".[dev]"
syztech inspect --prices data/prices                    # tickers, first/last date, bars, export defects
syztech universe-draft --prices data/prices             # writes data/universe.csv from the tickers found
syztech trend --prices data/prices --universe data/universe.csv --asof 2026-11-06 --charts   # scores, exceptions report, charts
syztech price-template --end 2026-11-06                 # Bloomberg template from universe.csv
pytest
```

Outputs go to `output/` (git-ignored). `trend` exits non-zero if any instrument is `insufficient_data`, unless `--allow-partial`.

## Data

Bloomberg exports only, placed in `data/` (git-ignored). Prices: wide sheet (`Date` + one column per ticker) or one sheet per ticker (`Date`, `PX_LAST`). The loader never forward-fills, de-duplicates dates (keeps last), never reads the sheet "Momentum Equities, Forex, Commo" as prices, and reports `#N/A` cells, duplicates, gaps > 5 days, whole-number (rounded) columns and runs of identical closes. Column template for the universe file: `data/schema_examples/universe_header.csv`.

## Parameters (`syztech/trend/rules.py › TrendParams` – the only place they live)

| parameter | default | meaning |
|---|---|---|
| `flat_band` | 0.0020 | 200-day MA is *flat* when its 20-bar change is within ±0.20%. To be calibrated against Florian's calls. |
| `cross_lookback` | 40 | a golden/death cross counts only if within the last 40 bars **and** the 200-day slope agreed on the cross bar. |
| `slope_lookback` | 20 | bars for the 200-day (and 50-day) slope, read at the last bar. |
| `band_window` | 100 | MAX100 / MIN100, prior bars only. |
| `min_history` | 320 | bars needed for a verdict. |
| `levels_lookback` | 100 | a drawn-level break counts from 100 bars before `levels_asof` (confirmed). |

## Doctrine decisions (confirmed 8 Nov 2026 – full text in BUILD_SPEC §3.3)

1. **Flat 200-day branch:** flat + support broken + MA50 below or rolling over → Bearish, no minimum break size. A Neutral- hold (EUR/CHF, 25 Oct 2026) is a discretionary override, recorded in `override_reason`.
2. **Rule order:** Bearish_LM before Bearish; falling MA + resistance broken (Neutral) before falling MA + intact (Neutral-).
3. **Drawn level vs band, same side:** the drawn level decides the break; a band break on that side only resets the opposite state.
4. **Drawn levels are dated:** closes beyond a level count from 100 bars before `levels_asof` onward (confirmed).
5. **MA50 slope (Bearish_LM):** 20-bar change > 0, no flat band.
6. **Exceptions grading:** Bearish (incl. Bearish_LM) | Neutral- | Neutral | Neutral+ | Bullish. Same side → tilt_only; one rung across sides → one_step; two rungs or more → conflict.
7. **A broken support stands until the resistance breaks;** a close back above it does not repair the structure.
8. **Rising 200-day + support broken + MA50 < MA200 → Bearish short term,** with "long term Neutral – 200d rising" in the `lt_view` column, report and chart.
9. **A downgrade may skip a step,** as an upgrade may.
