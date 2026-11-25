"""Research: the trend rule in force on weekly closes instead of daily (25 Nov 2026) – not used by any report.

python -m syztech.research.study_weekly -> output/rule_study/weekly_metrics.json

Weekly version = the same rule with every window divided by five:
  200-day average -> 40 weeks, 50-day -> 10 weeks, direction over 20 days -> 4 weeks (same 0.20% flat band),
  100-day band -> 20 weeks, one-month move = stdev of weekly log returns over 20 weeks × √4, median over 52 weeks,
  swing = 1.5 × that median, minimum history 320 days -> 64 weeks. Weekly close = last close of each calendar week.
Compared with the daily rule on the same instruments and the same dates (Fridays): share of dates with the same verdict
family (Bullish / Neutral / Bearish), verdict changes a year, and the same for the relative trend.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..indicators.rs import relative_strength
from ..io.bloomberg_prices import load_prices
from ..trend.rules import INSUFFICIENT, TrendParams, evaluate
from ..trend.score import resolve_levels
from ..trend.swing_levels import SWING_K, pivots
from .swing import family

OUT = Path("output/rule_study")
WEEKLY = TrendParams(ma_long=40, ma_short=10, band_window=20, slope_lookback=4, flat_band=0.0020, cross_lookback=8,
                     bb_window=20, min_history=64, levels_lookback=20)
SETS = [("data/prices_spx_it", "data/universe_spx_it.csv"), ("data/prices_swiss_spi", "data/universe_swiss_spi.csv"),
        ("data/prices_sectors_style", "data/universe_sectors_style.csv"), ("data/prices_thematics", "data/universe_thematics.csv")]


def to_weekly(s: pd.Series) -> pd.Series:
    s = s.dropna()
    return s.groupby([s.index.isocalendar().year, s.index.isocalendar().week]).tail(1)


def weekly_levels(w: pd.Series):
    """Swing levels on weekly closes: same construction as swing_levels, weekly windows."""
    if len(w) < 30 or (w <= 0).any():
        return None
    m = np.log(w).diff().rolling(20, min_periods=20).std() * np.sqrt(4)
    theta = (SWING_K * m.rolling(52, min_periods=26).median()).to_numpy()
    piv = pivots(w, theta)
    H = [(p[2], p[1]) for p in piv if p[0] == "H"]
    L = [(p[2], p[1]) for p in piv if p[0] == "L"]
    if not H or not L:
        return None
    (sup, sb), (res, rb) = L[-1], H[-1]
    if len(L) > 1 and L[-1][0] < L[-2][0]:
        sup, sb = L[-2]
    if len(H) > 1 and H[-1][0] > H[-2][0]:
        res, rb = H[-2]
    return float(sup), float(res), int(min(sb, rb))


def verdict_weekly(w: pd.Series) -> str | None:
    lv = weekly_levels(w)
    if lv is None:                                   # same fallback as the daily rule: 52-week levels
        if len(w) < 54:
            return None
        x = w.iloc[-53:-1]
        sup, res, st = float(x.min()), float(x.max()), len(w) - 1
    else:
        sup, res, st = lv
    r = evaluate(w, WEEKLY, sup, res, None, support_start=st, resistance_start=st)
    return None if r.verdict == INSUFFICIENT else r.verdict


def verdict_daily(s: pd.Series) -> str | None:
    sup, res, _so, _ro, ss, rs_ = resolve_levels(s, None, None, None, None)
    r = evaluate(s, support=sup, resistance=res, support_start=ss, resistance_start=rs_)
    return None if r.verdict == INSUFFICIENT else r.verdict


def rel_sign(rs: pd.Series, ma: int, look: int):
    if len(rs) <= ma + look:
        return None
    m = rs.rolling(ma).mean()
    c = m.iloc[-1] / m.iloc[-1 - look] - 1
    return "Outperform" if c > 0 else "Underperform" if c < 0 else "Neutral"


def main(n_series: int = 160, every: int = 4, seed: int = 7):
    rng = np.random.default_rng(seed)
    pool = []
    for px, un in SETS:
        if not Path(px).exists():
            continue
        p = load_prices(px)
        u = pd.read_csv(un)
        for t, b in zip(u.ticker, u.benchmark):
            if t in p.reports and p.series(t).dropna().size > 900 and (p.series(t).dropna() > 0).all():
                pool.append((p, t, b if isinstance(b, str) and b in p.reports else None))
    pick = [pool[i] for i in rng.choice(len(pool), size=min(n_series, len(pool)), replace=False)]
    rows = []
    for p, t, b in pick:
        s = p.series(t).dropna()
        w = to_weekly(s)
        rs = relative_strength(s, p.series(b)).dropna() if b else None
        rw = to_weekly(rs) if rs is not None else None
        for k in range(70, len(w), every):
            d = w.index[k]
            vd, vw = verdict_daily(s[s.index <= d]), verdict_weekly(w.iloc[:k + 1])
            row = dict(ticker=t, date=d, d=family(vd), w=family(vw), d_raw=vd, w_raw=vw)
            if rs is not None:
                row.update(rd=rel_sign(rs[rs.index <= d], 200, 20), rw=rel_sign(rw[rw.index <= d], 40, 4))
            rows.append(row)
    H = pd.DataFrame(rows)
    both = H.dropna(subset=["d", "w"])
    out = dict(series=len(pick), dates=int(both.date.nunique()), samples=int(len(both)), first=str(both.date.min().date()), last=str(both.date.max().date()),
               agree=float((both.d == both.w).mean()), agree_exact=float((both.d_raw == both.w_raw).mean()),
               opposite=float((((both.d == "Bullish") & (both.w == "Bearish")) | ((both.d == "Bearish") & (both.w == "Bullish"))).mean()),
               cross=pd.crosstab(both.d, both.w, normalize="all").round(4).to_dict())
    last = both.sort_values("date").groupby("ticker").tail(1)
    out["agree_today"] = float((last.d == last.w).mean())

    def flips(col):
        f = []
        for _, g in both.groupby("ticker"):
            g = g.sort_values("date")
            yrs = (g.date.iloc[-1] - g.date.iloc[0]).days / 365.25
            if yrs > 1:
                f.append((g[col] != g[col].shift()).iloc[1:].sum() / yrs)
        return float(np.mean(f))
    out["changes_daily"], out["changes_weekly"] = flips("d"), flips("w")       # sampled every `every` weeks: a floor for both
    r = H.dropna(subset=["rd", "rw"]) if "rd" in H else pd.DataFrame()
    if len(r):
        out["rel_agree"], out["rel_samples"] = float((r.rd == r.rw).mean()), int(len(r))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "weekly_metrics.json").write_text(json.dumps(out, indent=1))
    H.to_csv(OUT / "weekly_histories.csv", index=False)
    return out


if __name__ == "__main__":
    o = main()
    print(json.dumps({k: v for k, v in o.items() if k != "cross"}, indent=1))
    print(pd.DataFrame(o["cross"]).round(3).to_string())
