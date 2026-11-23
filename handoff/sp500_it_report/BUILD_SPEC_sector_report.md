# Build spec – S&P 500 Information Technology: Technical special report

Version of 22 November 2026 (trend levels: swing rule adopted 22 Nov 2026). The reference edition is **18 November 2026, data to 17 November 2026**. It has two outputs:

- **PowerPoint:** Syz A4, 91 pages.
- **HTML:** one interactive page plus 77 chart images.

`build_sector_report.py` implements this spec exactly. Under the rule in force until 21 November 2026 (52-week levels), running it on the reference inputs reproduced both outputs pixel for pixel and part for part (only the save timestamps of three embedded workbooks differed). Since 22 November 2026 levels come from swings (§1.2), so the same inputs give the edition under the current rule.

Notation used throughout:

- **x / y / w / h:** inches from the top-left of the slide.
- **pt:** typographic points.
- **Colours:** hexadecimal.
- **"Today":** the last date in the Bloomberg export, unless `ASOF` is set.

---

## 0. Principles (non-negotiable)

1. **Pure technical analysis.**
   - No fundamental, macro or news input enters any verdict.
   - Syz list membership (Master list / Focus List) is display only.
2. **Bloomberg is the only data source.**
   - Never fill, extrapolate or invent a value.
   - A missing input stops the run and names the input.
   - A stock with too little history gets no verdict and is named in the footnotes.
3. **Facts and the rule that fired, never interpretation prose.**
   - Every slide title is a factual statement computed from the data, e.g. "54 of 75 stocks Bullish".
4. **House style.**
   - Nunito Sans everywhere, Syz colours (§5).
   - En dash U+2013 for minus signs and ranges, with one exception: the RS Mom minus is U+2212 "−".
   - 1 decimal for prices and percentages; 2 decimals for distances in the trigger watch.
5. **Source line.**
   - Every page and chart carries `Sources : Syz Research, Bloomberg` (with the space before the colon).
   - No external research provider is ever named.
6. **Disclaimer.** The Syz legal disclaimer closes both outputs, verbatim (template layout 22 in the PowerPoint, footer in the HTML).

---

## 1. Data

### 1.1 Price export (Bloomberg)

- **Workbook:** the one written by `build_sector_report.py template`, refreshed in Excel with the Bloomberg add-in.
- **Settings sheet:**
  - B2 = start date, `2019-01-01`;
  - B3 = end date, the day the template is made.
- **Reference sheet** (row 1 = header), one row per ticker:
  - column A: ticker;
  - column B: `=BDP(A,"NAME")`;
  - column C: `=BDP(A,"GICS_SUB_INDUSTRY_NAME")`.
- **Price sheets:** one sheet per ticker (sector index, 76 stocks, benchmark `SPX Index`).
  - D1 = ticker.
  - A2 = `=BDH($D$1,"PX_LAST",Settings!$B$2,Settings!$B$3,"Days=W","Fill=B","Dates=S","CshAdjNormal=Y","CshAdjAbnormal=Y","CapChg=Y")`.
  - The result is daily closes adjusted for splits and special dividends, weekdays only, one series per sheet.
- **Reader rules:**
  - Each sheet keeps its own dates.
  - Text such as `#N/A N/A` is a Bloomberg error and is reported.
  - Duplicate dates and non-numeric values are reported; nothing is filled.

### 1.2 Universe, built at each run

The universe has one row for the sector index and one per constituent. Columns:

