"""Relative-strength study: the trend rule in force applied to the RS line (price ÷ benchmark) against RS Mom.

python -m syztech.research.study_rs -> output/rule_study/rs_histories.csv, rs_metrics.json
Weekly samples from bar 320 of each RS line. RS Mom: sign of the 20-day change of the 200-day average of RS.
New: resolve_levels + evaluate on the RS line (swing levels k = 1.5 robust, variant B) -> Outperform / Neutral / Underperform.
Forward relative return: RS[t+h] / RS[t] − 1 for h = 20 and 65 bars.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..indicators.rs import relative_strength
from ..io.bloomberg_prices import load_prices
from ..trend.rules import evaluate
from ..trend.score import resolve_levels

OUT = Path("output/rule_study")
SETS = [("S&P 500 IT", "data/prices_spx_it", "data/universe_spx_it.csv"),
        ("Swiss", "data/prices_swiss_spi", "data/universe_swiss_spi.csv"),
        ("Sectors & style", "data/prices_sectors_style", "data/universe_sectors_style.csv"),
        ("Cross-asset", "data/prices", "data/universe.csv")]
FAM = {"Bullish": "Outperform", "Bearish": "Underperform", "Bearish_LM": "Underperform",
       "Neutral+": "Neutral", "Neutral": "Neutral", "Neutral-": "Neutral"}


def pairs():
    seen, out = set(), []
    for label, px, un in SETS:
        p = load_prices(px)
        u = pd.read_csv(un)
        for t, b, n in zip(u.ticker, u.benchmark, u.name):
            if not isinstance(b, str) or t not in p.reports or b not in p.reports or (t, b) in seen:
                continue
            if p.reports[t].bars == 0 or p.reports[b].bars == 0:
                continue
            seen.add((t, b))
            out.append((label, t, b, str(n).replace(" (ticker to confirm)", ""), relative_strength(p.series(t), p.series(b))))
    return out


def history(label, t, b, name, rs: pd.Series) -> pd.DataFrame:
    rs = rs.dropna()
    n = len(rs)
    idx = list(range(320, n, 5))
    if idx and idx[-1] != n - 1:
        idx.append(n - 1)
    if not idx:
        return pd.DataFrame()
    c = rs.to_numpy()
    ma = rs.rolling(200).mean().to_numpy()
    rows = []
    for i in idx:
        s = rs.iloc[:i + 1]
        sup, res, so, ro, ss, rs_ = resolve_levels(s, None, None, None, None)
        v = evaluate(s, support=sup, resistance=res, support_start=ss, resistance_start=rs_)
        slope = ma[i] / ma[i - 20] - 1
        rows.append(dict(set=label, ticker=t, bench=b, name=name, date=rs.index[i], i=i,
                         rsmom="+" if slope > 0 else "−" if slope < 0 else "0", verdict=v.verdict, rule=v.rule,
                         f20=c[i + 20] / c[i] - 1 if i + 20 < n else np.nan, f65=c[i + 65] / c[i] - 1 if i + 65 < n else np.nan))
    return pd.DataFrame(rows)


def flips(h, col):
    per = []
    for _, g in h.groupby(["ticker", "bench"]):
        f = g[col]
        if len(f) < 10:
            continue
        per.append((f != f.shift()).iloc[1:].sum() / (len(f) * 5 / 252))
    return float(np.mean(per))


def fwd(h, col):
    out = {}
    for k, g in h.groupby(col):
        out[k] = {"share": float(len(g) / len(h))}
        for hz in ("f20", "f65"):
            z = g[hz].dropna()
            out[k][hz] = {"mean": float(z.mean()), "median": float(z.median()), "hit": float((z > 0).mean()), "n": int(len(z))}
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    hs = [history(*p) for p in pairs()]
    h = pd.concat([x for x in hs if len(x)], ignore_index=True)
    h["state"] = h.verdict.map(FAM)
    h.to_csv(OUT / "rs_histories.csv", index=False)
    m = {"pairs": int(h.groupby(["ticker", "bench"]).ngroups), "samples": int(len(h)),
         "first": str(h.date.min().date()), "last": str(h.date.max().date()),
         "rsmom": {"flips_per_year": flips(h, "rsmom"), "fwd": fwd(h[h.rsmom != "0"], "rsmom")},
         "rule": {"flips_per_year": flips(h, "state"), "fwd": fwd(h, "state")},
         "cross": pd.crosstab(h.rsmom, h.state, normalize="all").round(4).to_dict(),
         "by_set": {}}
    today = h.sort_values("date").groupby(["ticker", "bench"]).tail(1)
    m["today"] = {"rsmom": today.rsmom.value_counts().to_dict(), "rule": today.state.value_counts().to_dict(),
                  "cross": pd.crosstab(today.rsmom, today.state).to_dict()}
    for lab, g in h.groupby("set"):
        m["by_set"][lab] = {"pairs": int(g.groupby(["ticker", "bench"]).ngroups), "rsmom": fwd(g[g.rsmom != "0"], "rsmom"), "rule": fwd(g, "state")}
    (OUT / "rs_metrics.json").write_text(json.dumps(m, indent=1, default=str))
    today.to_csv(OUT / "rs_today.csv", index=False)
    print(json.dumps({k: m[k] for k in ("pairs", "samples", "first", "last")}))
    for k in ("rsmom", "rule"):
        print(k, "flips/yr", round(m[k]["flips_per_year"], 2),
              {s: (f"{v['share']:.0%}", f"4w {v['f20']['mean'] * 100:+.2f}% hit {v['f20']['hit']:.0%}",
                   f"13w {v['f65']['mean'] * 100:+.2f}% hit {v['f65']['hit']:.0%}") for s, v in m[k]["fwd"].items()})
    print("today", m["today"])


if __name__ == "__main__":
    main()
