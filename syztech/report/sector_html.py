"""HTML version of the sector special report: one page, data embedded as JSON, charts as files next to it.

Same numbers as the PowerPoint (built from the same table); the page only filters, sorts and draws.
"""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import pandas as pd
from PIL import Image

from .sectordoc import SHORT_IND, trigger_watch
from .weekly import VLABEL

ASSETS = Path(__file__).parent / "assets"


def _f(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)


def _s(x):
    return x if isinstance(x, str) else ""


def _slug(t: str) -> str:
    return t.replace(" ", "_").replace("/", "-")


def _row(r, charts):
    return dict(t=r.ticker, n=_s(r.name), ind=_s(getattr(r, "industry", None)), ish=SHORT_IND.get(_s(getattr(r, "industry", None)), _s(getattr(r, "industry", None))),
                b=_s(getattr(r, "bucket", None)), c=_f(r.close), d=int(r.decimals), s200=_s(r.slope200),
                vs200=_f(r.vs200), c1=_f(r.chg1m), c3=_f(r.chg3m), c12=_f(r.chg12m), fh=_f(r.from_hi52),
                rs=_s(r.rs_trend), rs3=_f(r.rs_chg63), v=_s(r.verdict), rule=_s(getattr(r, "rule", None)),
                hi52=_f(r.hi52), lo52=_f(r.lo52), hi100=_f(r.hi100), lo100=_f(r.lo100),
                img=f"charts/{_slug(r.ticker)}.jpg" if r.ticker in charts else None,
                lists=[x.strip() for x in _s(getattr(r, "syz_lists", None)).split(";") if x.strip()])


def build_sector_html(stocks: pd.DataFrame, sector: pd.Series, charts: dict, out_dir: Path, *, title: str, edition: str,
                      asof: str, bench: str, sector_name: str, insufficient: list[str], draft: bool = True, lists_asof: str = "") -> Path:
    out_dir = Path(out_dir)
    (out_dir / "charts").mkdir(parents=True, exist_ok=True)
    for t, src in charts.items():
        dst = out_dir / "charts" / f"{_slug(t)}.jpg"
        with Image.open(src) as im:
            im.convert("RGB").resize((1400, int(1400 * im.height / im.width)), Image.LANCZOS).save(dst, quality=84)
    shutil.copy(ASSETS / "syz_logo.png", out_dir / "syz_logo.png")
    tw = trigger_watch(stocks)
    data = dict(
        title=title, edition=edition, asof=asof, bench=bench, sector_name=sector_name, draft=draft,
        insufficient=insufficient, vlabel=VLABEL, lists_asof=lists_asof,
        sector=_row(sector, charts),
        stocks=[_row(r, charts) for r in stocks.itertuples()],
        triggers=[dict(t=r.ticker, n=r.name, c=_f(r.close), d=int(r.decimals), kind=_s(r.kind), level=_f(r.level),
                       dist=_f(r.dist), v=_s(r.verdict)) for r in tw.itertuples()],
    )
    html = (ASSETS / "sector_report.html").read_text(encoding="utf-8")
    html = html.replace("__TITLE__", f"{sector_name} Technicals").replace(
        "/*__DATA__*/null", json.dumps(data, ensure_ascii=False, allow_nan=False))
    out = out_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    return out