| Column | Sector row | Stock rows |
|---|---|---|
| ticker | `S5INFT Index` | Bloomberg ticker from `TICKERS` |
| name | from `DISPLAY_NAMES` | from `DISPLAY_NAMES` (Bloomberg NAME is never used as the display name) |
| asset_class / group | `sector` / `Sector index` | `equity` / `S&P 500 Information Technology` |
| benchmark / decimals | `SPX Index` / 1 | `SPX Index` / 1 |
| support / resistance | written as 52-week low / high; replaced at scoring by the swing levels (§2.1) | same |
| support_origin / resistance_origin | `52w …` in the file; the engine reports `swing low (YYYY-MM-DD)[, broken]` / `swing high (…)` | same |
| levels_asof | today | today |
| industry | empty | full GICS sub-industry (§1.3) |
| bucket | empty | sub-sector (§1.3) |
| syz_lists | empty | `Master list`, `Focus List`, `Master list; Focus List` or empty (§1.4) |
| badge, badge_asof, standing_position, override_reason | empty | empty (no published views in this report) |

**Levels (rule of 22 Nov 2026):** the universe file carries the 52-week low / high, but any level with a `52w` origin is recomputed by the engine as a **swing level**: support = last confirmed swing low, resistance = last confirmed swing high, a swing being confirmed when the close reverses 1.5 × the median one-month move of the past year (one-month move = daily volatility over 100 days × √20; robust threshold of 23 Nov 2026). After a lower low the broken prior swing low stays the support until the resistance breaks (and symmetrically). The 52-week low / high are used only where no swing is confirmed.

### 1.3 Sub-industry and sub-sector

- Bloomberg truncates the GICS sub-industry at 30 characters. The full name is the unique entry of this list that starts with the truncated text:

  IT Consulting & Other Services · Internet Services & Infrastructure · Application Software · Systems Software · Communications Equipment · Technology Hardware, Storage & Peripherals · Electronic Equipment & Instruments · Electronic Components · Electronic Manufacturing Services · Technology Distributors · Semiconductor Materials & Equipment · Semiconductors.

  An unknown or missing value stops the run.
- **Buckets** (one dashboard page each, in this order):
  1. **Semiconductors & equipment:** Semiconductors; Semiconductor Materials & Equipment.
  2. **Software:** Application Software; Systems Software.
  3. **Hardware & equipment:** all remaining sub-industries.
  4. **IT services & internet:** IT Consulting & Other Services; Internet Services & Infrastructure.
- **Short names** used in the dashboards:

  | Full GICS name | Dashboard name |
  |---|---|
  | Technology Hardware, Storage & Peripherals | Hardware, storage & periph. |
  | Semiconductor Materials & Equipment | Semi materials & equipment |
  | Internet Services & Infrastructure | Internet services & infra. |
  | Electronic Equipment & Instruments | Electronic equipment |
  | Electronic Manufacturing Services | Electronic manufacturing |
  | IT Consulting & Other Services | IT consulting & services |

  Other sub-industries keep their full name.

### 1.4 Syz lists (display only)

- **Source:** the Master list workbook.
  - Sheet `Master_list_F`, rows with Grouping = "North America": `Factset ID` is the US ticker (a leading `*` is stripped).
  - Sheet `Focus List`, rows with COUNTRIES = "United States": `FACTSET ID` is `TICKER-COUNTRY`; the ticker is the part before `-`.
- **Matching:**
  - Only US listings are matched (Bloomberg suffix `UW|UN|UQ|UA|UR|UP|US Equity`).
  - The ticker root must match, and the first word of the company name must agree with the list name (letters and digits only, upper case). Containment counts too.
  - A ticker match with a different name is reported and **not** tagged.
  - Hand-checked aliases live in `LIST_ALIASES` (`IBM UN Equity` → "International Business Machines").
- **Reference result:** Master list 21 (incl. TXN), Focus List 8 (incl. TXN), 28 stocks on at least one list.

---

## 2. Calculations

### 2.1 Trend verdict (one rule set, first match wins)

**Parameters:**

| Parameter | Value |
|---|---|
| MA long / short | 200 / 50 days |
| Band window | 100 days |
| Slope lookback | 20 bars |
| Flat band | ±0.20 % |
| Cross lookback | 40 bars |
| Minimum history | 320 bars |
| Levels lookback | 100 bars before levels_asof |

