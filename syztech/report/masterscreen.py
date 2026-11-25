"""Master-list technical screen – weekly closes (this document only; `syztech/trend/weekly.py`).

python -m syztech.report.masterscreen -> output/html_masterlist/index.html

Each stock is read against the benchmark of its zone, both in price return and in the benchmark's currency.
Weekly dates differ by market (Friday; Thursday in the Gulf; Saturday or Sunday labels for Taiwan, Korea, India, the UAE,
Israel): every series is keyed on the Friday of its ISO week, so a stock and its benchmark are compared week for week.
Nothing is filled: a week without a close is absent.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from ..io.bloomberg_prices import load_prices
from ..trend.rules import INSUFFICIENT
from ..trend.weekly import evaluate_weekly, relative_weekly
from .weekly import VLABEL

ASSETS = Path(__file__).parent / "assets"
OUT = Path("output/html_masterlist")
FALLBACK = {"SPIX Index": ("SPI Index", "SPI (total return)")}      # used when the price index did not load; flagged
GROUPS = [("US & Canada", ["United States", "Canada"]), ("Europe ex-CH", ["Europe ex-CH"]), ("Switzerland", ["Switzerland"]),
          ("Japan", ["Japan"]), ("Developed Pacific", ["Developed Pacific"]), ("Emerging Markets", ["Emerging Markets"])]


def week_key(s: pd.Series) -> pd.Series:
    """Index every weekly close on the Friday of its ISO week (last close kept if a week has two)."""
    s = s.dropna()
    if not len(s):
        return s
    fri = s.index - pd.to_timedelta(s.index.dayofweek, unit="D") + pd.Timedelta(days=4)
    out = pd.Series(s.to_numpy(), index=fri)
    return out[~out.index.duplicated(keep="last")].sort_index()


def _chg(w: pd.Series, k: int):
    return float(w.iloc[-1] / w.iloc[-1 - k] - 1) if len(w) > k else None


def read_stock(w: pd.Series, bw: pd.Series | None) -> dict:
    r, lv = evaluate_weekly(w)
    out = dict(verdict=r.verdict, rule=r.rule, missing=r.missing, weeks=len(w), last=w.index[-1] if len(w) else None, **lv)
    if r.snapshot is not None:
        n = r.snapshot
        c = float(w.iloc[-1])
        hi = float(w.iloc[-52:].max())
        out.update(close=c, slope=n.slope200, vs40=c / n.ma200 - 1, c4=_chg(w, 4), c13=_chg(w, 13), c52=_chg(w, 52), fh=c / hi - 1)
    if bw is not None and len(w):
        b = bw[bw.index <= w.index[-1]]
        out.update(relative_weekly(w, b))
        both = pd.concat([w, b], axis=1, join="inner").dropna()
        rs = both.iloc[:, 0] / both.iloc[:, 1]
        out["rs13"] = float(rs.iloc[-1] / rs.iloc[-14] - 1) if len(rs) > 13 else None
        out["rs26"] = float(rs.iloc[-1] / rs.iloc[-27] - 1) if len(rs) > 26 else None
    return out


def build_screen(prices_dir="data/prices_masterlist", universe="data/universe_masterlist.csv") -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    prices = load_prices(prices_dir)
    u = pd.read_csv(universe).fillna("")
    W = {t: week_key(prices.series(t)) for t in u.ticker if t in prices.reports}
    notes, bench_used = [], {}
    for b in sorted(set(u[u.asset_class == "equity"].benchmark)):
        if b in W and len(W[b]):
            bench_used[b] = (b, None)
        elif b in FALLBACK and FALLBACK[b][0] in W and len(W[FALLBACK[b][0]]):
            bench_used[b] = FALLBACK[b]
            notes.append(f"{b} returned no data: {FALLBACK[b][1]} is used instead, so relative strength for that zone drifts down by about the dividend yield.")
        else:
            bench_used[b] = (None, None)
            notes.append(f"{b} returned no data: no relative trend for its zone.")
    asof = max(w.index[-1] for w in W.values() if len(w))
    rows = []
    for r in u[u.asset_class == "equity"].itertuples():
        w = W.get(r.ticker)
        base = dict(ticker=r.ticker, name=r.name, zone=r.zone, country=r.country, sector=r.sector or "Not classified", industry=r.industry,
                    satellite=str(r.satellite).strip().lower() == "yes", focus=str(r.focus).strip().lower() == "yes",
                    bench=r.bench_name, currency=r.currency)
        if w is None or not len(w):
            rows.append({**base, "verdict": INSUFFICIENT, "rule": "no_price_series", "missing": "no weekly closes in the export", "weeks": 0})
            continue
        bt = bench_used[r.benchmark][0]
        rows.append({**base, **read_stock(w, W[bt] if bt else None)})
    S = pd.DataFrame(rows)
    S["lag"] = [(asof - d).days // 7 if pd.notna(d) else None for d in S["last"]]
    brow = []
    for b, (bt, alt) in bench_used.items():
        if bt:
            name = u.set_index("ticker").bench_name.get(b, b)
            brow.append(dict(ticker=bt, name=alt or name, zone_bench=name, **read_stock(W[bt], None)))
    B = pd.DataFrame(brow)
    return S, B, dict(asof=asof, notes=notes, n_files=len(prices.reports))


def _f(x, d=4):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), d)


def build_html(out_dir: Path = OUT) -> Path:
    S, B, meta = build_screen()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(ASSETS / "syz_logo.png", out_dir / "syz_logo.png")
    g_of = {z: g for g, zs in GROUPS for z in zs}
    rows = [dict(t=r.ticker, n=r.name, z=r.zone, g=g_of.get(r.zone, r.zone), co=r.country, se=r.sector, ind=r.industry, sat=bool(r.satellite), foc=bool(r.focus),
                 b=r.bench, cur=r.currency, v=r.verdict, rule=r.rule, s=getattr(r, "slope", None) if isinstance(getattr(r, "slope", None), str) else None,
                 rs=r.rel_state if isinstance(getattr(r, "rel_state", None), str) else None,
                 vs40=_f(getattr(r, "vs40", None)), c4=_f(getattr(r, "c4", None)), c13=_f(getattr(r, "c13", None)), c52=_f(getattr(r, "c52", None)),
                 fh=_f(getattr(r, "fh", None)), rs13=_f(getattr(r, "rs13", None)), rs26=_f(getattr(r, "rs26", None)), wk=int(r.weeks),
                 lag=int(r.lag) if pd.notna(r.lag) else None) for r in S.itertuples()]
    bench = [dict(t=r.ticker, n=r.name, zb=r.zone_bench, v=r.verdict, s=r.slope if isinstance(r.slope, str) else None, vs40=_f(r.vs40), c13=_f(r.c13), c52=_f(r.c52), fh=_f(r.fh))
             for r in B.itertuples()]
    d = meta["asof"]
    data = dict(asof=f"{d.day} {d:%B %Y}", vlabel=VLABEL, rows=rows, bench=bench, notes=meta["notes"], groups=[g for g, _ in GROUPS],
                sectors=sorted(set(S.sector)))
    html = (ASSETS / "masterscreen.html").read_text(encoding="utf-8").replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False))
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    ok = S[S.verdict != INSUFFICIENT]
    print(f"written: {out_dir / 'index.html'} – {len(S)} stocks, {len(ok)} with a verdict, week to {d.date()}; notes: {meta['notes']}")
    return out_dir / "index.html"


if __name__ == "__main__":
    build_html()
