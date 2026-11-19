"""Bundle the syztech code behind the sector special report into one self-contained script.

    python tools/bundle_sector_report.py  ->  handoff/sp500_it_report/build_sector_report.py

The library part is copied verbatim from the package (top-level definitions picked by name, in dependency
order); only names that collide between modules are renamed, and asset paths point at ASSET_DIR.
Re-run after any change to the package so the handoff stays identical to what the repo produces.
"""
from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "syztech"
OUT = ROOT / "handoff" / "sp500_it_report" / "build_sector_report.py"

R_COLOURS = {"MINT": "R_MINT", "ORANGE": "R_ORANGE", "AMBER": "R_AMBER", "NAVY": "R_NAVY", "GREY": "R_GREY"}
T_NAMES = {"NAVY": "T_NAVY", "ORANGE": "T_ORANGE", "FONT": "T_FONT"}
ALL = None
# (module, names to keep or ALL, renames, section title)
MODULES = [
    ("fmt", ["EN_DASH", "num"], {}, "Number formatting"),
    ("indicators/ma", ALL, {}, "Indicators – moving average"),
    ("indicators/slope", ALL, {}, "Indicators – slope of an average"),
    ("indicators/bands", ALL, {}, "Indicators – 100-day high / low band"),
    ("indicators/crosses", ALL, {}, "Indicators – golden / death crosses"),
    ("indicators/rs", ALL, {}, "Indicators – relative strength"),
    ("indicators/breadth", ALL, {}, "Indicators – breadth"),
    ("io/bloomberg_prices", ALL, {}, "Bloomberg price export reader"),
    ("io/universe", ["COLUMNS", "OPTIONAL_COLUMNS", "ASSET_CLASSES", "BADGES", "load_universe", "with_benchmarks"], {},
     "Universe file"),
    ("io/template", ALL, T_NAMES, "Bloomberg price template writer"),
    ("io/syz_lists", ALL, {}, "Syz list membership (display only)"),
    ("trend/rules", ALL, {}, "Trend engine – verdict rules (BUILD_SPEC §3)"),
    ("trend/score", ALL, {}, "Trend engine – scoring a universe"),
    ("charts/syz_style", ALL, {}, "Syz chart style and the verdict badge"),
    ("charts/deck_chart", ALL, {}, "Publication chart (A4 page)"),
    ("report/weekly", ["NAVY", "MINT", "VCOL", "VGLYPH", "VLABEL", "SOURCE", "NUMERIC", "L_COVER", "X0", "rgb",
                       "instrument_table", "triggers", "Deck", "text", "box", "source", "pct", "table", "verdict_style",
                       "full_page_chart", "chart_image"], R_COLOURS, "PowerPoint helpers"),
    ("report/listdoc", ["RS_ORDER", "V_ORDER", "_bucket"], R_COLOURS, "Sort orders"),
    ("report/sectordoc", ALL, R_COLOURS, "Sector report – PowerPoint"),
    ("report/sector_html", ALL, {}, "Sector report – HTML"),
]
PATH_SUBS = [
    ('Path(__file__).parent / "fonts"', 'ASSET_DIR / "fonts"'),
    ('(ASSETS / "sector_report.html").read_text(encoding="utf-8")', "HTML_TEMPLATE"),
    ('ASSETS / "syz_logo.png"', 'ASSET_DIR / "syz_logo.png"'),
]
SKIP = {"ASSETS", "_FONT_DIR_UNUSED"}


def _names(node) -> list[str]:
    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
        return [node.name]
    if isinstance(node, ast.Assign):
        return [x.id for t in node.targets for x in ast.walk(t) if isinstance(x, ast.Name)]
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [node.target.id]
    return []


def _rename(src: str, ren: dict) -> str:
    if not ren:
        return src
    toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    out = [(t.type, ren.get(t.string, t.string)) if t.type == tokenize.NAME else (t.type, t.string) for t in toks]
    # untokenize in full mode keeps positions: rebuild by replacing exact spans
    lines = src.splitlines(keepends=True)
    for t in reversed(toks):
        if t.type == tokenize.NAME and t.string in ren:
            (r, c0), (_, c1) = t.start, t.end
            ln = lines[r - 1]
            lines[r - 1] = ln[:c0] + ren[t.string] + ln[c1:]
    return "".join(lines)


def main() -> None:
    imports, body = {}, []
    for mod, keep, ren, title in MODULES:
        src = (PKG / f"{mod}.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        parts = []
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and (node.level or node.module == "__future__"):
                    continue
                key = ast.unparse(node)
                imports.setdefault(key, None)
                continue
            if isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant):
                continue                                     # module docstring
            if isinstance(node, ast.Expr):                   # e.g. matplotlib.use("Agg")
                imports.setdefault(ast.unparse(node), None)
                continue
            names = _names(node)
            if set(names) & SKIP:
                continue
            if keep is not ALL and not (set(names) & set(keep)):
                continue
            start = node.lineno - 1
            if getattr(node, "decorator_list", None):
                start = min(d.lineno for d in node.decorator_list) - 1
            seg = "".join(src.splitlines(keepends=True)[start:node.end_lineno])
            parts.append(_rename(seg, ren))
        text = "\n\n".join(p.rstrip() for p in parts)
        for a, b in PATH_SUBS:
            text = text.replace(a, b)
        body.append(f"# {'─' * 108}\n# {title}  (syztech/{mod}.py)\n# {'─' * 108}\n{text}\n")
    head = (ROOT / "tools" / "sector_report_header.py").read_text(encoding="utf-8")
    pipe = (ROOT / "tools" / "sector_report_pipeline.py").read_text(encoding="utf-8")
    html = (PKG / "report" / "assets" / "sector_report.html").read_text(encoding="utf-8")
    assert "'''" not in html and not html.rstrip().endswith("\\")
    plain, frm = set(), {}
    for k in imports:
        n = ast.parse(k).body[0]
        if isinstance(n, ast.Import):
            plain.add(k)
        elif isinstance(n, ast.ImportFrom):
            frm.setdefault(n.module, set()).update(a.name if not a.asname else f"{a.name} as {a.asname}" for a in n.names)
    plain.discard("import matplotlib")
    rest = sorted(plain) + [f"from {m} import {', '.join(sorted(v))}" for m, v in sorted(frm.items())]
    lib = ("\n# " + "═" * 108 + "\n# LIBRARY – copied from the syztech package (do not edit here)\n# " + "═" * 108 + "\n"
           + "import matplotlib\nmatplotlib.use(\"Agg\")\n" + "\n".join(rest) + "\n\n" + "\n\n".join(body)
           + "\n\n# HTML page template (syztech/report/assets/sector_report.html); data is injected at /*__DATA__*/null\n"
           + "HTML_TEMPLATE = r'''" + html + "'''\n")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(head + lib + pipe, encoding="utf-8")
    print(f"written: {OUT} ({len((head + lib + pipe).splitlines())} lines)")


if __name__ == "__main__":
    main()