**Inputs:**

- **slope200:**
  - `rising` if MA200[t] / MA200[t−20] − 1 > +0.002;
  - `falling` if it is below −0.002;
  - `flat` otherwise.
- **Structure state:** set by the most recent structural event.
  - Support side, with a level: close < support, counted from levels_asof − 100 bars. Without a level: close < MIN100 (lowest of the prior 100 closes).
  - Resistance side, with a level: close > resistance. Without a level: close > MAX100.
  - Here both sides have swing levels (support / resistance of §1.2); breaks count from the earlier of the two swing points, and the levels outrank band breaks.
  - A MAX100 break resets an old support break to intact; a MIN100 break resets an old resistance break.
- **Cross:** the last golden or death cross of MA50 / MA200 within 40 bars.
- **price_vs_200:** above or below the MA200.
- **MA50 slope:** over 20 bars.

**Rules, in order:**

| Rule | Condition | Verdict |
|---|---|---|
| rising_support_intact | 200d rising, support not broken | Bullish |
| rising_support_broken_death_cross | rising, support broken, MA50 < MA200 | Bearish (lt_view "Neutral – 200d rising") |
| rising_support_broken | rising, support broken | Neutral+ |
| falling_losing_momentum | falling, support broken, price above MA200, MA50 slope > 0 | Bearish_LM |
| falling_support_broken | falling, support broken, resistance not broken | Bearish |
| falling_resistance_broken | falling, resistance broken | Neutral |
| falling_range_intact | falling, support not broken | Neutral- |
| flat_support_broken_ma50_weak | flat, support broken, (MA50 < MA200 or MA50 slope < 0) | Bearish |
| flat_negative | flat and (support broken or death cross or price below MA200) | Neutral- |
| flat_positive | flat and (resistance broken or golden cross or price above MA200) | Neutral+ |
| flat_neutral | otherwise | Neutral |

- Fewer than 320 closes → `insufficient_data`, no verdict. Reference edition: Qnity Electronics, 267 bars.
- **Display labels:** Bullish · Neutral + · Neutral · Neutral – · Bearish (LM) · Bearish. Glyphs ▲ ◆ ◆ ◆ ▼ ▼.
- **Families** used for counts and badges: Bullish = {Bullish}; Neutral = {Neutral+, Neutral, Neutral-}; Bearish = {Bearish, Bearish_LM}.

### 2.2 Momentum (closing prices, no dividends)

| Measure | Definition |
|---|---|
| vs 200d | close / MA200 − 1 |
| 1m, 3m, 12m | close / last close on or before (last date − 1, 3, 12 calendar months) − 1 |
| vs 52w high | close / max of closes over the last 52 weeks (last bar included) − 1; green when ≥ −5 % |
| 1-week change | used internally only |

### 2.3 Relative strength against the S&P 500 (informs, never changes the verdict)

| Measure | Definition |
|---|---|
| RS | close / SPX × 100, on common dates only |
| RS 3m | RS[t] / RS[t−63] − 1 |
| RS Mom | sign of MA200(RS)[t] / MA200(RS)[t−20] − 1: `+` (outperforming), `−` (underperforming), `–` if zero. Needs more than 220 RS bars. |

### 2.4 Breadth (sector chart, third panel)

- **Members:** every stock in the universe with prices. The sector index and the benchmark are excluded.
- **Date axis:** the sector index's dates up to today.
- **For each stock and date:**
  - "rising" = MA200 slope over 20 bars > +0.20 %;
  - "above" = close > MA200.
  - A stock counts only from the date both exist (220 closes), with no filling.
- **Share** = count / number of stocks measurable that date × 100.
- **Caveat:** today's constituents only, so survivorship applies. The footnote says so.

### 2.5 Trigger watch

