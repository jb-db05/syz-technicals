"""Variant B: robust k = 1.5 (adopted) + Bullish only while MA50 >= MA200 (otherwise Neutral+)."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .study import OUT, fwd_table, flips, series_pool
from .swing import family


def main():
    pool, cls = series_pool()
    h = pd.read_csv(OUT / "histories.csv", parse_dates=["date"])
    b = pd.read_csv(OUT / "badges.csv")
    m = json.loads((OUT / "metrics.json").read_text())
    below = {}
    for t, s in pool.items():
        below[t] = (s.rolling(50).mean() < s.rolling(200).mean()).to_numpy()
    flag = np.array([below[t][int(i)] for t, i in zip(h.ticker, h.i)])
    h["b1.5"] = np.where((h["r1.5"] == "Bullish") & flag, "Neutral+", h["r1.5"])
    fl, sp = flips(h, "b1.5")
    m["rules"]["b1.5"] = {"flips_per_year": fl, "median_spell_weeks": sp, "fwd": fwd_table(h, "b1.5", cls)}
    today = h.sort_values("date").groupby("ticker").tail(1)
    m["today"]["b1.5"] = today["b1.5"].map(family).value_counts().to_dict()
    bv = []
    for r in b.itertuples():
        s = pool[r.ticker]
        s = s[s.index <= "2026-11-06"]
        lo = s.rolling(50).mean().iloc[-1] < s.rolling(200).mean().iloc[-1]
        bv.append("Neutral+" if (r._asdict()["_" + str(list(b.columns).index("r1.5") + 1)] == "Bullish" and lo) else
                  r._asdict()["_" + str(list(b.columns).index("r1.5") + 1)])
    b["b1.5"] = bv
    agree = b["b1.5"].map(family) == b.published.map(family)
    m["badges"]["b1.5"] = {"agree": int(agree.sum()), "share": float(agree.mean()),
                           "confusion": pd.crosstab(b.published.map(family), b["b1.5"].map(family)).to_dict()}
    h.to_csv(OUT / "histories.csv", index=False)
    b.to_csv(OUT / "badges.csv", index=False)
    (OUT / "metrics.json").write_text(json.dumps(m, indent=1, default=str))
    for c in ("r1.5", "b1.5"):
        v = m["rules"][c]; f = v["fwd"]
        print(c, "badges", m["badges"][c]["agree"], "/ 80", "flips", round(v["flips_per_year"], 2), "spell", v["median_spell_weeks"],
              "today", m["today"][c], "| f65", {k: (round(f[k]["f65"]["mean"] * 100, 1), round(f[k]["f65"]["hit"] * 100)) for k in f})
    print(pd.crosstab(b.published.map(family), b["b1.5"].map(family)).to_string())
    ch = b[b["b1.5"] != b["r1.5"]][["name", "published", "r1.5", "b1.5"]]
    print("calls changed by B:\n", ch.to_string())


if __name__ == "__main__":
    main()
