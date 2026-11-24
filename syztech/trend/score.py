"""Run the trend engine across the universe (BUILD_SPEC §3.5, scores table)."""
from __future__ import annotations

import pandas as pd

from ..indicators.rs import rs_summary
from ..io.bloomberg_prices import LoadResult
from .rules import DEFAULT_PARAMS, INSUFFICIENT, NEUTRAL, TrendParams, evaluate
from .swing_levels import swing_levels

FALLBACK_ORIGINS = ("52w", "swing")      # levels with these origins are recomputed at every run, never treated as drawn


REL_STATE = {"outperforming": "Outperform", "underperforming": "Underperform", "mixed": "Neutral"}
REL_RULE = {"outperforming": "rs_ma200_rising", "underperforming": "rs_ma200_falling", "mixed": "rs_ma200_unchanged"}


def relative_verdict(s: pd.Series, b: pd.Series, params: TrendParams = DEFAULT_PARAMS) -> dict:
    """Relative trend (rule of 25 Nov 2026): only the slope of the 200-day average of the relative-strength line.

    RS = price ÷ benchmark × 100; slope = its 200-day average today against 20 trading days ago. Rising = Outperform,
    falling = Underperform, exactly unchanged = Neutral (no flat band). Needs more than 220 common closes; otherwise
    rel_state is None and rel_missing says so. Nothing else (price structure, 50-day) enters."""
    t = rs_summary(s, b).get("rs_trend")
    if t is None:
        return {"rel_state": None, "rel_rule": "rs_history_too_short",
                "rel_missing": "fewer than 221 common closes with the benchmark for the 200-day average of relative strength"}
    return {"rel_state": REL_STATE[t], "rel_rule": REL_RULE[t], "rel_missing": None}


def _opt(x):
    return None if x is None or pd.isna(x) else float(x)


def resolve_levels(s: pd.Series, sup, res, sup_origin, res_origin):
    """Per side: a drawn level (text / chart) is kept; otherwise the swing level (§3.2), else the 52-week level.

    Returns (support, resistance, support_origin, resistance_origin, support_start, resistance_start); a start of None
    means the drawn-level window (levels_asof − levels_lookback)."""
    drawn = lambda v, o: v is not None and not (isinstance(o, str) and o.startswith(FALLBACK_ORIGINS))
    ds, dr = drawn(sup, sup_origin), drawn(res, res_origin)
    out = [sup if ds else None, res if dr else None, sup_origin if ds else None, res_origin if dr else None, None, None]
    if ds and dr:
        return tuple(out)
    sw = swing_levels(s)
    if sw is not None:
        d = lambda b: s.index[b].date()
        if not ds:
            out[0], out[4] = sw.support, sw.start
            out[2] = f"swing low ({d(sw.support_bar)})" + (", broken" if sw.support_broken_prior else "")
        if not dr:
            out[1], out[5] = sw.resistance, sw.start
            out[3] = f"swing high ({d(sw.resistance_bar)})" + (", broken" if sw.resistance_broken_prior else "")
        return tuple(out)
    end = s.index[-1]
    w = s[(s.index > end - pd.Timedelta(weeks=52)) & (s.index < end)]
    if len(w):
        if not ds:
            out[0], out[2], out[4] = float(w.min()), f"52w low ({w.idxmin().date()})", len(s) - 1
        if not dr:
            out[1], out[3], out[5] = float(w.max()), f"52w high ({w.idxmax().date()})", len(s) - 1
    return tuple(out)


def score_universe(prices: LoadResult, universe: pd.DataFrame, asof=None,
                   params: TrendParams = DEFAULT_PARAMS) -> pd.DataFrame:
    asof = pd.Timestamp(asof) if asof is not None else None
    rows = []
    for _, u in universe.iterrows():
        t = u.ticker
        base = {"ticker": t, "name": u.get("name"), "asset_class": u.get("asset_class"), "group": u.get("group"),
                "decimals": u.get("decimals"), "badge": u.get("badge"), "badge_asof": u.get("badge_asof"),
                "levels_asof": u.get("levels_asof"),
                "support_origin": u.get("support_origin"), "resistance_origin": u.get("resistance_origin")}
        if t not in prices.reports:
            rows.append({**base, "verdict": INSUFFICIENT, "rule": "no_price_series",
                         "missing": "no price series for this ticker in data/prices"})
            continue
        s = prices.series(t)
        if asof is not None:
            s = s[s.index <= asof]
        sup, res, so, ro, ss, rs_ = resolve_levels(s.dropna(), _opt(u.get("support")), _opt(u.get("resistance")),
                                                   u.get("support_origin"), u.get("resistance_origin"))
        base["support_origin"], base["resistance_origin"] = so, ro
        r = evaluate(s, params, sup, res, u.get("levels_asof"), support_start=ss, resistance_start=rs_)
        row = {**base, "last_date": s.index[-1].date() if len(s) else None, "bars": len(s),
               "verdict": r.verdict, "rule": r.rule, "score": r.score, "lt_view": r.lt_view, "missing": r.missing,
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
                          "+".join(sorted({str(o).split(" ")[0] if isinstance(o, str) and o.startswith(FALLBACK_ORIGINS) else "drawn"
                                           for o in (so, ro)})),
                "structure": st.state, "structure_event": st.event, "structure_date": d(st.event_pos),
            })
            prior = u.get("standing_position")
            row["prior"] = prior if r.verdict == NEUTRAL and isinstance(prior, str) and prior else None
            bench = u.get("benchmark")
            if isinstance(bench, str) and bench:
                if bench in prices.reports:
                    b = prices.series(bench)
                    b = b[b.index <= s.index[-1]]
                    row.update(rs_summary(s, b))
                    row.update(relative_verdict(s, b, params))
                else:
                    row["rs_note"] = f"benchmark {bench} not in export"
        rows.append(row)
    return pd.DataFrame(rows)