- One row per stock: the nearest level within ±2 % of the close.
- **Candidate levels:**
  - the swing low (support) and swing high (resistance), labelled "Swing low / high";
  - the 100-day high and low (prior 100 closes), labelled "100-day high / low".
- **Distance** = close / level − 1, shown with 2 decimals.
- **Sort:** by absolute distance; keep the first row per stock.

---

## 3. PowerPoint document

- **Template:** `assets/template_syz_a4.pptx`, Syz A4 landscape, 11.69 × 8.27 in, 28 layouts. It has no slides of its own.

  | Layout index | Use |
  |---|---|
  | 1 | Cover |
  | 21 | Titled page (placeholder idx 0 = title, idx 14 = subtitle) |
  | 22 | Legal disclaimer |
  | 24 | Final page |
  | 26 | Blank |

- **Content frame:** x 0.73, width 10.28.
- **Footnote on every titled page:** at x 0.73, y 7.62, w 8.5, 7 pt, grey 8A93A6:

  `Sources : Syz Research, Bloomberg. Data to <D Month YYYY>. <note>`

- **Primitives** (python-pptx):
  - **text box:** zero margins, word-wrap.
  - **box:** rounded rectangle, corner adjustment 0.08, no line, no shadow.
  - **table:**
    - header row navy 202945, white bold;
    - body rows alternate FFFFFF / F6F7F9, navy text;
    - cell margins 0.05 / 0.01 in, vertically centred;
    - numbers right-aligned, text left-aligned.
  - **verdict cell:** fill by family (Mint 3BAF90 / Blueberry 4B5F80 / Mulberry AC5D85), white bold, centred, text `<glyph> <label>`. A stock with no verdict: fill E9ECF1, grey text "n/a – history".
- **Stock sort order** everywhere unless stated:
  1. verdict (Bullish, Neutral+, Neutral, Neutral-, Bearish_LM, Bearish);
  2. RS Mom (+, mixed, −);
  3. RS 3m, descending.

### Page by page (reference: 91 pages)

**1. Cover** (layout 1)

- **Left side:** placeholder 0 = `TITLE`; placeholder 13 = edition in capitals. All other placeholders are removed.
- **Right half:** a navy rectangle at x 5.85, y 0, 5.85 × 8.27, no rounding.
  - "N STOCKS – TREND VERDICTS": 11 pt, amber FFA400, bold, at (6.45, 2.2).
  - Three counts at y 2.85 + k × 1.15: 48 pt bold numbers at x 6.45, coloured Mint 3BAF90 / Sky 79D6FF / Peach E6A4AD.
  - Labels Bullish / Neutral / Bearish: 16 pt white, at x 8.15, y + 0.30.
  - If any stock lacks history: "N without enough history for a verdict", 10 pt grey, at (6.45, 6.35).
- **Author line:** "Florian Marini, CFA, CMT – Head of Research", 10 pt Blueberry, at (0.73, 7.45).
- **Draft mark** if `DRAFT`: "DRAFT – FOR INTERNAL REVIEW", 10 pt orange FF6C0E, bold, at (0.73, 4.75).

**2. Sector against the market** (layout 21)

- **Title:** "S&P 500 IT: <label> trend, RS Mom <+|−> against the S&P 500".
- **Subtitle:** "Sector index: absolute momentum and relative strength against the S&P 500".
- **Nine tiles** in a 3 × 3 grid:
  - x = 0.73 + col × 3.47, y = 2.55 + row × 1.6;
  - tile 3.3 × 1.38, fill F6F7F9, with a left accent bar 0.09 wide (orange for even index k, Blueberry for odd);
  - label at +0.25 / +0.14, 10 pt Blueberry;
  - value at +0.25 / +0.5, 24 pt bold, colour by sign (Mint ≥ 0, Mulberry < 0).
  - Order: Trend verdict · 200-day average · Price vs 200-day · vs 52-week high (navy) · 1-month change · 3-month change · 12-month change · RS Mom vs S&P 500 · RS 3m vs S&P 500.
