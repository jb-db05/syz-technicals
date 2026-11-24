"""Thematic review, step 1 – review page for the cluster map (research; for the analyst to validate the groups).

python -m syztech.research.theme_cluster_page -> output/html_thematics_clusters/index.html (+ corr.png, syz_logo.png)
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from .theme_clusters import run

ASSETS = Path(__file__).resolve().parents[1] / "report" / "assets"
OUT = Path("output/html_thematics_clusters")
FACTORS = ["rates_10y", "dollar", "brent", "copper", "gold", "growth_value", "small_large", "nasdaq_spx", "semis_spx", "hy_spread"]
# proposed cluster names, keyed by one member (the analyst confirms or renames them)
NAMES = {
    "IMAE NA Equity": "Europe & Switzerland – broad market, financials, defensives", "GLD US Equity": "Gold, precious metals & miners",
    "GSG US Equity": "Energy & broad commodities", "KRE US Equity": "US banks, financials & mid / small caps",
    "CLOU US Equity": "Software, cloud & cyber security", "IBIT US Equity": "Crypto assets & blockchain",
    "IBB US Equity": "Biotech & health care", "SOXX US Equity": "AI, semiconductors & US technology",
    "XLU US Equity": "Utilities, real estate & infrastructure", "PHO US Equity": "Materials, water & agriculture",
    "EEM US Equity": "Emerging markets – broad, ex-China, Korea", "FINX US Equity": "Digital consumer, fintech & travel",
    "MCHI US Equity": "China & China technology", "ITA US Equity": "Aerospace, defence & space",
    "IWDA LN Equity": "Global & US core, quality", "ICLN US Equity": "Clean energy – solar, wind, hydrogen",
    "XLP US Equity": "US consumer staples", "IFRA US Equity": "US industrials & infrastructure build-out",
    "4BRZ GY Equity": "Latin America & EM dividend", "URA US Equity": "Uranium", "IJPA LN Equity": "Japan & world value",
    "LIT US Equity": "Batteries, lithium & rare earths", "XLG US Equity": "US mega caps & ESG large caps", "SXKP Index": "Telecoms",
    "ROBO US Equity": "Robotics & internet of things", "S5INSU Index": "US insurance, commercial services, health-care equipment",
    "IAUS LN Equity": "Pacific ex-Japan, Australia, Canada", "COPA LN Equity": "Industrial metals – copper, aluminium",
    "ESPO US Equity": "Video games & social media", "TRAN Index": "US transport", "SXTP Index": "Europe travel & leisure",
    "SX8P Index": "Europe technology", "SPMV LN Equity": "Minimum volatility", "CMEX NA Equity": "Mexico",
    "ARKK US Equity": "Disruptive innovation & IPOs", "DTCR US Equity": "Data centres & digital infrastructure",
    "S5RETL Index": "US consumer discretionary", "S5MEDA Index": "US media & communication services"}


def _f(x, d=2):
    return None if x is None or pd.isna(x) else round(float(x), d)


def build():
    info, C, _z, d0, d1 = run()
    ok = info[info.cluster.notna()].copy()
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy(ASSETS / "syz_logo.png", OUT / "syz_logo.png")
    order = list(ok.sort_values("leaf").index)
    M = C.loc[order, order].to_numpy()
    # correlation map (residual correlations, themes in cluster order; white lines = cluster borders)
    cmap = LinearSegmentedColormap.from_list("syz", ["#AC5D85", "#FFFFFF", "#202945"])
    fig, ax = plt.subplots(figsize=(9, 9), dpi=170)
    ax.imshow(M, cmap=cmap, vmin=-1, vmax=1, interpolation="nearest")
    cl = ok.loc[order, "cluster"].to_numpy()
    for i in range(1, len(cl)):
        if cl[i] != cl[i - 1]:
            ax.axhline(i - 0.5, color="#FF6C0E", lw=0.35)
            ax.axvline(i - 0.5, color="#FF6C0E", lw=0.35)
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    fig.tight_layout(pad=0.2)
    fig.savefig(OUT / "corr.png")
    plt.close(fig)

    clusters = []
    for c, g in ok.groupby("cluster"):
        g = g.sort_values("leaf")
        name = next((NAMES[t] for t in g.index if t in NAMES), None)
        sub = C.loc[g.index, g.index].to_numpy()
        within = float(sub[np.triu_indices(len(g), 1)].mean()) if len(g) > 1 else None
        clusters.append(dict(
            id=int(c), name=name or g.name.iloc[0].title(), single=len(g) == 1, n=len(g), beta=_f(g.beta.mean()), within=_f(within),
            vol=_f(g.vol.mean() * 100, 0), first=int(g.leaf.min()),
            expo={k: _f(g[k].mean()) for k in FACTORS},
            members=[dict(t=t, n=str(r["name"]).title() if str(r["name"]).isupper() else str(r["name"]), b=_f(r.beta), cm=_f(r.corr_mkt),
                          v=_f(r.vol * 100, 0), w=int(r.weeks), e={k: _f(r[k]) for k in FACTORS}) for t, r in g.iterrows()]))
    clusters.sort(key=lambda x: (-x["n"], x["first"]))
    # near-duplicates: sets of themes linked by a residual correlation of 0.95 or more (the same exposure under several tickers)
    parent = {t: t for t in order}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for i, a in enumerate(order):
        for j in range(i + 1, len(order)):
            if M[i, j] >= 0.95:
                parent[find(a)] = find(order[j])
    sets = {}
    for t in order:
        sets.setdefault(find(t), []).append(t)
    dup = []
    for g in sets.values():
        if len(g) > 1:
            ix = [order.index(t) for t in g]
            sub = M[np.ix_(ix, ix)]
            dup.append(dict(t=g, c=round(float(sub[np.triu_indices(len(g), 1)].min()), 2)))
    dup.sort(key=lambda d: -len(d["t"]))
    data = dict(d0=f"{d0.day} {d0:%B %Y}", d1=f"{d1.day} {d1:%B %Y}", n=len(ok), k=len(clusters),
                multi=sum(1 for c in clusters if not c["single"]), singles=sum(1 for c in clusters if c["single"]),
                beta_med=_f(ok.beta.median()), corr_med=_f(ok.corr_mkt.median()), clusters=clusters, dup=dup,
                names={t: (str(n).title() if str(n).isupper() else str(n)) for t, n in zip(ok.index, ok.name)})
    html = (ASSETS / "theme_clusters.html").read_text(encoding="utf-8").replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False))
    (OUT / "index.html").write_text(html, encoding="utf-8")
    return OUT / "index.html", data


if __name__ == "__main__":
    p, d = build()
    print(f"written: {p} – {d['n']} themes, {d['k']} clusters ({d['multi']} groups, {d['singles']} single), {len(d['dup'])} duplicate sets covering {sum(len(x['t']) for x in d['dup'])} tickers")
