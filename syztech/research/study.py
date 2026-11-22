"""Side-by-side study: current trend rule (52-week levels) against the swing rule (k = 1.5 / 2 / 2.5).

python -m syztech.research.study  ->  output/rule_study/{histories.parquet|csv, metrics.json, today.csv, badges.csv}
Weekly sampling (every 5th bar) from bar 320; forward returns on closes (rates excluded: yields are not prices).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..io.bloomberg_prices import load_prices
from ..io.universe import load_universe
from ..trend.rules import evaluate
from ..trend.score import score_universe
from .swing import family, swing_history

SOURCES = ["data/prices_sectors_style", "data/prices_swiss_spi", "data/prices_spx_it", "data/prices", "data/prices_swiss"]
UNIVERSES = ["data/universe.csv", "data/universe_swiss.csv", "data/universe_swiss_spi.csv", "data/universe_spx_it.csv",
             "data/universe_sectors_style.csv"]
KS = (1.5, 2.0, 2.5)
OUT = Path("output/rule_study")


def series_pool():
    pool, cls = {}, {}
    for f in UNIVERSES:
        if Path(f).exists():
            u = pd.read_csv(f)
            for t, a in zip(u.ticker, u.asset_class):
                cls.setdefault(t, a)
    for src in SOURCES:
        if not Path(src).exists():
            continue
        p = load_prices(src)
        for t, r in p.reports.items():
            if r.bars > 0 and t not in pool:
                pool[t] = p.series(t).dropna()
    return pool, cls


def history(t: str, s: pd.Series) -> pd.DataFrame:
    n = len(s)
    idx = list(range(320, n, 5))
    if idx and idx[-1] != n - 1:
        idx.append(n - 1)
    if not idx:
        return pd.DataFrame()
    c = s.to_numpy()
    sw = {k: swing_history(s, k=k) for k in KS}
    rows = []
    for i in idx:
        d = s.index[i]
        w = s[(s.index > d - pd.Timedelta(weeks=52)) & (s.index < d)]
        v0 = evaluate(s.iloc[:i + 1], support=float(w.min()), resistance=float(w.max()), levels_asof=d).verdict if len(w) else None
        row = dict(ticker=t, date=d, i=i, v0=v0,
                   f20=c[i + 20] / c[i] - 1 if i + 20 < n else np.nan, f65=c[i + 65] / c[i] - 1 if i + 65 < n else np.nan)
        for k in KS:
            row[f"v{k}"] = sw[k].verdict.iloc[i]
        rows.append(row)
    return pd.DataFrame(rows)


def flips(h: pd.DataFrame, col: str) -> tuple[float, float]:
    """Family changes per instrument-year, and median spell length in weeks."""
    per_year, spells = [], []
    for _, g in h.groupby("ticker"):
        f = g[col].map(family).dropna()
        if len(f) < 10:
            continue
        ch = (f != f.shift()).iloc[1:]
        years = len(f) * 5 / 252
        per_year.append(ch.sum() / years)
        run = (f != f.shift()).cumsum()
        spells += list(f.groupby(run).size().iloc[1:-1])     # complete spells only
    return float(np.mean(per_year)), float(np.median(spells)) if spells else float("nan")


def fwd_table(h: pd.DataFrame, col: str, cls: dict) -> dict:
    x = h[~h.ticker.map(lambda t: cls.get(t) == "rate")].copy()
    x["fam"] = x[col].map(family)
    out = {}
    for fam in ("Bullish", "Neutral", "Bearish"):
        y = x[x.fam == fam]
        out[fam] = {"n": int(len(y)), "share": float(len(y) / max(1, x.fam.notna().sum()))}
        for hz in ("f20", "f65"):
            z = y[hz].dropna()
            out[fam][hz] = {"mean": float(z.mean()) if len(z) else None, "median": float(z.median()) if len(z) else None,
                            "hit": float((z > 0).mean()) if len(z) else None, "n": int(len(z))}
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pool, cls = series_pool()
    hs = [history(t, s) for t, s in pool.items()]
    h = pd.concat([x for x in hs if len(x)], ignore_index=True)
    h.to_csv(OUT / "histories.csv", index=False)
    cols = ["v0"] + [f"v{k}" for k in KS]
    metrics = {"series": len(pool), "samples": len(h), "first": str(h.date.min().date()), "last": str(h.date.max().date()),
               "rules": {}}
    for col in cols:
        fl, sp = flips(h, col)
        metrics["rules"][col] = {"flips_per_year": fl, "median_spell_weeks": sp, "fwd": fwd_table(h, col, cls)}
    # today: last sample per instrument
    today = h.sort_values("date").groupby("ticker").tail(1).set_index("ticker")
    today[cols].to_csv(OUT / "today.csv")
    metrics["today"] = {col: today[col].map(family).value_counts().to_dict() for col in cols}
    # published verdicts (Cross-Asset universe, 8 Nov 2026): production rule with drawn levels, and the variants
    uni, _ = load_universe("data/universe.csv")
    pub = uni[uni.badge.notna()][["ticker", "name", "badge"]]
    p = load_prices("data/prices")
    prod = score_universe(p, uni[uni.ticker.isin(pub.ticker)], "2026-11-06").set_index("ticker").verdict
    rows = []
    for r in pub.itertuples():
        if r.ticker not in pool:
            continue
        s = pool[r.ticker]
        s = s[s.index <= "2026-11-06"]
        row = dict(ticker=r.ticker, name=r.name, published=r.badge, v0_drawn=prod.get(r.ticker))
        w = s[(s.index > s.index[-1] - pd.Timedelta(weeks=52)) & (s.index < s.index[-1])]
        row["v0"] = evaluate(s, support=float(w.min()), resistance=float(w.max()), levels_asof=s.index[-1]).verdict
        for k in KS:
            row[f"v{k}"] = swing_history(s, k=k).verdict.iloc[-1]
        rows.append(row)
    b = pd.DataFrame(rows)
    b.to_csv(OUT / "badges.csv", index=False)
    metrics["badges"] = {"n": len(b)}
    for col in ["v0_drawn"] + cols:
        agree = (b[col].map(family) == b.published.map(family))
        conf = pd.crosstab(b.published.map(family), b[col].map(family)).to_dict()
        metrics["badges"][col] = {"agree": int(agree.sum()), "share": float(agree.mean()), "confusion": conf}
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=1, default=str))
    print(json.dumps({c: {k: v for k, v in m.items() if k != "fwd"} for c, m in metrics["rules"].items()}, indent=1))
    print(json.dumps({k: (v if k == "n" else {"agree": v["agree"], "share": round(v["share"], 3)}) for k, v in metrics["badges"].items()}, indent=1))


if __name__ == "__main__":
    main()
