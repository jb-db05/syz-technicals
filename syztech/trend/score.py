"""Run the trend engine across the universe (BUILD_SPEC §3.5, scores table)."""
from __future__ import annotations

import pandas as pd

from ..indicators.rs import rs_summary
from ..io.bloomberg_prices import LoadResult
from .rules import DEFAULT_PARAMS, INSUFFICIENT, NEUTRAL, TrendParams, evaluate


def _opt(x):
    return None if x is None or pd.isna(x) else float(x)


def score_universe(prices: LoadResult, universe: pd.DataFrame, asof=None,
                   params: TrendParams = DEFAULT_PARAMS) -> pd.DataFrame:
    asof = pd.Timestamp(asof) if asof is not None else None
    rows = []
    for _, u in universe.iterrows():
        t = u.ticker
        base = {"ticker": t, "name": u.get("name"), "asset_class": u.get("asset_class"), "group": u.get("group"),
                "decimals": u.get("decimals"), "badge": u.get("badge"), "badge_asof": u.get("badge_asof"),
                "levels_asof": u.get("levels_asof")}
        if t not in prices.reports:
            rows.append({**base, "verdict": INSUFFICIENT, "rule": "no_price_series",
                         "missing": "no price series for this ticker in data/prices"})
            continue
        s = prices.series(t)
        if asof is not None:
            s = s[s.index <= asof]
        sup, res = _opt(u.get("support")), _opt(u.get("resistance"))
        r = evaluate(s, params, sup, res, u.get("levels_asof"))
        row = {**base, "last_date": s.index[-1].date() if len(s) else None, "bars": len(s),
               "verdict": r.verdict, "rule": r.rule, "score": r.score, "missing": r.missing,
               "support": sup, "resistance": res}
        if r.snapshot is not None:
            n, st = r.snapshot, r.snapshot.structure
            d = lambda p: s.index[p].date() if p is not None else None
            row.update({
                "close": n.close, "ma200": n.ma200, "ma50": n.ma50, "slope200": n.slope200,
                "slope200_pct": n.slope200_ratio, "ma50_slope_pct": n.ma50_slope_ratio,
                "price_vs_200": n.price_vs_200, "cross": n.cross, "cross_direction": n.cross_direction,
                "cross_date": d(n.cross_pos), "last_band": n.last_band, "last_band_date": d(n.last_band_pos),
                "last_band_level": n.last_band_level, "bbw100": n.bbw100, "target": n.target,
                "support_source": st.support_source, "resistance_source": st.resistance_source,
                "levels": "band-fallback" if sup is None and res is None else
                          "drawn" if sup is not None and res is not None else "partial",
                "structure": st.state, "structure_event": st.event, "structure_date": d(st.event_pos),
            })
            prior = u.get("standing_position")
            row["prior"] = prior if r.verdict == NEUTRAL and isinstance(prior, str) and prior else None
            bench = u.get("benchmark")
            if isinstance(bench, str) and bench:
                if bench in prices.reports:
                    b = prices.series(bench)
                    row.update(rs_summary(s, b[b.index <= s.index[-1]]))
                else:
                    row["rs_note"] = f"benchmark {bench} not in export"
        rows.append(row)
    return pd.DataFrame(rows)
