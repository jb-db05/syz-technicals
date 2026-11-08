"""Bloomberg price-export template: one sheet per ticker with a BDH formula (BUILD_SPEC §2.1, shape 2).

Each sheet shows its own dates, so instruments with shorter histories or other holiday
calendars can never be misaligned. Start / end dates live once, on the Settings sheet.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

NAVY, ORANGE, FONT = "202945", "FF6C0E", "Nunito Sans"
BDH_OPTIONS = ['"Days=W"', '"Fill=B"', '"Dates=S"', '"CshAdjNormal=Y"', '"CshAdjAbnormal=Y"', '"CapChg=Y"']
INVALID_SHEET_CHARS = set('[]:*?/\\')


def bdh_formula() -> str:
    return f'=BDH($D$1,"PX_LAST",Settings!$B$2,Settings!$B$3,{",".join(BDH_OPTIONS)})'


def build_template(universe: pd.DataFrame, out: str | Path, start: date, end: date) -> Path:
    head_font = Font(name=FONT, bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor=NAVY)
    body_font = Font(name=FONT, color=NAVY)
    wb = Workbook()

    ins = wb.active
    ins.title = "Instructions"
    lines = [
        ("Syz Research – Bloomberg price export for syz-technicals", True),
        ("", False),
        ("1. Open in Excel on a Bloomberg terminal. Each ticker sheet fills from cell A2 (dates in A, PX_LAST in B).", False),
        ("2. Adjust the start / end dates on the Settings sheet if needed (end = last completed trading day).", False),
        ("3. Wait until every sheet has finished loading (no '#N/A Requesting Data...').", False),
        ("4. Save as .xlsx and attach it to the Claude session. No paste-as-values needed – saved values are read.", False),
        ("Do not rename sheets: the sheet name is the ticker. Do not add derived columns (MAs etc.).", False),
        ("Holidays are left blank (Fill=B) on purpose – never use 'previous value' fill.", False),
        ("", False),
        ("Ticker", True), ]
    for i, (txt, bold) in enumerate(lines, start=1):
        c = ins.cell(i, 1, txt)
        c.font = Font(name=FONT, bold=bold, color=NAVY, size=14 if i == 1 else 11)
    r0 = len(lines)
    for j, h in enumerate(["Ticker", "Name", "Asset class", "Group"], start=1):
        c = ins.cell(r0, j, h)
        c.font, c.fill = head_font, head_fill
    for k, u in enumerate(universe.itertuples(index=False), start=r0 + 1):
        ins.cell(k, 1, u.ticker).hyperlink = f"#'{u.ticker}'!A1"
        ins.cell(k, 1).font = Font(name=FONT, color=ORANGE, underline="single")
        for j, v in enumerate([u.name, u.asset_class, u.group], start=2):
            ins.cell(k, j, None if pd.isna(v) else v).font = body_font
    for col, w in zip("ABCD", (22, 62, 14, 24)):
        ins.column_dimensions[col].width = w

    st = wb.create_sheet("Settings")
    st["A1"], st["B1"] = "Parameter", "Value"
    st["A2"], st["B2"] = "Start date", start
    st["A3"], st["B3"] = "End date", end
    for c in ("A1", "B1"):
        st[c].font, st[c].fill = head_font, head_fill
    for c in ("B2", "B3"):
        st[c].number_format = "yyyy-mm-dd"
        st[c].font = Font(name=FONT, bold=True, color=ORANGE)
    st["A2"].font = st["A3"].font = body_font
    st.column_dimensions["A"].width, st.column_dimensions["B"].width = 14, 14

    for u in universe.itertuples(index=False):
        t = str(u.ticker)
        if len(t) > 31 or set(t) & INVALID_SHEET_CHARS:
            raise ValueError(f"{t}: cannot be used as an Excel sheet name")
        ws = wb.create_sheet(t)
        for ref, v in (("A1", "Date"), ("B1", "PX_LAST"), ("C1", "Ticker"), ("D1", t)):
            ws[ref] = v
            ws[ref].font, ws[ref].fill = head_font, head_fill
        ws["D1"].fill = PatternFill("solid", fgColor=ORANGE)
        ws["A2"] = bdh_formula()
        ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 12, 14
        ws.column_dimensions["D"].width = 20
        ws.freeze_panes = "A2"
        ws.sheet_view.zoomScale = 100
        ws["A2"].alignment = Alignment(horizontal="left")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out
