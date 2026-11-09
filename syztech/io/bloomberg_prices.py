"""Bloomberg price exports (BUILD_SPEC §2.1) → one long table `date, ticker, close`.

Accepted shapes:
  * wide – a `Date` (or `Dates`) column, one column per ticker, header = Bloomberg ticker;
  * one sheet per ticker – sheet name = ticker, columns include `Date` and `PX_LAST` / `Last Price`.

Rules: drop non-trading rows (NaN / non-numeric close); de-duplicate dates keeping the last;
never forward-fill; ascending dates. Every defect found is recorded, nothing is repaired silently.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

PRICE_HEADERS = {"px_last", "last price", "last_price"}
DATE_HEADERS = {"date", "dates"}
# Sheets that must never be read as prices (§2.1 known defects)
FORBIDDEN_SHEETS = {"momentum equities, forex, commo"}
# Housekeeping sheets of the price template – skipped silently
NON_PRICE_SHEETS = {"instructions", "settings", "readme"}
HEADER_SCAN_ROWS = 20


@dataclass
class SeriesReport:
    ticker: str
    source: str                      # file › sheet
    name: str | None = None
    raw_rows: int = 0
    non_numeric: int = 0             # e.g. "#N/A N/A"
    nan_rows: int = 0
    duplicate_dates: int = 0
    unsorted: bool = False
    weekend_dates: int = 0
    first: pd.Timestamp | None = None
    last: pd.Timestamp | None = None
    bars: int = 0
    gaps_over_5d: int = 0
    largest_gap_days: int = 0
    largest_gap_end: pd.Timestamp | None = None
    rounded_to_units: bool = False
    longest_flat_run: int = 0        # identical consecutive closes – a sign of filled holidays
    issues: list[str] = field(default_factory=list)


@dataclass
class LoadResult:
    prices: pd.DataFrame                       # long: date, ticker, close
    reports: dict[str, SeriesReport]
    file_notes: list[str]

    def series(self, ticker: str) -> pd.Series:
        d = self.prices[self.prices.ticker == ticker]
        return pd.Series(d.close.to_numpy(), index=pd.DatetimeIndex(d.date), name=ticker)

    @property
    def tickers(self) -> list[str]:
        return list(self.reports)


def _find_header(raw: pd.DataFrame) -> int | None:
    for i in range(min(HEADER_SCAN_ROWS, len(raw))):
        cells = [str(v).strip().lower() for v in raw.iloc[i].tolist()]
        if any(c in DATE_HEADERS for c in cells):
            return i
    return None


def _clean(ticker: str, source: str, dates: pd.Series, values: pd.Series, name: str | None) -> tuple[pd.DataFrame, SeriesReport]:
    rep = SeriesReport(ticker=ticker, source=source, name=name)
    errors = {str(v).strip() for v in pd.concat([dates, values]) if isinstance(v, str) and v.strip().startswith("#N/A")}
    errors.discard("#N/A N/A")
    d = pd.to_datetime(dates, errors="coerce")
    keep = d.notna()
    d, values = d[keep], values[keep]
    rep.raw_rows = int(len(d))
    num = pd.to_numeric(values, errors="coerce")
    rep.non_numeric = int((num.isna() & values.notna() & (values.astype(str).str.strip() != "")).sum())
    rep.nan_rows = int(num.isna().sum())
    df = pd.DataFrame({"date": d.to_numpy(), "close": num.to_numpy()}).dropna(subset=["close"])
    rep.unsorted = not df.date.is_monotonic_increasing
    rep.duplicate_dates = int(df.date.duplicated().sum())
    df = df.sort_values("date", kind="stable").drop_duplicates("date", keep="last").reset_index(drop=True)
    rep.weekend_dates = int((df.date.dt.dayofweek >= 5).sum())
    rep.bars = len(df)
    if rep.bars:
        rep.first, rep.last = df.date.iloc[0], df.date.iloc[-1]
        gaps = df.date.diff().dt.days
        big = gaps[gaps > 5]
        rep.gaps_over_5d = int(len(big))
        if len(big):
            j = int(gaps.idxmax())
            rep.largest_gap_days = int(gaps.max())
            rep.largest_gap_end = df.date.iloc[j]
        v = df.close.to_numpy()
        rep.rounded_to_units = bool(rep.bars >= 20 and np.all(np.isclose(v, np.round(v))) and np.median(np.abs(v)) < 1e5)
        runs = (df.close != df.close.shift()).cumsum()
        rep.longest_flat_run = int(df.groupby(runs).size().max())
    # human-readable issues
    for e in sorted(errors): rep.issues.append(f"Bloomberg error: {e}")
    if rep.non_numeric: rep.issues.append(f"{rep.non_numeric} non-numeric cells (dropped)")
    if rep.duplicate_dates: rep.issues.append(f"{rep.duplicate_dates} duplicate dates (kept last)")
    if rep.unsorted: rep.issues.append("dates not in ascending order (sorted)")
    if rep.weekend_dates: rep.issues.append(f"{rep.weekend_dates} weekend dates")
    if rep.gaps_over_5d:
        rep.issues.append(f"{rep.gaps_over_5d} gaps > 5 calendar days (largest {rep.largest_gap_days}d to {rep.largest_gap_end:%Y-%m-%d})")
    if rep.rounded_to_units: rep.issues.append("all closes are whole numbers – export looks rounded")
    if rep.longest_flat_run >= 5: rep.issues.append(f"{rep.longest_flat_run} identical closes in a row – possible filled holidays")
    if 0 < rep.bars < 320: rep.issues.append(f"only {rep.bars} bars (< 320 needed for a verdict)")
    df.insert(1, "ticker", ticker)
    return df, rep


def _read_sheet(raw: pd.DataFrame, sheet: str, source: str):
    """Yield (ticker, dates, values, name, note) for one sheet; or raise ValueError with the reason."""
    h = _find_header(raw)
    if h is None:
        raise ValueError("no 'Date' header in the first rows")
    header = [str(v).strip() if pd.notna(v) else "" for v in raw.iloc[h].tolist()]
    low = [c.lower() for c in header]
    date_cols = [i for i, c in enumerate(low) if c in DATE_HEADERS]
    body = raw.iloc[h + 1:].reset_index(drop=True)
    price_cols = [i for i, c in enumerate(low) if c in PRICE_HEADERS]
    if price_cols:                                         # one sheet per ticker
        # template sheets carry the BDH ticker next to a 'Ticker' header; it must match the tab name
        if "ticker" in low:
            k = low.index("ticker")
            formula_ticker = header[k + 1] if k + 1 < len(header) else ""
            if formula_ticker and formula_ticker != sheet.strip():
                # the data comes from the formula's ticker: key the series on it and say so
                yield formula_ticker, body.iloc[:, date_cols[0]], body.iloc[:, price_cols[0]], \
                    None, f"tab named '{sheet.strip()}' but the formula pulls '{formula_ticker}' – loaded as {formula_ticker}"
                return
        yield sheet.strip(), body.iloc[:, date_cols[0]], body.iloc[:, price_cols[0]], None, None
        return
    if len(date_cols) > 1:
        raise ValueError(f"{len(date_cols)} 'Date' columns – paired-column layout is not a supported shape")
    dc = date_cols[0]
    # optional text rows between header and data (e.g. security names)
    dates = pd.to_datetime(body.iloc[:, dc], errors="coerce")
    first_data = int(dates.notna().idxmax()) if dates.notna().any() else len(body)
    for i, t in enumerate(header):
        if i == dc or not t:
            continue
        name = None
        for r in range(first_data):
            v = body.iat[r, i]
            if isinstance(v, str) and v.strip():
                name = v.strip()
        yield t, body.iloc[:, dc], body.iloc[:, i], name, None


def load_prices(path: str | Path) -> LoadResult:
    """One export folder/file, or several separated by commas (first one wins on duplicate tickers)."""
    if isinstance(path, str) and "," in path:
        parts = [load_prices(p.strip()) for p in path.split(",") if p.strip()]
        reports, notes, frames = {}, [], []
        for r in parts:
            notes += r.file_notes
            for t, rep in r.reports.items():
                if t not in reports:
                    reports[t] = rep
                    frames.append(r.prices[r.prices.ticker == t])
        prices = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["date", "ticker", "close"])
        return LoadResult(prices, reports, notes)
    path = Path(path)
    files = sorted(p for p in ([path] if path.is_file() else path.glob("*.xls*")) if not p.name.startswith("~$"))
    frames, reports, notes = [], {}, []
    if not files:
        notes.append(f"no Excel files found in {path}")
    for f in files:
        try:
            book = pd.read_excel(f, sheet_name=None, header=None, keep_default_na=False, na_values=[""])
        except Exception as e:                               # unreadable file: report, do not guess
            notes.append(f"{f.name}: cannot be read ({e})")
            continue
        for sheet, raw in book.items():
            if sheet.strip().lower() in FORBIDDEN_SHEETS:
                notes.append(f"{f.name} › {sheet}: skipped – helper sheet holds 200-day MAs, not prices")
                continue
            if sheet.strip().lower() in NON_PRICE_SHEETS or raw.dropna(how="all").empty:
                continue
            source = f"{f.name} › {sheet}"
            try:
                for ticker, dates, values, name, note in _read_sheet(raw, sheet, source):
                    if note:
                        notes.append(f"{source}: {note}")
                    if ticker in reports:
                        notes.append(f"{source}: {ticker} already loaded from {reports[ticker].source} – second copy ignored")
                        continue
                    df, rep = _clean(ticker, source, dates, values, name)
                    frames.append(df)
                    reports[ticker] = rep
            except ValueError as e:
                notes.append(f"{source}: not read – {e}")
    prices = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["date", "ticker", "close"])
    return LoadResult(prices, reports, notes)
