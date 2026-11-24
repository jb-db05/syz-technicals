"""Thematic review – does the shortlist rule work as a portfolio? (research; never part of a verdict)

python -m syztech.research.theme_backtest -> output/thematics/backtest.json, backtest_monthly.csv

Every 21 trading days from the first date with enough history, each theme is read with the data available that day
(trend engine in force, relative trend against the MSCI ACWI, momentum score). A portfolio is formed, held for the next
21 days in equal weights (unless stated), and compared with the MSCI ACWI and with an equal-weight basket of all themes.
No costs; turnover is reported. A month with no eligible theme holds the MSCI ACWI.

Caveats, to be repeated wherever the result is shown: seven years of history; the clusters were formed on 2023–26 data;
the list holds only funds that exist today; themes enter the test as their history allows.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..io.bloomberg_prices import load_prices
from ..report.thematic import BENCH, MAX_PER_CLUSTER, build_review, composite, momentum_score
from ..trend.rules import INSUFFICIENT, evaluate
from ..trend.score import relative_verdict, resolve_levels

OUT = Path("output/thematics")
STEP = 21
WEAK = ("Neutral-", "Bearish", "Bearish_LM")


def state(s: pd.Series, b: pd.Series) -> dict | None:
    """What the review would have said on the last day of `s` (None if the series is too short or stale)."""
    if len(s) < 260:
        return None
    sup, res, _so, _ro, ss, rs_ = resolve_levels(s, None, None, None, None)
    r = evaluate(s, support=sup, resistance=res, support_start=ss, resistance_start=rs_)
    if r.verdict == INSUFFICIENT or r.snapshot is None:
        return None
    rel = relative_verdict(s, b)
    m = momentum_score(s, b)
    vol = float(np.log(s).diff().iloc[-126:].std() * np.sqrt(252))
    return dict(v=r.verdict, slope=r.snapshot.slope200, rel=rel.get("rel_state"), rs3=m["rs3"], mom=m["mom"], vol=vol)


def panel(rv, prices) -> tuple[pd.DataFrame, list, dict]:
    b = prices.series(BENCH).dropna()
    b = b[b.index <= rv.asof]
    dates = [b.index[i] for i in range(320, len(b), STEP)]
    th = rv.themes
    S = {t: prices.series(t).dropna() for t in th.ticker}
    comp = {}
    for cid, g in th.groupby("cid"):
        comp[cid] = composite({t: S[t] for t in g.ticker}) if len(g) > 1 else S[g.ticker.iloc[0]]
    cid_of = dict(zip(th.ticker, th.cid))
    rows = []
    for d in dates:
        bd = b[b.index <= d]
        crel = {}
        for cid, s in comp.items():
            sd = s[s.index <= d]
            crel[cid] = relative_verdict(sd, bd).get("rel_state") if len(sd) > 230 and (d - sd.index[-1]).days <= 7 else None
        for t, s in S.items():
            sd = s[s.index <= d]
            if not len(sd) or (d - sd.index[-1]).days > 7:          # not trading yet, or stale: not eligible
                continue
            st = state(sd, bd)
            if st is None:
                continue
            rows.append(dict(date=d, ticker=t, cid=cid_of[t], px=float(sd.iloc[-1]), crel=crel[cid_of[t]], **st))
    return pd.DataFrame(rows), dates, {"bench": b}


def _pick(day: pd.DataFrame, extra=None, per=MAX_PER_CLUSTER) -> list[str]:
    ok = day[(day.v == "Bullish") & (day.slope == "rising") & (day.rel == "Outperform")]
    if extra is not None:
        ok = ok[extra(ok)]
    return list(ok.sort_values("mom", ascending=False).groupby("cid").head(per).ticker)


def run_variants(P: pd.DataFrame, dates: list, bench: pd.Series) -> tuple[pd.DataFrame, dict]:
    by = {d: g.set_index("ticker") for d, g in P.groupby("date")}
    names = ["Base rule", "+ cluster Outperforms", "+ RS 3m positive", "+ hold until it weakens", "All three", "One per cluster, risk-weighted"]
    held = {n: [] for n in names}
    recs = []
    for i, d in enumerate(dates[:-1]):
        d1 = dates[i + 1]
        day, nxt = by.get(d), by.get(d1)
        if day is None or nxt is None:
            continue
        fwd = (nxt.px / day.px).dropna() - 1                      # themes priced on both dates
        day = day.loc[day.index.intersection(fwd.index)]
        dd = day.reset_index()
        bret = float(bench[bench.index <= d1].iloc[-1] / bench[bench.index <= d].iloc[-1] - 1)
        conf = lambda x: x.crel == "Outperform"
        rs3 = lambda x: x.rs3 > 0
        both = lambda x: (x.crel == "Outperform") & (x.rs3 > 0)

        def sticky(prev, extra):
            keep = [t for t in prev if t in day.index and day.v[t] not in WEAK and day.rel[t] == "Outperform"]
            new = [t for t in _pick(dd, extra, per=99) if t not in keep]
            out = list(keep)
            for t in new:                                          # holdings keep their place; the cap applies to entries
                if sum(1 for x in out if day.cid[x] == day.cid[t]) < MAX_PER_CLUSTER:
                    out.append(t)
            return out
        picks = {"Base rule": _pick(dd), "+ cluster Outperforms": _pick(dd, conf), "+ RS 3m positive": _pick(dd, rs3),
                 "+ hold until it weakens": sticky(held["+ hold until it weakens"], None),
                 "All three": sticky(held["All three"], both), "One per cluster, risk-weighted": _pick(dd, per=1)}
        rec = dict(date=d1, acwi=bret, all_themes=float(fwd.mean()), n_all=int(len(fwd)))
        for n in names:
            h = picks[n]
            if h:
                w = (1 / day.vol[h]) if n.startswith("One per") else pd.Series(1.0, index=h)
                w = w / w.sum()
                rec[n] = float((fwd[h] * w).sum())
            else:
                rec[n] = bret
            prev = held[n]
            rec[n + "|n"] = len(h)
            rec[n + "|to"] = (len(set(h) ^ set(prev)) / max(1, len(h) + len(prev))) if (h or prev) else 0.0   # one-way turnover
            held[n] = h
        recs.append(rec)
    M = pd.DataFrame(recs).set_index("date")
    per_year = 252 / STEP

    def stats(r: pd.Series, n=None) -> dict:
        eq = (1 + r).cumprod()
        ex = r - M.acwi
        out = dict(ret=float(eq.iloc[-1] ** (per_year / len(r)) - 1), vol=float(r.std() * np.sqrt(per_year)),
                   dd=float((eq / eq.cummax() - 1).min()), excess=float(ex.mean() * per_year),
                   hit=float((ex > 0).mean()), t=float(ex.mean() / (ex.std() / np.sqrt(len(ex)))) if ex.std() > 0 else None)
        out["rv"] = out["ret"] / out["vol"] if out["vol"] else None
        if n:
            out.update(n=float(M[n + "|n"].mean()), empty=float((M[n + "|n"] == 0).mean()), turnover=float(M[n + "|to"].mean()))
        return out
    res = {"MSCI ACWI": stats(M.acwi), "All themes, equal weight": stats(M.all_themes)}
    for n in names:
        res[n] = stats(M[n], n)
    # second half only, as a stability check
    half = M.iloc[len(M) // 2:]
    res["_second_half"] = {n: float(((half[n] - half.acwi).mean()) * per_year) for n in ["all_themes"] + names}
    res["_first_half"] = {n: float(((M.iloc[:len(M) // 2][n] - M.iloc[:len(M) // 2].acwi).mean()) * per_year) for n in ["all_themes"] + names}
    meta = dict(first=str(M.index[0].date()), last=str(M.index[-1].date()), months=int(len(M)), n_start=int(M.n_all.iloc[0]), n_end=int(M.n_all.iloc[-1]),
                names=names)
    return M, {"meta": meta, "stats": res}


def main():
    rv = build_review()
    prices = load_prices("data/prices_thematics")
    P, dates, x = panel(rv, prices)
    M, out = run_variants(P, dates, x["bench"])
    OUT.mkdir(parents=True, exist_ok=True)
    M.to_csv(OUT / "backtest_monthly.csv")
    out["equity"] = {k: [round(float(v), 4) for v in (1 + M[c]).cumprod()] for k, c in
                     (("MSCI ACWI", "acwi"), ("All themes, equal weight", "all_themes"), ("Base rule", "Base rule"), ("All three", "All three"))}
    out["dates"] = [str(d.date()) for d in M.index]
    out["vs_themes"] = {}                                    # the rule against simply owning every theme
    for n in out["meta"]["names"]:
        ex = M[n] - M.all_themes
        out["vs_themes"][n] = dict(excess=float(ex.mean() * 252 / STEP), t=float(ex.mean() / (ex.std() / np.sqrt(len(ex)))), hit=float((ex > 0).mean()))
    out["years"] = {int(y): {k: float((1 + g[c]).prod() - 1) for k, c in (("acwi", "acwi"), ("themes", "all_themes"), ("base", "Base rule"), ("all3", "All three"))}
                    for y, g in M.groupby(M.index.year)}
    (OUT / "backtest.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    o = main()
    m = o["meta"]
    print(f"{m['months']} periods, {m['first']} to {m['last']}; themes in the test: {m['n_start']} at the start, {m['n_end']} at the end")
    print(f"{'':34s} {'ret':>7} {'vol':>6} {'maxDD':>7} {'r/vol':>6} {'excess':>7} {'hit':>5} {'t':>5} {'n':>5} {'empty':>6} {'turn':>5}")
    for k, s in o["stats"].items():
        if k.startswith("_"):
            continue
        print(f"{k:34s} {s['ret']:7.1%} {s['vol']:6.1%} {s['dd']:7.1%} {s['rv']:6.2f} {s['excess']:7.1%} {s['hit']:5.0%} {s['t'] if s['t'] is not None else 0:5.2f} "
              + (f"{s['n']:5.1f} {s['empty']:6.0%} {s['turnover']:5.0%}" if "n" in s else ""))
    print("excess vs ACWI, first half :", {k: f"{v:+.1%}" for k, v in o["stats"]["_first_half"].items()})
    print("excess vs ACWI, second half:", {k: f"{v:+.1%}" for k, v in o["stats"]["_second_half"].items()})
