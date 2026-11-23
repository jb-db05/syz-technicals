"""Variant r: as the adopted rule (study3 'd'), but the swing threshold uses the median one-month move over the past
year (robust to parabolic runs and crashes). k = 1.5 and 1.0."""
from __future__ import annotations

import json

import pandas as pd

from .study import OUT, fwd_table, flips, series_pool
from .study3 import levels
from .study3 import P0
from ..trend.rules import evaluate
from .swing import family, swing_history

VK = (1.5, 1.0)


def verdict_at(s, sw, i):
    r = sw.iloc[i]
    if pd.isna(r.swing_low) or pd.isna(r.swing_high):
        w = s.iloc[max(0, i - 252):i]
        return evaluate(s.iloc[:i + 1], support=float(w.min()), resistance=float(w.max()), levels_asof=s.index[i]).verdict
    sup, res, start = levels(r)
    return evaluate(s.iloc[:i + 1], P0, support=float(sup), resistance=float(res), levels_asof=s.index[start]).verdict


def main():
    pool, cls = series_pool()
    h = pd.read_csv(OUT / "histories.csv", parse_dates=["date"])
    m = json.loads((OUT / "metrics.json").read_text())
    b = pd.read_csv(OUT / "badges.csv")
    for k in VK:
        col = f"r{k}"
        vals = []
        for t, g in h.groupby("ticker", sort=False):
            s = pool[t]
            sw = swing_history(s, k=k, robust=True)
            vals.append(pd.Series([verdict_at(s, sw, int(i)) for i in g.i], index=g.index))
        h[col] = pd.concat(vals)
        fl, sp = flips(h, col)
        m["rules"][col] = {"flips_per_year": fl, "median_spell_weeks": sp, "fwd": fwd_table(h, col, cls)}
        today = h.sort_values("date").groupby("ticker").tail(1)
        m["today"][col] = today[col].map(family).value_counts().to_dict()
        vs = []
        for r in b.itertuples():
            s = pool[r.ticker]
            s = s[s.index <= "2026-11-06"]
            vs.append(verdict_at(s, swing_history(s, k=k, robust=True), len(s) - 1))
        b[col] = vs
        agree = b[col].map(family) == b.published.map(family)
        m["badges"][col] = {"agree": int(agree.sum()), "share": float(agree.mean()),
                            "confusion": pd.crosstab(b.published.map(family), b[col].map(family)).to_dict()}
        print(col, "flips/yr", round(fl, 2), "spell", sp, "badges", int(agree.sum()), "/", len(b), flush=True)
        print(pd.crosstab(b.published.map(family), b[col].map(family)).to_string(), flush=True)
    h.to_csv(OUT / "histories.csv", index=False)
    b.to_csv(OUT / "badges.csv", index=False)
    (OUT / "metrics.json").write_text(json.dumps(m, indent=1, default=str))


if __name__ == "__main__":
    main()