- **Footnote:** last close; 52-week low and high; "Rule fired: <rule>"; the breadth-panel sentence including "survivorship applies".

**3. Sector chart** (layout 26): the full-page chart image (§4) at x 0.30, y 0.30, width 10.65, no title.

**4. Breadth**

- **Title:** "Breadth: X of N stocks Bullish, Y of N above their 200-day, Z with RS Mom +".
- **Subtitle:** "Share of stocks by sub-sector, %".
- **Four stat boxes** at x 0.73, y 2.55 + k × 1.22, size 3.2 × 1.05, fill F6F7F9:
  - big number 24 pt bold: Mint / navy / orange / Blueberry;
  - label 10 pt.
  - Contents: Bullish X/N_ok; above the 200-day Y/N; RS Mom + Z/N; within 5 % of the 52-week high W/N.
- **Native clustered column chart** at (4.18, 2.45), 6.85 × 4.95:
  - categories "<bucket> (n)";
  - series Bullish (Mint), Above 200-day (navy), RS Mom + (orange), each the % of the bucket rounded to 0 dp;
  - gap 60, overlap −10;
  - data labels 8 pt in format `0`;
  - legend at top, 9 pt;
  - value axis hidden, 0–100, no gridlines; category labels 8.5 pt.

**5. By sub-industry**

- **Title:** "By sub-industry: <top> leads on relative strength over 3 months".
- **Table**, ranked by median RS 3m, descending. Columns and widths:

  | Sub-industry | Stocks | Bullish | Above 200-day | RS Mom + | Median 3m | Median RS 3m vs S&P 500 |
  |---|---|---|---|---|---|---|
  | 3.6 | 0.9 | 0.9 | 1.2 | 1.1 | 1.1 | 1.48 |

- **Count colours:** Mint if > 50 % of the row's stocks, Mulberry if < 50 %, navy if exactly 50 %.
- **Total row:** "S&P 500 IT constituents", fill FFE9D6, bold.
- **Row height** min(0.34, 5.0 / (rows + 1)), 9.5 pt.

**6. Momentum map**

- **Title:** "Momentum map: K stocks above their 200-day and gaining on the S&P 500".
- **Image:** a matplotlib scatter, 10.28 × 5.0 in at 200 dpi, placed at (0.73, 2.4), width 10.28.
  - x = vs 200d %; y = RS 3m %.
  - Points: size 34, white edge 0.6; Mint if Bullish, Mulberry if Bearish or Bearish_LM, Blueberry otherwise.
  - Labels: ticker root, 6.2 pt navy, offset (3, 3) pt.
  - Zero lines B8BFCC, 0.8 pt.
  - Four corner labels, 8 pt bold, alpha 0.85:
    - "Above 200-day, gaining on S&P 500" (Mint, top right);
    - "Below 200-day, losing to S&P 500" (Mulberry, bottom left);
    - the other two in Blueberry.
  - Axis labels 8.5 pt navy; ticks 7.5 pt Blueberry; top and right spines hidden.

**7–10. Momentum dashboards,** one per bucket in §1.3 order

- **Title:** "<bucket>: X of n Bullish, Y with RS Mom + against the S&P 500".
- **Group labels** above the header: rounded pills, h 0.24 at y 2.2, white 9 pt bold.
  - "Absolute momentum" (navy) over columns Last … vs 52w high;
  - "vs S&P 500" (orange) over RS Mom and RS 3m;
  - "Verdict" (Blueberry) over Trend.
- **Table** at y 2.5, width 10.28. Columns and widths:

  | Stock | Syz list | Sub-industry | Last | 200-day | vs 200d | 1m | 3m | 12m | vs 52w high | RS Mom | RS 3m | Trend |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|
  | 1.60 | 0.66 | 1.62 | 0.64 | 0.60 | 0.60 | 0.56 | 0.56 | 0.60 | 0.68 | 0.55 | 0.60 | 1.01 |

