"""Variant d: current verdict table; support / resistance from confirmed swings, with the doctrine that a broken level
stands: after a lower low the broken prior swing low stays the support (its break counts) until the resistance breaks;
after a higher high the broken prior swing high stays the resistance. Otherwise the last swing low / high."""
from __future__ import annotations

import json
from dataclasses import replace

import pandas as pd

from ..io.universe import load_universe
from ..trend.rules import DEFAULT_PARAMS, evaluate
from .study import OUT, fwd_table, flips, series_pool
from .swing import family, swing_history

P0 = replace(DEFAULT_PARAMS, levels_lookback=0)
VK = (1.5, 2.0)


def levels(r):
    sup, sb = r.swing_low, r.swing_low_bar
    res, rb = r.swing_high, r.swing_high_bar
    if pd.notna(r.prev_low) and r.swing_low < r.prev_low:        # lower low: the prior swing low was broken
        sup, sb = r.prev_low, r.prev_low_bar
    if pd.notna(r.prev_high) and r.swing_high > r.prev_high:     # higher high: the prior swing high was broken
        res, rb = r.prev_high, r.prev_high_bar
    return sup, res, int(min(sb, rb))


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
        col = f"d{k}"
        vals = []
        for t, g in h.groupby("ticker", sort=False):
            s = pool[t]
            sw = swing_history(s, k=k)
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
            vs.append(verdict_at(s, swing_history(s, k=k), len(s) - 1))
        b[col] = vs
        agree = b[col].map(family) == b.published.map(family)
        m["badges"][col] = {"agree": int(agree.sum()), "share": float(agree.mean()),
                            "confusion": pd.crosstab(b.published.map(family), b[col].map(family)).to_dict()}
        print(col, "flips/yr", round(fl, 2), "spell", sp, "badges", int(agree.sum()), "/", len(b))
        print(pd.crosstab(b.published.map(family), b[col].map(family)).to_string())
    h.to_csv(OUT / "histories.csv", index=False)
    b.to_csv(OUT / "badges.csv", index=False)
    (OUT / "metrics.json").write_text(json.dumps(m, indent=1, default=str))


if __name__ == "__main__":
    main()
