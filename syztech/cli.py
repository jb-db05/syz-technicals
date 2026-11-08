"""syztech command line (BUILD_SPEC §6)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from .fmt import EN_DASH
from .io.bloomberg_prices import load_prices
from .io.universe import COLUMNS, draft, guess_asset_class, load_universe
from .trend.rules import INSUFFICIENT
from .trend.score import score_universe

OUT = Path("output")


def _d(x):
    return x.strftime("%Y-%m-%d") if x is not None and pd.notna(x) else EN_DASH


def cmd_inspect(a) -> int:
    res = load_prices(a.prices)
    print(f"Price export: {a.prices}")
    for n in res.file_notes:
        print(f"  note: {n}")
    if not res.reports:
        print("No price series found.")
        return 1
    print(f"\n{'ticker':24} {'first':10} {'last':10} {'bars':>6}  issues")
    for t, r in res.reports.items():
        print(f"{t:24} {_d(r.first):10} {_d(r.last):10} {r.bars:>6}  {'; '.join(r.issues) or 'none'}")
    OUT.mkdir(exist_ok=True)
    pd.DataFrame([{k: v for k, v in vars(r).items() if k != "issues"} | {"issues": "; ".join(r.issues)}
                  for r in res.reports.values()]).to_csv(OUT / "inspect.csv", index=False)
    print(f"\nwritten: {OUT / 'inspect.csv'}")
    return 0


def cmd_universe_draft(a) -> int:
    res = load_prices(a.prices)
    out = Path(a.out)
    if out.exists() and not a.force:
        print(f"{out} exists – not overwritten (use --force).")
        return 1
    df = draft(res.tickers, {t: r.name for t, r in res.reports.items()})
    df.to_csv(out, index=False)
    print(f"written: {out} ({len(df)} tickers)")
    for t in res.tickers:
        note = guess_asset_class(t)[1]
        if note:
            print(f"  {t}: {note}")
    return 0


def cmd_trend(a) -> int:
    prices = load_prices(a.prices)
    uni, problems = load_universe(a.universe)
    for p in problems:
        print(f"universe: {p}")
    asof = a.asof or (prices.prices.date.max().date() if len(prices.prices) else None)
    df = score_universe(prices, uni, asof)
    OUT.mkdir(exist_ok=True)
    path = OUT / f"trend_scores_{asof}.csv"
    df.to_csv(path, index=False)
    counts = df.verdict.value_counts()
    print(f"Trend scores as of {asof}: {len(df)} instruments")
    for v, c in counts.items():
        print(f"  {v:18} {c}")
    print(f"written: {path}")
    print("exceptions report (§3.4): not built yet – next session.")
    bad = df[df.verdict == INSUFFICIENT]
    for _, r in bad.iterrows():
        print(f"  insufficient_data – {r.ticker}: {r.missing}")
    return 1 if len(bad) and not a.allow_partial else 0


def cmd_later(phase):
    def f(a):
        print(f"Not started: {phase} begins only after Phase 1 is done (BUILD_SPEC §7).")
        return 1
    return f


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="syztech")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("inspect", help="tickers, first/last date, bar count, export defects")
    s.add_argument("--prices", default="data/prices")
    s.set_defaults(func=cmd_inspect)
    s = sub.add_parser("universe-draft", help="draft data/universe.csv from the tickers in the export")
    s.add_argument("--prices", default="data/prices")
    s.add_argument("--out", default="data/universe.csv")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_universe_draft)
    s = sub.add_parser("trend", help="mechanical trend verdicts for the universe")
    s.add_argument("--prices", default="data/prices")
    s.add_argument("--universe", default="data/universe.csv")
    s.add_argument("--asof")
    s.add_argument("--charts", action="store_true")
    s.add_argument("--allow-partial", action="store_true")
    s.set_defaults(func=cmd_trend)
    s = sub.add_parser("ledger"); s.add_argument("--editions"); s.add_argument("--prices")
    s.set_defaults(func=cmd_later("Phase 2 (ledger)"))
    s = sub.add_parser("regime"); s.add_argument("--breadth"); s.add_argument("--prices"); s.add_argument("--backtest", action="store_true")
    s.set_defaults(func=cmd_later("Phase 3 (regime)"))
    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