- **Cell rules:**
  - **Syz list:** "★ Master" (fill FFE9D6, orange bold), "★ Focus" (fill E4E8F0, navy bold) or "★ Focus + M." (fill FFE9D6, navy bold). Not on a list: "–" in D5DAE3.
  - **Sub-industry:** short name (§1.3), Blueberry.
  - **200-day:** rising Mint, falling Mulberry, flat Blueberry.
  - **% columns:** Mint ≥ 0, Mulberry < 0.
  - **vs 52w high:** Mint if ≥ −5 %, navy otherwise.
  - **RS Mom:** + Mint, − Mulberry, bold, centred.
  - **Trend:** verdict cell.
- **Row height** min(0.30, 5.0 / (n + 1)); 8 pt if row height ≥ 0.24, else 7.5 pt.
- **Footnote:** "Sorted by trend verdict, then RS Mom, then RS 3m. Changes on closing prices, total return not included. vs 52w high in green when within 5%. Syz list: Focus List / Master list (<LISTS_ASOF>), shown for information, not part of the verdict." Add the insufficient-history note if the bucket has such a stock.

**11. Relative strength leaders and laggards**

- **Title:** "Relative strength: the 15 leaders and the 15 laggards against the S&P 500".
- **Two native bar charts,** 5.0 × 4.75, at x 0.73 and 5.93, y 2.7:
  - captions "Leaders" (Mint) and "Laggards" (Mulberry), 11 pt bold, at y 2.4;
  - bars Mint if ≥ 0, Mulberry otherwise;
  - data labels 7.5 pt in format `+0.0;–0.0`;
  - category labels 8 pt, positioned low;
  - gap 40; value axis hidden.
- **Footnote:** the median of all constituents.

**12. Trend × RS grid**

- **Title:** "N stocks are in an uptrend while their relative-strength trend points down".
- **Table:**
  - rows Bullish, Neutral+, Neutral, Neutral-, Bearish (Bearish_LM folded into Bearish);
  - columns "RS Mom + (gaining on the S&P 500)", fill E3F4EF, and "RS Mom − (losing to the S&P 500)", fill F6E8EF;
  - widths 1.45 / 4.4 / 4.43;
  - cells list names alphabetically, comma-separated, 8 pt.
- **Row height:** proportional to the wrapped lines (about 95 characters per line), unit = min(0.2, 4.65 / Σ(lines + 1)), row = unit × (lines + 1).

**13. Trigger watch**

- **Title:** "Trigger watch: N stocks within 2% of a swing level or a 100-day high or low".
- **Table:**

  | Stock | Last | Level | Value | Distance | Trend |
  |---|---|---|---|---|---|
  | 3.6 | 1.3 | 1.7 | 1.3 | 1.0 | 1.38 |

  - Distance in bold, Mint if ≥ 0, Mulberry otherwise.
  - 9.5 pt below 18 rows, 8 pt from 18 rows.

**14. Method** ("How to read the verdicts")

- Five rows at y 2.55 + k × 0.98.
- Each row: a label box 2.2 × 0.8 (orange for even k, navy for odd), white 12 pt bold; the text at x + 2.4, width 7.85, 11 pt.
- Rows: Trend · Structure · Verdict · Absolute momentum · Relative strength (wording as in the script).

**15–89. Stock charts:** one full-page chart per stock (layout 26). Order: buckets in §1.3 order, stocks in the default sort within each bucket.

**90. Legal disclaimer** (layout 22). **91. Final page** (layout 24).

- **Chart images:** each PNG chart is converted to a JPEG 1,800 px wide, quality 88, before insertion.

---

## 4. Charts (matplotlib, one per instrument)

