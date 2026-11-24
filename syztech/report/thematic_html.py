"""Thematic Technical Review – interactive HTML page (charts alongside).

python -m syztech.report.thematic_html -> output/html_thematics/index.html
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
from PIL import Image

from ..charts.deck_chart import deck_chart
from ..trend.rules import INSUFFICIENT
from .sectorstyle import rotation_points
from .thematic import BENCH, MAX_PER_CLUSTER, Review, build_review, momentum_test, shortlist
from .weekly import VLABEL

ASSETS = Path(__file__).parent / "assets"
OUT = Path("output/html_thematics")
BADGES = ("Bullish", "Neutral+", "Neutral", "Neutral-", "Bearish_LM", "Bearish")


def _f(x, d=4):
    return None if x is None or pd.isna(x) else round(float(x), d)


def _s(x):
    return "" if x is None or (isinstance(x, float) and pd.isna(x)) else str(x)


def _slug(t):
    return t.replace(":", "_").replace(" ", "_").replace("/", "-")


class _Shim:
    """rotation_points wants an object with .series(ticker): the review's own series (themes and cluster composites)."""
    def __init__(self, rv: Review):
        self.rv = rv

    def series(self, t):
        return self.rv.bench if t == BENCH else self.rv.series[t]


def _row(r, img):
    return dict(v=_s(r.verdict), rule=_s(r.rule), s200=_s(getattr(r, "slope200", None)), rs=_s(getattr(r, "rel_state", None)),
                vs200=_f(getattr(r, "vs200", None)), c1=_f(getattr(r, "chg1m", None)), c3=_f(getattr(r, "chg3m", None)),
                c12=_f(getattr(r, "chg12m", None)), fh=_f(getattr(r, "from_hi52", None)), rs3=_f(r.rs3), rs6=_f(r.rs6), rs12=_f(r.rs12),
                mom=_f(r.mom, 2), rank=_f(r.mom_rank, 0), beta=_f(r.beta, 2), img=img)


def build(out_dir: Path = OUT, charts: bool = True, edition: str = "") -> Path:
    rv = build_review()
    out_dir = Path(out_dir)
    (out_dir / "charts").mkdir(parents=True, exist_ok=True)
    work = Path("output/thematics/charts")
    work.mkdir(parents=True, exist_ok=True)
    shutil.copy(ASSETS / "syz_logo.png", out_dir / "syz_logo.png")
    img = {}
    items = ([(r.ticker, r.name, r) for r in rv.themes.itertuples()] + [(r.ticker, r.name, r) for r in rv.anchors.itertuples()]
             + [(r.key, f"{r.cluster} – cluster composite", r) for r in rv.clusters.itertuples() if r.n > 1])
    if charts:
        for key, name, r in items:
            s = rv.series[key]
            png = work / f"{_slug(key)}.png"
            row = {"ticker": key if not key.startswith("cluster:") else f"Equal-weight composite of {r.n} themes", "name": name, "decimals": 1,
                   "support": r.support, "resistance": r.resistance, "support_origin": r.support_origin, "resistance_origin": r.resistance_origin}
            try:
                deck_chart(s, row, png, badge=r.verdict if r.verdict in BADGES else None, badge_kind="mechanical", benchmark=rv.bench,
                           benchmark_name="MSCI ACWI", page="a4")
            except Exception as e:                      # one bad series must not stop the run
                print(f"chart skipped: {key}: {e}")
                continue
            dst = out_dir / "charts" / f"{_slug(key)}.jpg"
            with Image.open(png) as im:
                im.convert("RGB").resize((1400, int(1400 * im.height / im.width)), Image.LANCZOS).save(dst, quality=84)
            img[key] = f"charts/{dst.name}"
    else:
        for key, _n, _r in items:
            p = out_dir / "charts" / f"{_slug(key)}.jpg"
            if p.exists():
                img[key] = f"charts/{p.name}"
    themes = [dict(t=r.ticker, n=r.name, cid=int(r.cid), sub=_s(r.sub), dups=_s(r.dups), **_row(r, img.get(r.ticker))) for r in rv.themes.itertuples()]
    anchors = [dict(t=r.ticker, n=r.name, type=r.type, dups=_s(r.dups), **_row(r, img.get(r.ticker))) for r in rv.anchors.itertuples()]
    clusters = [dict(t=r.key, cid=int(r.cid), n=r.cluster, parent=_s(r.parent), single=bool(r.single), size=int(r.n), nb=int(r.n_bull), nr=int(r.n_rising),
                     no=int(r.n_out), nok=int(r.n_ok), **_row(r, img.get(r.key))) for r in rv.clusters.itertuples()]
    a, w = shortlist(rv)
    multi = [r.key for r in rv.clusters.itertuples() if r.n > 1]
    pts = rotation_points(_Shim(rv), multi, BENCH)
    rot = []
    for t, g in pts.groupby("ticker"):
        g = g.sort_values("k", ascending=False)
        rot.append(dict(t=t, xy=[[round(float(x), 3), round(float(y), 3)] for x, y in zip(g.x, g.y)]))
    test = momentum_test(rv)
    bn = rv.bench
    from .thematic import read
    acwi = read(bn, None)
    d = rv.asof
    data = dict(asof=f"{d.day} {d:%B %Y}", edition=edition or f"{d.day} {d:%B %Y}", vlabel=VLABEL, themes=themes, clusters=clusters, anchors=anchors,
                short=list(a.ticker), watch=list(w.ticker), cap=MAX_PER_CLUSTER, rot=rot,
                acwi=dict(v=acwi["verdict"], s200=acwi.get("slope200"), vs200=_f(acwi.get("vs200")), c3=_f(acwi.get("chg3m")), c12=_f(acwi.get("chg12m"))),
                n_all=len(rv.themes) + len(rv.anchors) + sum(len(v) for v in rv.dropped.values()), n_dup=sum(len(v) for v in rv.dropped.values()),
                window=[f"{x.day} {x:%B %Y}" for x in rv.window],
                test=dict(dates=test["dates"], first=f"{test['first']:%B %Y}", last=f"{test['last']:%B %Y}",
                          f1={k: _f(v, 5) for k, v in test["f1"].items()}, f3={k: _f(v, 5) for k, v in test["f3"].items()}))
    bt = Path("output/thematics/backtest.json")               # written by syztech.research.theme_backtest (about three minutes)
    data["bt"] = json.loads(bt.read_text()) if bt.exists() else None
    html = (ASSETS / "thematic.html").read_text(encoding="utf-8").replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False))
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"written: {out_dir / 'index.html'} – {len(themes)} themes, {len(anchors)} anchors, {len(clusters)} clusters, {len(img)} charts, shortlist {len(a)}, watch {len(w)}")
    return out_dir / "index.html"


if __name__ == "__main__":
    import sys
    build(charts="--no-charts" not in sys.argv)
