# syz-technicals

Quantitative layer of Syz Research technical analysis. The specification is `BUILD_SPEC.md`; working rules are in `CLAUDE.md`.
Status: **Phase 1 (trend engine)** – indicators (§3.1), structure and verdict rules (§3.2–3.3) and all §3.6 tests are in place. Exceptions report (§3.4) and charts (§3.5) come next, once `data/universe.csv` is filled.

## Run

```bash
pip install -e ".[dev]"
syztech inspect --prices data/prices                    # tickers, first/last date, bars, export defects
syztech universe-draft --prices data/prices             # writes data/universe.csv from the tickers found
syztech trend --prices data/prices --universe data/universe.csv --asof 2026-11-07
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

## Open decision and implementation choices to confirm

1. **Flat 200-day branch (§3.3, open).** Default implemented: flat + support broken + MA50 < MA200 → **Bearish**. EUR/CHF on 25 Oct 2026 was held at Neutral-. Test `test_eurchf_flat_ma_small_support_loss` documents it.
2. **Rule order (§3.3).** As listed, two rules can never fire, because a broken support and a broken resistance cannot both be the current state. The engine tests *Bearish, losing momentum* before *Bearish* and *falling MA + resistance broken → Neutral* before *falling MA + intact → Neutral-*, which is what the USD/BRL tests in §3.6 require.
3. **Drawn level and band on the same side.** When a drawn support exists, a MIN100 break does not by itself set "support broken" (the drawn level has priority) but it cancels an older "resistance broken" state; symmetrically for MAX100 with a drawn resistance.
4. **Drawn levels are dated.** A close beyond a drawn level only counts from `levels_asof` onward; blank `levels_asof` means the whole history.
5. **"MA50 slope > 0"** in the Bearish_LM rule uses the same 20-bar window as the 200-day slope, with no flat band.