- **Page:** 10.65 × 7.45 in, 170 dpi, white. Nunito Sans (bundled TTF), with DejaVu Sans as fallback for glyphs.
- **Margins:** left 0.55, right gap 1.40 (for value tags), top gap 1.12.
- **Window:** 5 calendar years; trading-day integer x-axis; year labels at the first bar of each year.
- **Scale:** log; linear if the window holds values ≤ 0.
- **Panels:**
  - **Stocks:** price (top) + relative strength. RS panel at y 0.50, height 1.40; price panel from y 2.30.
  - **Sector index:** price + RS + breadth. Breadth panel at y 0.62, height 1.00; RS panel at y 2.00, height 1.00; price panel from y 3.38.
- **Price panel:**

  | Element | Style |
  |---|---|
  | Close | navy 202945, 1.2 pt |
  | 50-day MA | blue 2F6FDE, 1.3 pt |
  | 200-day MA | orange FF6C0E, 2.0 pt |
  | 100-day high/low band | fill Blueberry, alpha 0.08; edges Blueberry 0.6 pt, alpha 0.45 |
  | swing low/high (52-week where no swing) | grey 8A93A6, 1.0 pt, dash (2, 3) |

  - **Tags on the right axis,** pushed apart by at least 19 pt so none hides another:
    - "swing low x" / "swing high x" (or "52w …") on E4E7EE;
    - "100d high x" / "100d low x";
    - last close on navy;
    - MA200 on orange.
  - **Legend** above the panel, 9 pt, 4 columns: Close, 50-day MA, 200-day MA, 100-day high / low band.
  - **Y grid:** B8BFCC, alpha 0.35, 0.6 pt.
- **RS panel:**
  - RS rebased to 100 at the window start, Mulberry 1.1 pt;
  - its 200-day average, grey B8BFCC 1.2 pt;
  - dotted line at 100;
  - 3 y-ticks;
  - caption "Relative strength vs S&P 500, rebased to 100 (grey: its 200-day)", 9 pt bold navy.
- **Breadth panel** (sector chart only):
  - % with a rising 200-day: Mint line 1.3 pt over a Mint fill, alpha 0.18;
  - % above the 200-day: Blueberry 0.9 pt;
  - y 0–100 % with ticks 0 / 50 / 100; dotted lines at 20 and 80; a solid line at 50;
  - the last value tagged in a Mint pill;
  - caption "% of S&P 500 IT stocks in an uptrend (green: 200-day average rising; blue: above it)".
- **Title block:**
  - name: 22 pt bold navy at 0.40 in from the top, shrinking down to 13 pt so it clears the badge and the list tags;
  - subtitle "<ticker> | daily close, log scale, 5 years": Blueberry, at 0.66 in;
  - orange accent line 0.9 in long, 3 pt, at 0.74 in.
- **Verdict badge** (top right): **only the three reference visuals** in `assets/verdict_badges_reference.pptx`:

  | Badge | Fill |
  |---|---|
  | ▲ BULLISH | Mint 3BAF90 |
  | ◆ NEUTRAL | Blueberry 4B5F80 |
  | ▼ BEARISH | Mulberry AC5D85 |

  - Shape: rounded rectangle 1.18 × 0.34 in, corner radius 23.5 % of the height, top edge 0.20 in from the top, right edge 0.05 in from the right.
  - Glyph: white 11 pt bold, centred 0.22 in from the left edge.
  - Label: white bold capitals from 0.32 in, 11 pt with 1.5 pt letter spacing. Spacing tightens (down to 0.6 pt), then size, until the label fits 0.80 in.
  - Neutral+ and Neutral- show NEUTRAL; Bearish_LM shows BEARISH.
  - No published view exists, so a caption "Rules-based reading" appears below the badge: 7.5 pt Blueberry, right-aligned.
  - No verdict (insufficient history) → no badge.
