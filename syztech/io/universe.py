"""Instrument master `data/universe.csv` (BUILD_SPEC §2.2)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

COLUMNS = ["ticker", "name", "asset_class", "group", "benchmark", "decimals", "support", "resistance",
           "levels_asof", "badge", "badge_asof", "standing_position", "override_reason"]
# Optional: where each level came from (text / chart / 52w low|high) – shown in the exceptions report
OPTIONAL_COLUMNS = ["support_origin", "resistance_origin"]
ASSET_CLASSES = {"equity", "index", "sector", "fx", "rate", "commodity", "crypto"}
BADGES = {"Bullish", "Neutral+", "Neutral", "Neutral-", "Bearish", "Bearish_LM"}
CRYPTO_PREFIXES = ("XBT", "XET", "ETH", "BTC", "SOL", "XRP")
METAL_PREFIXES = ("XAU", "XAG", "XPT", "XPD")
RATE_PREFIXES = ("USGG", "GDBR", "GTDEM", "GUKG", "GJGB", "GSWISS", "GTII", "GT", "GBTPGR", "GFRN", "GSPG")


def guess_asset_class(ticker: str) -> tuple[str, str]:
    """(asset_class, note). A first guess from the Bloomberg yellow key – the analyst confirms it."""
    t = ticker.strip()
    key = t.split()[-1].lower() if " " in t else ""
    root = t.split()[0].upper()
    if key == "equity":
        return "equity", ""
    if key == "comdty":
        return "commodity", ""
    if key == "govt":
        return "rate", ""
    if key == "curncy":
        if root.startswith(METAL_PREFIXES):
            return "commodity", ""
        if root.startswith(CRYPTO_PREFIXES):
            return "crypto", ""
        return "fx", ""
    if key == "index":
        if root.startswith(RATE_PREFIXES):
            return "rate", "check: guessed rate from ticker root"
        return "index", "check: Index key – may be sector, rate or FX index"
    return "", "check: yellow key not recognised"


DEFAULT_DECIMALS = {"equity": 1, "index": 1, "sector": 1, "commodity": 1, "crypto": 1, "fx": 2, "rate": 2}


def draft(tickers: list[str], names: dict[str, str | None] | None = None) -> pd.DataFrame:
    rows = []
    for t in tickers:
        ac, _ = guess_asset_class(t)
        rows.append({"ticker": t, "name": (names or {}).get(t) or "", "asset_class": ac,
                     "decimals": DEFAULT_DECIMALS.get(ac, "")})
    return pd.DataFrame(rows, columns=COLUMNS).astype(object)


def load_universe(path: str | Path) -> tuple[pd.DataFrame, list[str]]:
    """Read and validate. Returns (frame, problems). Problems are reported, never auto-fixed."""
    df = pd.read_csv(path, dtype={"ticker": str, "name": str, "group": str, "benchmark": str,
                                  "badge": str, "standing_position": str, "override_reason": str})
    problems = []
    missing_cols = [c for c in COLUMNS if c not in df.columns]
    if missing_cols:
        problems.append(f"missing columns: {', '.join(missing_cols)}")
        for c in missing_cols:
            df[c] = pd.NA
    for c in ("support", "resistance"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["decimals"] = pd.to_numeric(df["decimals"], errors="coerce").astype("Int64")
    for c in ("levels_asof", "badge_asof"):
        df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=False)
    for _, r in df.iterrows():
        if pd.notna(r.asset_class) and r.asset_class not in ASSET_CLASSES:
            problems.append(f"{r.ticker}: asset_class '{r.asset_class}' not in {sorted(ASSET_CLASSES)}")
        if pd.notna(r.badge) and r.badge not in BADGES:
            problems.append(f"{r.ticker}: badge '{r.badge}' not in {sorted(BADGES)}")
        if pd.notna(r.decimals) and int(r.decimals) not in (1, 2, 4):
            problems.append(f"{r.ticker}: decimals {r.decimals} not in 1/2/4")
        if pd.notna(r.support) and pd.notna(r.resistance) and r.support >= r.resistance:
            problems.append(f"{r.ticker}: support {r.support} >= resistance {r.resistance}")
    if df.ticker.duplicated().any():
        problems.append(f"duplicate tickers: {', '.join(df.ticker[df.ticker.duplicated()])}")
    return df, problems
