"""Thematic Technical Review – the numbers (BUILD in progress, 24 Nov 2026).

Two stages, as agreed with Florian:
  1. clusters – themes that carry the same risk (syztech.research.theme_clusters); the large Europe block is split one
     level down; inside every set of near-identical series one line is kept;
  2. technicals – every kept theme and every cluster composite is read with the trend engine in force (verdict,
     200-day direction, relative trend against the MSCI ACWI) and ranked on a momentum score.

Cluster composite: equal-weight index of the cluster's kept themes, built from daily log returns; a theme enters a day's
average only if it has a close on that day and the day before (nothing is filled).
Momentum score (ranking only, not a verdict): average over 3, 6 and 12 months of the theme's return minus the ACWI's,
each divided by the theme's own volatility scaled to the horizon. Rank = percentile among the themes (or clusters).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from ..indicators.rs import relative_strength
from ..io.bloomberg_prices import load_prices
from ..research.theme_clusters import average_linkage, run as run_clusters
from ..research.theme_cluster_page import NAMES
from ..trend.rules import INSUFFICIENT, evaluate
from ..trend.score import relative_verdict, resolve_levels

BENCH = "MXWD Index"
DUP_CORR = 0.95
EUROPE_ANCHOR, EUROPE_CUT = "IMAE NA Equity", 0.30
EUROPE_PARENT = "Europe & Switzerland"
SUB_NAMES = {"IMAE NA Equity": "Europe – broad market & cyclicals", "SMICHA SW Equity": "Switzerland", "SX7P Index": "European banks",
             "ISF LN Equity": "United Kingdom", "S600FOP Index": "European food & staples", "SXIP Index": "European insurance",
             "VHYD LN Equity": "Global high dividend"}
HORIZONS = (63, 126, 252)
MAX_PER_CLUSTER = 2


def _title(n: str) -> str:
    n = str(n)
    return n.title() if n.isupper() else n


def dedupe(order: list[str], C: pd.DataFrame, bars: dict[str, int]) -> tuple[list[str], dict[str, list[str]]]:
    """One line per set of near-identical series (residual correlation ≥ 0.95, linked transitively).
    Kept: a fund or share (it can be bought) before an index or a spot rate, then the longest history, then the ticker."""
    parent = {t: t for t in order}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    M = C.loc[order, order].to_numpy()
    for i, a in enumerate(order):
        for j in range(i + 1, len(order)):
            if M[i, j] >= DUP_CORR:
                parent[find(a)] = find(order[j])
    sets: dict[str, list[str]] = {}
    for t in order:
        sets.setdefault(find(t), []).append(t)
    keep, dropped = [], {}
    for g in sets.values():
        best = sorted(g, key=lambda t: (0 if t.endswith("Equity") else 1, -bars.get(t, 0), t))[0]
        keep.append(best)
        if len(g) > 1:
            dropped[best] = [t for t in g if t != best]
    return keep, dropped


def composite(series: dict[str, pd.Series]) -> pd.Series:
    """Equal-weight index (100 at the start) from daily log returns; a member counts on a day only with a close on that
    day and on its own previous trading day inside the last 5 calendar days (no filling, no stale jumps)."""
    rets = {}
    for t, s in series.items():
        s = s.dropna()
        s = s[s > 0]
        r = np.log(s).diff()
        gap = s.index.to_series().diff().dt.days
        rets[t] = r[gap <= 5]
    R = pd.DataFrame(rets).sort_index()
    avg = R.mean(axis=1, skipna=True)
    avg = avg[R.notna().sum(axis=1) >= max(1, int(np.ceil(len(series) / 2)))]
    return (100 * np.exp(avg.cumsum())).rename("composite")


def momentum_score(s: pd.Series, b: pd.Series) -> dict:
    """Relative return against the benchmark over 3 / 6 / 12 months and the volatility-adjusted average (None if short)."""
    both = pd.concat([s, b], axis=1, join="inner").dropna()
    out = {"rs3": None, "rs6": None, "rs12": None, "mom": None}
    if len(both) < 64:
        return out
    x, y = both.iloc[:, 0], both.iloc[:, 1]
    vol = np.log(x).diff().iloc[-252:].std() * np.sqrt(252)
    parts = []
    for h, k in zip(HORIZONS, ("rs3", "rs6", "rs12")):
        if len(both) > h:
            rel = (x.iloc[-1] / x.iloc[-1 - h]) / (y.iloc[-1] / y.iloc[-1 - h]) - 1
            out[k] = float(rel)
            if vol and vol > 0:
                parts.append(rel / (vol * np.sqrt(h / 252)))
    if len(parts) == len(HORIZONS):
        out["mom"] = float(np.mean(parts))
    return out


def read(s: pd.Series, b: pd.Series | None) -> dict:
    """Trend engine in force on one series: verdict, rule, 200-day direction, levels, price changes, relative trend."""
    s = s.dropna()
    sup, res, so, ro, ss, rs_ = resolve_levels(s, None, None, None, None)
    r = evaluate(s, support=sup, resistance=res, support_start=ss, resistance_start=rs_)
    out = dict(verdict=r.verdict, rule=r.rule, missing=r.missing, support=sup, resistance=res, support_origin=so, resistance_origin=ro,
               bars=len(s), last_date=s.index[-1].date() if len(s) else None)
    if r.snapshot is not None:
        n = r.snapshot
        c = float(s.iloc[-1])
        end = s.index[-1]
        w = s[(s.index > end - pd.Timedelta(weeks=52))]
        ch = lambda m: (c / float(s[s.index <= end - pd.DateOffset(months=m)].iloc[-1]) - 1) if len(s[s.index <= end - pd.DateOffset(months=m)]) else None
        out.update(close=c, slope200=n.slope200, vs200=c / n.ma200 - 1, chg1m=ch(1), chg3m=ch(3), chg12m=ch(12),
                   from_hi52=c / float(w.max()) - 1)
    if b is not None:
        b = b[b.index <= s.index[-1]]
        out.update(relative_verdict(s, b))
        out.update(momentum_score(s, b))
    return out


@dataclass
class Review:
    asof: pd.Timestamp
    themes: pd.DataFrame            # kept themes, one row each
    clusters: pd.DataFrame          # one row per cluster (sub-cluster for Europe)
    series: dict = field(default_factory=dict)      # ticker or cluster id -> price series (to asof)
    bench: pd.Series | None = None
    dropped: dict = field(default_factory=dict)     # kept ticker -> duplicates left out
    window: tuple = ()


def pct_rank(x: pd.Series) -> pd.Series:
    return (x.rank(pct=True) * 100).round()


def build_review(prices_dir="data/prices_thematics", universe="data/universe_thematics.csv", asof=None) -> Review:
    prices = load_prices(prices_dir)
    info, C, _z, d0, d1 = run_clusters(prices_dir, universe)
    info = info[info.cluster.notna()].copy()
    info["name"] = info.name.map(_title)
    last = {t: prices.series(t).dropna().index[-1] for t in info.index}
    asof = pd.Timestamp(asof) if asof else min(last.values())          # last day every theme has a close
    # cluster names; Europe split one level down
    info["cname"], info["parent"] = "", ""
    for c, g in info.groupby("cluster"):
        g = g.sort_values("leaf")
        nm = next((NAMES[t] for t in g.index if t in NAMES), g.name.iloc[0])
        info.loc[g.index, "cname"] = nm
    eu = list(info[info.cluster == info.loc[EUROPE_ANCHOR, "cluster"]].sort_values("leaf").index)
    D = 1 - C.loc[eu, eu].to_numpy()
    np.fill_diagonal(D, 0)
    lab, _ = average_linkage(D, EUROPE_CUT)
    for k in sorted(set(lab)):
        m = [eu[i] for i in range(len(eu)) if lab[i] == k]
        nm = next((SUB_NAMES[t] for t in m if t in SUB_NAMES), info.loc[m[0], "name"])
        info.loc[m, "cname"], info.loc[m, "parent"] = nm, EUROPE_PARENT
    info["cid"] = info.cname.map({n: i for i, n in enumerate(dict.fromkeys(info.sort_values("leaf").cname), start=1)})
    bars = {t: int(prices.series(t).dropna().size) for t in info.index}
    order = list(info.sort_values("leaf").index)
    keep, dropped = dedupe(order, C, bars)
    bench = prices.series(BENCH).dropna()
    bench = bench[bench.index <= asof]
    rows, series = [], {}
    for t in keep:
        s = prices.series(t).dropna()
        s = s[s.index <= asof]
        series[t] = s
        r = read(s, bench)
        i = info.loc[t]
        rows.append(dict(ticker=t, name=i["name"], cid=int(i.cid), cluster=i.cname, parent=i.parent, beta=float(i.beta),
                         dups=", ".join(x.rsplit(" ", 1)[0] for x in dropped.get(t, [])), **r))
    th = pd.DataFrame(rows)
    th["mom_rank"] = pct_rank(th.mom)
    crow = []
    for cid, g in th.groupby("cid"):
        comp = composite({t: series[t] for t in g.ticker}) if len(g) > 1 else series[g.ticker.iloc[0]]
        key = f"cluster:{cid}"
        series[key] = comp
        r = read(comp, bench)
        v = g[g.verdict != INSUFFICIENT]
        crow.append(dict(key=key, cid=int(cid), cluster=g.cluster.iloc[0], parent=g.parent.iloc[0], n=len(g), beta=float(g.beta.mean()),
                         n_bull=int((v.verdict == "Bullish").sum()), n_rising=int((v.slope200 == "rising").sum()),
                         n_out=int((g.rel_state == "Outperform").sum()), n_ok=len(v), **r))
    cl = pd.DataFrame(crow)
    cl["mom_rank"] = pct_rank(cl.mom)
    return Review(asof=asof, themes=th, clusters=cl, series=series, bench=bench, dropped=dropped, window=(d0, d1))


def shortlist(rv: Review) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Shortlist: Bullish, rising 200-day, Outperform – the best `MAX_PER_CLUSTER` per cluster by momentum score.
    Watch list: Neutral verdict with a rising 200-day and Outperform (same cap)."""
    t = rv.themes
    a = t[(t.verdict == "Bullish") & (t.slope200 == "rising") & (t.rel_state == "Outperform")]
    w = t[t.verdict.astype(str).str.startswith("Neutral") & (t.slope200 == "rising") & (t.rel_state == "Outperform")]
    cap = lambda d: d.sort_values("mom", ascending=False).groupby("cid").head(MAX_PER_CLUSTER).sort_values("mom", ascending=False)
    return cap(a), cap(w)


