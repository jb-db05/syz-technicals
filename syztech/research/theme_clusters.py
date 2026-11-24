"""Thematic review, step 1 – which themes carry the same risk (research; not part of any verdict).

python -m syztech.research.theme_clusters -> output/thematics/clusters.csv, exposures.csv, residual_corr.csv

Weekly log returns (Friday closes, no filling: a week counts only where both Fridays have a close), three years to the
last complete week. For each theme: beta to the MSCI ACWI, then the residual (return − alpha − beta × ACWI). Themes are
grouped on the correlation of those residuals (average-linkage hierarchical clustering, distance = 1 − correlation), so
the common equity-market move does not glue everything together. Exposures: correlation of each residual with
price-based factors (US 10-year yield change, dollar, Brent, copper, gold, growth − value, small − large, Nasdaq − S&P,
semis − S&P, high-yield spread change, VIX change).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from ..io.bloomberg_prices import load_prices, load_reference

OUT = Path("output/thematics")
BENCH = "MXWD Index"
WEEKS, MIN_WEEKS = 156, 60
CUT = 0.55                     # clusters = groups whose average residual correlation is above 1 − CUT


def average_linkage(D: np.ndarray, cut: float):
    """Agglomerative clustering, average linkage (numpy only). Merges the two closest groups until the closest pair
    is further apart than `cut`. Returns (labels 1..k, leaf order) – the order keeps merged groups side by side and
    goes on merging past the cut so that neighbouring clusters are the most alike."""
    n = len(D)
    groups = {i: [i] for i in range(n)}
    dist = {i: D[i].copy() for i in range(n)}          # dist[g][h] = average distance between group g and group h (by id)
    M = D.astype(float).copy()
    np.fill_diagonal(M, np.inf)
    alive = np.ones(n, bool)
    size = np.ones(n)
    labels = None
    while alive.sum() > 1:
        sub = np.where(alive)[0]
        blk = M[np.ix_(sub, sub)]
        k = int(np.argmin(blk))
        a, b = sub[k // len(sub)], sub[k % len(sub)]
        if labels is None and blk.flat[k] > cut:
            labels = np.zeros(n, int)
            for c, g in enumerate(sub, start=1):
                labels[groups[g]] = c
        new = (M[a] * size[a] + M[b] * size[b]) / (size[a] + size[b])
        M[a], M[:, a] = new, new
        M[a, a] = np.inf
        alive[b] = False
        M[b], M[:, b] = np.inf, np.inf
        size[a] += size[b]
        groups[a] = groups[a] + groups.pop(b)
    if labels is None:
        labels = np.ones(n, int)
    return labels, groups[int(np.where(alive)[0][0])]


def weekly(prices, tickers) -> pd.DataFrame:
    """Friday-to-Friday log returns; a Friday without a close stays empty (no carrying forward)."""
    cols = {}
    for t in tickers:
        s = prices.series(t).dropna()
        s = s[s > 0] if (s > 0).all() else s
        f = s[s.index.dayofweek == 4]
        cols[t] = f
    px = pd.DataFrame(cols).sort_index()
    return px


def run(prices_dir="data/prices_thematics", universe="data/universe_thematics.csv"):
    p = load_prices(prices_dir)
    u = pd.read_csv(universe)
    ref = load_reference(prices_dir).set_index("ticker")
    themes = [t for t in u[u.group == "Themes"].ticker if t in p.reports]
    fac = [t for t in u[u.group == "Factors"].ticker if t in p.reports]
    px = weekly(p, themes + fac + ["XAU BGN Curncy"])
    px = px[px[BENCH].notna()].iloc[-(WEEKS + 1):]
    lr = np.log(px).diff().iloc[1:]
    for t in ("USGG10YR Index", "USGG2YR Index", "LF98OAS Index"):          # yields and spreads: change in points
        lr[t] = px[t].diff().iloc[1:]
    m = lr[BENCH]
    rows, resid = [], {}
    for t in themes:
        r = lr[t]
        ok = r.notna() & m.notna()
        if ok.sum() < MIN_WEEKS:
            rows.append(dict(ticker=t, weeks=int(ok.sum()), note="history too short for the clustering"))
            continue
        b = np.cov(r[ok], m[ok])[0, 1] / m[ok].var()
        a = r[ok].mean() - b * m[ok].mean()
        e = (r - a - b * m)
        resid[t] = e
        rows.append(dict(ticker=t, weeks=int(ok.sum()), beta=b, corr_mkt=np.corrcoef(r[ok], m[ok])[0, 1],
                         vol=r[ok].std() * np.sqrt(52), resid_vol=e[ok].std() * np.sqrt(52)))
    E = pd.DataFrame(resid)
    fx = pd.DataFrame({
        "rates_10y": lr["USGG10YR Index"], "dollar": lr["DXY Curncy"], "brent": lr["CO1 Comdty"], "copper": lr["HG1 Comdty"],
        "gold": lr["XAU BGN Curncy"], "growth_value": lr["SGX Index"] - lr["SVX Index"], "small_large": lr["RTY Index"] - lr["SPX Index"],
        "nasdaq_spx": lr["NDX Index"] - lr["SPX Index"], "semis_spx": lr["SOX Index"] - lr["SPX Index"],
        "hy_spread": lr["LF98OAS Index"], "vix": lr["VIX Index"]})
    expo = pd.DataFrame({k: E.corrwith(fx[k]) for k in fx})
    C = E.corr(min_periods=MIN_WEEKS)
    C = C.fillna(0.0)
    D = 1 - C.to_numpy()
    np.fill_diagonal(D, 0)
    D = (D + D.T) / 2
    lab, leaves = average_linkage(D, CUT)
    Z = None
    order = [C.index[i] for i in leaves]
    info = pd.DataFrame(rows).set_index("ticker")
    info["name"] = [str(ref.name.get(t, t)) for t in info.index]
    info["cluster"] = pd.Series(lab, index=C.index)
    info = info.join(expo)
    info["leaf"] = pd.Series({t: i for i, t in enumerate(order)})
    OUT.mkdir(parents=True, exist_ok=True)
    info.sort_values(["cluster", "leaf"]).to_csv(OUT / "clusters.csv")
    C.loc[order, order].to_csv(OUT / "residual_corr.csv")
    return info, C, Z, px.index[0].date(), px.index[-1].date()


if __name__ == "__main__":
    info, C, Z, d0, d1 = run()
    ok = info[info.cluster.notna()]
    print(f"weekly returns {d0} to {d1}; {len(ok)} themes clustered, {info.cluster.isna().sum()} too short")
    print("clusters:", ok.cluster.nunique(), "sizes:", sorted(ok.cluster.value_counts().tolist(), reverse=True))
    print("median beta", round(ok.beta.median(), 2), "median market corr", round(ok.corr_mkt.median(), 2))
    fcols = ["rates_10y", "dollar", "brent", "copper", "gold", "growth_value", "small_large", "nasdaq_spx", "semis_spx", "hy_spread"]
    for c, g in sorted(ok.groupby("cluster"), key=lambda x: -len(x[1])):
        g = g.sort_values("leaf")
        ex = g[fcols].mean()
        top = ex.abs().sort_values(ascending=False).index[:3]
        print(f"\n#{int(c)} n={len(g)} beta {g.beta.mean():.2f} | " + ", ".join(f"{k} {ex[k]:+.2f}" for k in top))
        print("   " + "; ".join(f"{t.split()[0]}:{n[:26]}" for t, n in zip(g.index, g.name)))