- **Syz list tags,** left of the badge (only for listed stocks):
  - one pill per list, 1.45 × 0.24 in, gap 0.04, white fill;
  - outline 1.4 pt, orange FF6C0E for the Master list, navy for the Focus List;
  - text "★  SYZ MASTER LIST" / "★  SYZ FOCUS LIST", 8.5 pt bold, in the outline colour;
  - Focus List on top; the stack is centred vertically on the badge.
- **Footer:**
  - "Sources : Syz Research, Bloomberg", 9 pt Blueberry, at 0.10 in from the bottom, left;
  - "Data to D Mon YYYY" right-aligned at the plot edge.
- **Files:** `charts_a4/<asof>/<group>/<NNN>_<ticker_with_underscores>.png`. NNN is the universe order: 001 is the sector index, then `TICKERS` order.

---

## 5. Colours and fonts

| Name | Hex | Use |
|---|---|---|
| Navy (Space Blue) | 202945 | text, table headers, cover panel, Close line |
| Blueberry | 4B5F80 | neutral, secondary text, Focus pill text |
| Mint | 3BAF90 | bullish, positive values |
| Mulberry | AC5D85 | bearish, negative values |
| Tiger Orange | FF6C0E | MA200, accents, Master list tag |
| Mango Amber | FFA400 | cover eyebrow |
| Sky | 79D6FF | cover Neutral count |
| Peach | E6A4AD | cover Bearish count |
| MA50 blue | 2F6FDE | 50-day MA only (agreed 8 Nov 2026) |
| Grey (pptx text) | 8A93A6 | footnotes |
| Grey (chart grid) | B8BFCC | grids, RS average |
| Light fills | F6F7F9 · E9ECF1 · FFE9D6 · E4E8F0 · E3F4EF · F6E8EF · D5DAE3 | tiles, n/a, list cells, grid cells |

**Fonts:**

- Charts: Nunito Sans Regular, Bold and Light, bundled TTF (SIL OFL).
- PowerPoint: text inherits the template theme.
- HTML: Nunito Sans from Google Fonts, falling back to the system sans-serif.

---

## 6. HTML version

- **Files:** one `index.html`, with all data embedded as JSON (the same table as the PowerPoint), plus `charts/<ticker_with_underscores>.jpg` (1,400 px wide, quality 84) and `syz_logo.png`.
- **Page structure:**
  1. **Navy masthead:** logo, eyebrow "Technical special report · <edition>", title, sub-line with "N on a Syz list", draft pill, verdict counts. It has a 4 px orange-to-amber gradient underline.
  2. **Sticky section nav:** Sector · Breadth · Momentum map · Dashboard · Relative strength · Trend × RS · Trigger watch · Charts · Method.
  3. **Sector:** nine tiles plus the sector chart (click to enlarge).
  4. **Breadth:** stats, an SVG grouped column chart, the sub-industry table.
  5. **Momentum map:** an SVG scatter with hover tooltip and click-to-chart; sub-sector filter chips.
  6. **Dashboard:** all stocks in one table, columns as in the PowerPoint. Sortable headers; filters for sub-sector chips, verdict, RS Mom, Syz list and free-text search. A row opens its chart.
  7. **Relative strength** leaders and laggards (HTML bars); **trend × RS grid** (name chips open charts); **trigger watch**.
  8. **Gallery** by sub-sector, with lazy thumbnails and list tags; a lightbox with ‹ › arrow keys.
  9. **Method;** source line; full legal disclaimer at 10 px.
- **Theme:** light and dark tokens. Charts always sit on white plates.
- **Layout:** works at phone width with no horizontal page scroll.

---

## 7. Validation before release

1. The script prints no `skipped` chart.
2. Every insufficient-history stock is named in the footnotes.
3. Run `validate.py --original assets/template_syz_a4.pptx` (pptx skill) on the PowerPoint → "All validations PASSED".
4. Render a PDF with LibreOffice and look at pages 2–14 for overflow.
5. Check the Syz list matches printed by the script (name mismatches are listed, not tagged).
