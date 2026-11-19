# Inputs – what you provide for each edition

The script needs **two files and three settings** each time. Everything else is fixed and ships in `assets/`.

## Each edition

| # | Input | Where it goes | Reference value (18 Nov 2026) | If missing |
|---|---|---|---|---|
| 1 | **Bloomberg price export**: the template made by `python build_sector_report.py template`, opened in Excel with the Bloomberg add-in, refreshed (all sheets filled, no `#N/A`), saved as .xlsx | `inputs/Bloomberg_template_SPX_IT.xlsx` (`PRICES_XLSX`) | 81 sheets: Instructions, Settings, Reference, S5INFT Index, 76 stocks, SPX Index; data 2 Jan 2019 – 17 Nov 2026 | Run stops: "missing input". A ticker without prices is left out and named, never filled |
| 2 | **Syz Master list workbook** (sheets `Master_list_F` and `Focus List`) | `inputs/<date>_MasterList.xlsx` (`MASTERLIST_XLSX`) | `20261029_MasterList.xlsx` | Set `MASTERLIST_XLSX = None`: no list tags anywhere |
| 3 | **Master list date**, shown in footnotes | `LISTS_ASOF` | `"29 Oct 2026"` | Footnote without a date |
| 4 | **Edition date**: cover, file names | `EDITION` | `"18 November 2026"` | – |
| 5 | **Draft or final**: `True` prints "DRAFT – FOR INTERNAL REVIEW" on the cover and the HTML | `DRAFT` | `True` | – |

Optional:
- `ASOF = "YYYY-MM-DD"` to cut the data at a past date. The default is the last date in the export.

## Only when the S&P 500 IT membership changes

| Input | Where | Rule |
|---|---|---|
| Constituent tickers (Bloomberg, e.g. `NVDA UW Equity`) | `TICKERS` | Then re-run `template` and refresh it in Bloomberg |
| Display name of each new ticker | `DISPLAY_NAMES` | The run stops and names any ticker without a display name. Write the published name, not the Bloomberg upper-case NAME |
| Hand-checked name aliases for the Syz lists | `LIST_ALIASES` | Only when the run prints "name differs, not tagged" and you confirm it is the same company |
| New GICS sub-industry | `GICS_IT`, `BUCKET` | The run stops on an unknown sub-industry |

## Fixed (ship once, do not change)

`assets/`:
- `template_syz_a4.pptx`: Syz A4 template;
- `syz_logo.png`;
- `fonts/NunitoSans-*.ttf`;
- `verdict_badges_reference.pptx`: the reference for the three chart badges.

## Run

Steps 1–2 make the price template, step 3 builds the report:

1. Run template mode:
   ```bash
   python build_sector_report.py template
   ```
2. In Excel with the Bloomberg add-in: open `inputs/Bloomberg_template_SPX_IT.xlsx`, refresh all, wait until every sheet is filled, then save.
3. Build the report:
   ```bash
   python build_sector_report.py build
   ```

**Outputs:**
- `output/Syz_SP500_IT_Technicals_<EDITION>.pptx`
- `output/html_<EDITION>/` (`index.html` + `charts/` + `syz_logo.png`; publish the whole folder)
- `output/charts_a4/<asof>/…png`
- `output/work/` (universe CSV, JPEG copies)

**Requirements:** Python 3.11+, with:
```bash
pip install pandas numpy openpyxl matplotlib python-pptx Pillow
```
Build time is about 45 seconds.
