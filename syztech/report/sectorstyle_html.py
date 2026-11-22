"""HTML version of the sectors & style review: one page, data embedded as JSON, charts as files next to it.

Same numbers as the PowerPoint (built from the same table); the page draws the heatmap, the tables and
interactive rotation maps from the JSON.
"""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import pandas as pd
from PIL import Image

from .sectorstyle import BENCH_NAMES, MAP_LABELS, RATIOS, REGION_NAME, REGIONS, SECTOR_KEYS, key_readings, short_name
from .weekly import VLABEL

ASSETS = Path(__file__).parent / "assets"


def _f(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)


def _s(x):
    return x if isinstance(x, str) else ""


def _slug(t: str) -> str:
    return t.replace(" ÷ ", "_over_").replace(" ", "_").replace("/", "-")


def build_sector_style_html(df: pd.DataFrame, charts: dict, points: dict, out_dir: Path, *, edition: str, asof: str,
                            dropped: list[str], draft: bool = True) -> Path:
    out_dir = Path(out_dir)
    (out_dir / "charts").mkdir(parents=True, exist_ok=True)
    img = {}
    for t, src in charts.items():
        dst = out_dir / "charts" / f"{_slug(t)}.jpg"
        with Image.open(src) as im:
            im.convert("RGB").resize((1400, int(1400 * im.height / im.width)), Image.LANCZOS).save(dst, quality=84)
        img[t] = f"charts/{dst.name}"
    shutil.copy(ASSETS / "syz_logo.png", out_dir / "syz_logo.png")
    rows = []
    for r in df.itertuples():
        sn = short_name(_s(r.name))
        rows.append(dict(t=r.ticker, n=_s(r.name), sn=sn, ml=MAP_LABELS.get(sn, sn), g=_s(r.group), reg=_s(r.region),
                         sk=_s(r.sector_key), c=_f(r.close), d=int(r.decimals), s200=_s(r.slope200), vs200=_f(r.vs200),
                         c1=_f(r.chg1m), c3=_f(r.chg3m), c12=_f(r.chg12m), fh=_f(r.from_hi52), rs=_s(r.rs_trend),
                         rs3=_f(r.rs_chg63), v=_s(r.verdict), rule=_s(getattr(r, "rule", None)),
                         b=BENCH_NAMES.get(_s(r.benchmark), _s(r.benchmark)), img=img.get(r.ticker)))
    maps = {}
    for key, (pts, bench) in points.items():
        series = []
        for t, g in pts.groupby("ticker"):
            g = g.sort_values("k", ascending=False)
            series.append(dict(t=t, xy=[[round(float(x), 3), round(float(y), 3)] for x, y in zip(g.x, g.y)]))
        maps[key] = dict(bench=BENCH_NAMES.get(bench, bench), series=series)
    nb_reg, out_reg, cols = key_readings(df)
    data = dict(
        edition=edition, asof=asof, draft=draft, vlabel=VLABEL, dropped=dropped, rows=rows, maps=maps,
        readings=[dict(h=h, lines=ls) for h, ls in cols], nb_reg=nb_reg, out_reg=out_reg,
        regions=[dict(reg=reg, name=REGION_NAME[reg], bench=bench, bname=bname, sg=sg, ig=ig or "", styg=styg,
                      ib="SXXP Index" if reg == "Europe" else bench, ibn="Stoxx 600" if reg == "Europe" else bname,
                      ilabel="Stoxx 600 supersectors" if reg == "Europe" else "S&P 500 industry groups")
                 for reg, bench, bname, sg, ig, styg in REGIONS],
        ratios=[dict(name=n, num=a, den=b) for _, _, _, n, a, b in RATIOS],
        sector_keys=[[k, n] for k, n in SECTOR_KEYS],
    )
    html = (ASSETS / "sector_style.html").read_text(encoding="utf-8")
    html = html.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, allow_nan=False))
    out = out_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    return out
