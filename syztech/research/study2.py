"""Variant: the current verdict table with the last confirmed swing low / high (k × one-month move) as support /
resistance instead of the 52-week low / high. Breaks count from the earlier of the two swing points."""
from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pandas as pd

from ..io.universe import load_universe
from ..trend.rules import DEFAULT_PARAMS, evaluate
from .study import KS, OUT, fwd_table, flips, series_pool
from .swing import family, swing_history

P0 = replace(DEFAULT_PARAMS, levels_lookback=0)
VK = (1.5, 2.0)


def verdict_at(s, sw, i):
    r = sw.iloc[i]
    if pd.isna(r.swing_low) or pd.isna(r.swing_high):
        w = s.iloc[max(0, i - 252):i]                      # no confirmed swing yet: fall back to 52 weeks
        return evaluate(s.iloc[:i + 1], support=float(w.min()), resistance=float(w.max()), levels_asof=s.index[i]).verdict
    start = int(min(r.swing_low_bar, r.swing_high_bar))
    return evaluate(s.iloc[:i + 1], P0, support=float(r.swing_low), resistance=float(r.swing_high), levels_asof=s.index[start]).verdict


def main():
    pool, cls = series_pool()
    h = pd.read_csv(OUT / "histories.csv", parse_dates=["date"])
    for k in VK:
        col = f"s{k}"
        vals = []
        for t, g in h.groupby("ticker", sort=False):
            s = pool[t]
            sw = swing_history(s, k=k)
            vals.append(pd.Series([verdict_at(s, sw, int(i)) for i in g.i], index=g.index))
        h[col] = pd.concat(vals)
    h.to_csv(OUT / "histories.csv", index=False)
    m = json.loads((OUT / "metrics.json").read_text())
    today = h.sort_values("date").groupby("ticker").tail(1)
    b = pd.read_csv(OUT / "badges.csv")
    uni, _ = load_universe("data/universe.csv")
    for k in VK:
        col = f"s{k}"
        fl, sp = flips(h, col)
        m["rules"][col] = {"flips_per_year": fl, "median_spell_weeks": sp, "fwd": fwd_table(h, col, cls)}
        m["today"][col] = today[col].map(family).value_counts().to_dict()
        vs = []
        for r in b.itertuples():
            s = pool[r.ticker]
            s = s[s.index <= "2026-11-06"]
            vs.append(verdict_at(s, swing_history(s, k=k), len(s) - 1))
        b[col] = vs
        agree = b[col].map(family) == b.published.map(family)
        m["badges"][col] = {"agree": int(agree.sum()), "share": float(agree.mean()),
                            "confusion": pd.crosstab(b.published.map(family), b[col].map(family)).to_dict()}
        print(col, "flips/yr", round(fl, 2), "spell", sp, "badges", int(agree.sum()), "/", len(b))
        print(pd.crosstab(b.published.map(family), b[col].map(family)).to_string())
    b.to_csv(OUT / "badges.csv", index=False)
    (OUT / "metrics.json").write_text(json.dumps(m, indent=1, default=str))


if __name__ == "__main__":
    main()
