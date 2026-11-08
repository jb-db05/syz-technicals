"""Exceptions report (BUILD_SPEC §3.4): mechanical verdict vs published badge.

States facts and the rule that fired. No interpretation – the analyst writes that.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from ..fmt import EN_DASH, num
from .rules import (BEARISH, BEARISH_LM, BULLISH, INSUFFICIENT, NEUTRAL, NEUTRAL_NEG, NEUTRAL_POS)

# Ladder: Bearish | Neutral- | Neutral | Neutral+ | Bullish. Bearish_LM sits on the Bearish rung (a tilt).
RUNG = {BEARISH: 0, BEARISH_LM: 0, NEUTRAL_NEG: 1, NEUTRAL: 2, NEUTRAL_POS: 3, BULLISH: 4}
SIDE = {BEARISH: -1, BEARISH_LM: -1, NEUTRAL_NEG: 0, NEUTRAL: 0, NEUTRAL_POS: 0, BULLISH: 1}
ORDER = ["trigger_hit", "conflict", "one_step", "tilt_only", "levels_stale", "agree"]
STALE_DAYS = 28


def compare(mechanical: str, badge) -> str:
    """agree / tilt_only / one_step / conflict / no_badge / not_scored."""
    if mechanical not in RUNG:
        return "not_scored"
    if not isinstance(badge, str) or badge not in RUNG:
        return "no_badge"
    if mechanical == badge:
        return "agree"
    if SIDE[mechanical] == SIDE[badge]:
        return "tilt_only"
    if abs(RUNG[mechanical] - RUNG[badge]) == 1:
        return "one_step"
    return "conflict"


def trigger_crossed(close: pd.Series, support, resistance, badge_asof) -> tuple[str, date, float] | None:
    """First close after `badge_asof` on the other side of a drawn level (strict, close-only).

    Reference is the last close on or before `badge_asof`. Returns (description, date, level) or None.
    """
    if badge_asof is None or pd.isna(badge_asof) or close.empty:
        return None
    ts = pd.Timestamp(badge_asof)
    before, after = close[close.index <= ts], close[close.index > ts]
    if before.empty or after.empty:
        return None
    ref = before.iloc[-1]
    if support is not None and not pd.isna(support) and ref >= support:
        hit = after[after < support]
        if len(hit):
            return "close below support", hit.index[0].date(), float(support)
    if resistance is not None and not pd.isna(resistance) and ref <= resistance:
        hit = after[after > resistance]
        if len(hit):
            return "close above resistance", hit.index[0].date(), float(resistance)
    return None


def levels_stale(levels_asof, asof, has_levels: bool) -> bool:
    if not has_levels:
        return False
    if levels_asof is None or pd.isna(levels_asof):
        return True
    return (pd.Timestamp(asof) - pd.Timestamp(levels_asof)).days > STALE_DAYS


def _d(x) -> str:
    if x is None or (not isinstance(x, (str, date)) and pd.isna(x)):
        return EN_DASH
    t = pd.Timestamp(x)
    return f"{t.day} {t:%b %Y}"


def _structure_text(r, dec) -> str:
    st, ev, dt = r.get("structure"), r.get("structure_event"), r.get("structure_date")
    sup, res = r.get("support"), r.get("resistance")
    has_s = sup is not None and not pd.isna(sup)
    has_r = res is not None and not pd.isna(res)
    if st == "support_broken":
        lvl = f"support {num(sup, dec)}" if has_s else "MIN100"
        return f"{lvl} broken {_d(dt)}"
    if st == "resistance_broken":
        lvl = f"resistance {num(res, dec)}" if has_r else "MAX100"
        return f"{lvl} broken {_d(dt)}"
    parts = []
    if has_s:
        parts.append(f"support {num(sup, dec)} intact")
    if has_r:
        parts.append(f"resistance {num(res, dec)} not broken")
    if not parts:
        parts.append("no band break in force" + (f" (last: {ev} {_d(dt)})" if ev else ""))
    return ", ".join(parts)


def reason(r: pd.Series) -> str:
    """One line from the rule that fired, e.g. '200d rising, support 7,500.0 intact → Bullish; badge Neutral-'."""
    dec = int(r.decimals) if pd.notna(r.get("decimals")) else 1
    v, rule = r.verdict, r.rule
    if v == INSUFFICIENT:
        return f"insufficient_data – {r.get('missing')}"
    s = f"200d {r.slope200}, {_structure_text(r, dec)}"
    if rule == "falling_losing_momentum":
        s += ", price above 200d, 50d rising"
    if rule.startswith("flat_"):
        s += f", 50d {'below' if r.ma50 < r.ma200 else 'above'} 200d"
        if r.ma50 >= r.ma200 and r.get("ma50_slope_pct", 0) < 0:
            s += " and rolling over"
        s += f", price {r.price_vs_200} 200d"
        if r.get("cross") in ("golden", "death"):
            s += f", {r.cross} cross {_d(r.get('cross_date'))}"
    if rule == "rising_support_broken_death_cross":
        s += ", 50d below 200d"
    s += f" → {v}"
    lt = r.get("lt_view")
    if isinstance(lt, str) and lt:
        s += f" (short term); long term {lt}"
    badge = r.get("badge")
    s += f"; badge {badge}" if isinstance(badge, str) and badge else "; no badge"
    return s


def classify_frame(scores: pd.DataFrame, closes: dict[str, pd.Series], asof) -> pd.DataFrame:
    df = scores.copy()
    df["comparison"] = [compare(v, b) for v, b in zip(df.verdict, df.badge)]
    trig, stale = [], []
    for _, r in df.iterrows():
        s = closes.get(r.ticker)
        t = trigger_crossed(s, r.get("support"), r.get("resistance"), r.get("badge_asof")) if s is not None else None
        trig.append(None if t is None else f"{t[0]} {num(t[2], int(r.decimals) if pd.notna(r.decimals) else 1)} on {_d(t[1])}")
        has = pd.notna(r.get("support")) or pd.notna(r.get("resistance"))
        stale.append(levels_stale(r.get("levels_asof"), asof, has))
    df["trigger_hit"], df["levels_stale"] = trig, stale
    sections = []
    for _, r in df.iterrows():
        if isinstance(r.trigger_hit, str):
            sections.append("trigger_hit")
        elif r.comparison in ("conflict", "one_step", "tilt_only"):
            sections.append(r.comparison)
        elif r.levels_stale:
            sections.append("levels_stale")
        else:
            sections.append(r.comparison)            # agree / no_badge / not_scored
    df["section"] = sections
    df["reason"] = [reason(r) for _, r in df.iterrows()]
    return df


TITLES = {
    "trigger_hit": "Trigger hit – a drawn level was crossed since the badge date",
    "conflict": "Conflict – opposite sides or two steps apart",
    "one_step": "One step – adjacent verdicts",
    "tilt_only": "Tilt only – same side, tilt differs",
    "levels_stale": f"Levels stale – drawn levels older than {STALE_DAYS} days",
    "no_badge": "No published badge",
    "not_scored": "Not scored – insufficient data",
}


def _row(r) -> str:
    dec = int(r.decimals) if pd.notna(r.decimals) else 1
    if r.verdict == INSUFFICIENT:
        return f"| {r.ticker} | {r['name']} | {EN_DASH} | {EN_DASH} | {EN_DASH} | {EN_DASH} | {EN_DASH} | {r.badge if isinstance(r.badge, str) else EN_DASH} | {r.section} | {r.reason} |"
    ma = f"{num(r.ma200, dec)} {r.slope200} ({r.slope200_pct * 100:+.2f}%)"
    band = EN_DASH if r.last_band == "none" else f"{r.last_band} {_d(r.last_band_date)} @ {num(r.last_band_level, dec)}"
    lv = f"{num(r.support, dec)} / {num(r.resistance, dec)}"
    tags = [r.comparison] + (["trigger_hit"] if isinstance(r.trigger_hit, str) else []) + (["levels_stale"] if r.levels_stale is True else [])
    why = r.reason + (f"; {r.trigger_hit}" if isinstance(r.trigger_hit, str) else "")
    return (f"| {r.ticker} | {r['name']} | {num(r.close, dec)} | {ma} | {band} | {lv} | **{r.verdict}** | "
            f"{r.badge if isinstance(r.badge, str) else EN_DASH} | {', '.join(tags)} | {why} |")


HEADER = ("| Ticker | Name | Last close | MA200 (20d slope) | Last band event | Support / resistance | "
          "Mechanical | Badge | Classification | Rule that fired |\n|---|---|---:|---|---|---|---|---|---|---|")


def render_markdown(df: pd.DataFrame, asof) -> str:
    out = [f"# Trend engine – exceptions report, data as of {_d(asof)}", "",
           "Mechanical verdict (BUILD_SPEC §3.3) against the published badge. Facts and the rule that fired only.", ""]
    counts = df.section.value_counts()
    out.append("| Section | Count |\n|---|---:|")
    for s in ORDER + ["no_badge", "not_scored"]:
        if counts.get(s, 0):
            out.append(f"| {s} | {counts[s]} |")
    out.append("")
    for s in ORDER[:-1] + ["no_badge", "not_scored"]:
        part = df[df.section == s]
        if part.empty:
            continue
        out += [f"## {TITLES[s]} ({len(part)})", "", HEADER]
        out += [_row(r) for _, r in part.sort_values(["group", "ticker"], na_position="last").iterrows()]
        out.append("")
    out.append(f"## Agree: {int(counts.get('agree', 0))} instruments")
    out.append("")
    return "\n".join(out)