def momentum_test(rv: Review, prices_dir="data/prices_thematics", step: int = 21) -> dict:
    """Did the ranking separate what followed? Every `step` bars: clusters ranked on the momentum score with the data to
    that day, split in thirds; average relative return against the ACWI over the next 1 and 3 months for the top and
    bottom third. Caveat: the clusters themselves were formed on 2023–26 data."""
    prices = load_prices(prices_dir)
    b = prices.series(BENCH).dropna()
    comps = {}
    for cid, g in rv.themes.groupby("cid"):
        ss = {t: prices.series(t).dropna() for t in g.ticker}
        comps[cid] = composite(ss) if len(ss) > 1 else list(ss.values())[0]
    dates = b.index[b.index <= rv.asof]
    rows = []
    for i in range(300, len(dates) - 21, step):
        d = dates[i]
        sc = {}
        for cid, s in comps.items():
            m = momentum_score(s[s.index <= d], b[b.index <= d])["mom"]
            if m is not None and s.index[-1] >= d:
                sc[cid] = m
        if len(sc) < 15:
            continue
        r = pd.Series(sc).rank(pct=True)
        for h, lab in ((21, "f1"), (63, "f3")):
            if i + h >= len(dates):
                continue
            d1 = dates[i + h]
            fb = b[b.index <= d1].iloc[-1] / b[b.index <= d].iloc[-1]
            for cid in sc:
                s = comps[cid]
                x0, x1 = s[s.index <= d], s[s.index <= d1]
                if len(x1) and x1.index[-1] > d:
                    rows.append(dict(date=d, cid=cid, h=lab, third="top" if r[cid] > 2 / 3 else "bottom" if r[cid] <= 1 / 3 else "middle",
                                     fwd=(x1.iloc[-1] / x0.iloc[-1]) / fb - 1))
    T = pd.DataFrame(rows)
    out = {"dates": int(T.date.nunique()), "first": T.date.min().date(), "last": T.date.max().date()}
    for lab in ("f1", "f3"):
        x = T[T.h == lab]
        by = x.groupby(["date", "third"]).fwd.mean().unstack()
        spread = (by["top"] - by["bottom"]).dropna()
        out[lab] = dict(top=float(by["top"].mean()), middle=float(by["middle"].mean()), bottom=float(by["bottom"].mean()),
                        spread=float(spread.mean()), hit=float((spread > 0).mean()), n=int(len(spread)),
                        t=float(spread.mean() / (spread.std() / np.sqrt(len(spread)))) if spread.std() > 0 else None)
    return out
