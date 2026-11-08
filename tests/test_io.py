"""Loader behaviour on synthetic Bloomberg-shaped workbooks (BUILD_SPEC §2.1)."""
import numpy as np
import pandas as pd

from syztech.cli import main
from syztech.io.bloomberg_prices import load_prices
from syztech.io.universe import COLUMNS, draft, load_universe
from syztech.trend.score import score_universe
from tests.fixtures import series as fx


def _wide_book(path):
    dates = pd.bdate_range("2025-01-01", periods=30)
    a = np.linspace(100.25, 110.75, 30)
    rounded = np.round(np.linspace(7000, 7300, 30))
    with pd.ExcelWriter(path) as xw:
        rows = [["Syz price export", None, None], ["Date", "SPX Index", "CAC Index"],
                [None, "S&P 500 INDEX", "CAC 40 INDEX"]]
        for i, d in enumerate(dates):
            rows.append([d, a[i], rounded[i]])
        rows[5][1] = "#N/A N/A"                    # non-numeric cell
        rows.append([dates[-1], 999.0, 7300.0])    # duplicate date – last kept
        pd.DataFrame(rows).to_excel(xw, sheet_name="Prices", header=False, index=False)
        pd.DataFrame({"Date": dates, "PX_LAST": a}).to_excel(xw, sheet_name="EURUSD Curncy", index=False)
        pd.DataFrame({"Name": ["x"], "R": [1.0], "S": [2.0]}).to_excel(
            xw, sheet_name="Momentum Equities, Forex, Commo", index=False)


def test_both_shapes_and_defects(tmp_path):
    _wide_book(tmp_path / "export.xlsx")
    res = load_prices(tmp_path)
    assert set(res.tickers) == {"SPX Index", "CAC Index", "EURUSD Curncy"}
    spx = res.reports["SPX Index"]
    assert spx.name == "S&P 500 INDEX"
    assert spx.non_numeric == 1 and spx.duplicate_dates == 1
    assert spx.bars == 29                                    # 30 dates − 1 #N/A; duplicate collapsed
    assert res.series("SPX Index").iloc[-1] == 999.0         # keep last
    assert res.reports["CAC Index"].rounded_to_units
    assert not spx.rounded_to_units
    assert any("200-day MAs" in n for n in res.file_notes)   # helper sheet never read as price
    s = res.series("EURUSD Curncy")
    assert s.index.is_monotonic_increasing and len(s) == 30


def test_no_forward_fill(tmp_path):
    dates = pd.bdate_range("2025-01-01", periods=10)
    v = [1.0, 2.0, np.nan, np.nan, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    pd.DataFrame({"Date": dates, "X Index": v}).to_excel(tmp_path / "p.xlsx", index=False)
    s = load_prices(tmp_path).series("X Index")
    assert len(s) == 8 and dates[2] not in s.index


def test_universe_draft_and_end_to_end(tmp_path):
    s, kw = fx.silver_close_below_trigger()
    pd.DataFrame({"Date": s.index, "XAG Curncy": s.to_numpy(), "EURUSD Curncy": s.to_numpy() / 25}).to_excel(
        tmp_path / "p.xlsx", index=False)
    res = load_prices(tmp_path)
    uni = draft(res.tickers)
    assert list(uni.columns) == COLUMNS
    assert dict(zip(uni.ticker, uni.asset_class)) == {"XAG Curncy": "commodity", "EURUSD Curncy": "fx"}
    assert dict(zip(uni.ticker, uni.decimals)) == {"XAG Curncy": 1, "EURUSD Curncy": 2}
    uni.loc[uni.ticker == "XAG Curncy", "support"] = 27.4
    uni.loc[uni.ticker == "XAG Curncy", "standing_position"] = "Bullish"
    uni = pd.concat([uni, pd.DataFrame([{"ticker": "MISSING Index"}])], ignore_index=True)
    uni.to_csv(tmp_path / "u.csv", index=False)
    u, problems = load_universe(tmp_path / "u.csv")
    assert problems == []
    out = score_universe(res, u).set_index("ticker")
    assert out.loc["XAG Curncy", "verdict"] == "Bearish"
    assert out.loc["XAG Curncy", "levels"] == "partial"
    assert out.loc["MISSING Index", "verdict"] == "insufficient_data"
    # CLI exits non-zero on insufficient_data unless --allow-partial
    import os
    cwd = os.getcwd(); os.chdir(tmp_path)
    try:
        assert main(["trend", "--prices", ".", "--universe", "u.csv"]) == 1
        assert main(["trend", "--prices", ".", "--universe", "u.csv", "--allow-partial"]) == 0
        assert (tmp_path / "output").exists()
    finally:
        os.chdir(cwd)


def test_price_template_round_trip(tmp_path):
    """The template's ticker sheets are read as shape-2 exports once Bloomberg has filled them."""
    from datetime import date
    from openpyxl import load_workbook
    from syztech.io.template import build_template
    uni = draft(["SPX Index", "EURUSD Curncy"])
    out = build_template(uni, tmp_path / "t.xlsx", date(2019, 1, 1), date(2026, 11, 6))
    wb = load_workbook(out)
    assert wb.sheetnames == ["Instructions", "Settings", "SPX Index", "EURUSD Curncy"]
    assert wb["SPX Index"]["A2"].value.startswith('=BDH($D$1,"PX_LAST",Settings!$B$2,Settings!$B$3')
    assert '"Fill=B"' in wb["SPX Index"]["A2"].value and '"Dates=S"' in wb["SPX Index"]["A2"].value
    # simulate Bloomberg having filled one sheet (values replace the formula)
    ws = wb["SPX Index"]
    for i, d in enumerate(pd.bdate_range("2026-01-05", periods=5), start=2):
        ws.cell(i, 1, d.to_pydatetime()); ws.cell(i, 2, 6000.0 + i)
    wb.save(out)
    res = load_prices(tmp_path)
    assert res.series("SPX Index").tolist() == [6002.0, 6003.0, 6004.0, 6005.0, 6006.0]
    assert not any("Instructions" in n or "Settings" in n for n in res.file_notes)


def test_bloomberg_error_is_reported(tmp_path):
    with pd.ExcelWriter(tmp_path / "p.xlsx") as xw:
        pd.DataFrame([["Date", "PX_LAST"], ["#N/A Invalid Security", None]]).to_excel(
            xw, sheet_name="BAD Index", header=False, index=False)
    rep = load_prices(tmp_path).reports["BAD Index"]
    assert rep.bars == 0 and "Bloomberg error: #N/A Invalid Security" in rep.issues
