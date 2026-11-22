# S&P 500 IT technical special report – handoff package

| File | What it is |
|---|---|
| `build_sector_report.py` | Self-contained build script; parameters at the top. `template` writes the Bloomberg workbook, `build` writes the report |
| `BUILD_SPEC_sector_report.md` | Full description of the document: data, rules, every page, chart, colour and font |
| `INPUTS.md` | What to provide each edition, and how to run |
| `assets/` | Syz A4 template, logo, Nunito Sans fonts, reference chart badges |

**For a fresh chat:**
1. Give it these files, the refreshed Bloomberg export and the Master list workbook.
2. Ask it to set the parameters listed in `INPUTS.md` and run `python build_sector_report.py build`.

**Rule change, 22 Nov 2026:** support / resistance now come from volatility-scaled swings (k = 1.5) instead of the 52-week low / high, so the script no longer reproduces the 18 November PowerPoint, which was built under the old rule; it produces the edition under the current rule.

**Verified on 19 Nov 2026 (old rule):** run on the reference inputs, the script reproduces the published 18 November 2026 edition exactly:
- 77 charts, pixel for pixel;
- all PowerPoint slides and images;
- the HTML page.

The only difference is the save timestamp inside the three embedded chart workbooks.

The script is generated from the syztech repository by `tools/bundle_sector_report.py`. Rules change in the repository first; then re-bundle.
