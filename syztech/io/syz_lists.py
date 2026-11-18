"""Syz list membership (display only, never part of a verdict): master list and Focus List workbook.

US stocks are matched on the ticker: the master list ID for North America is the ticker itself, the Focus List ID
is ticker-country (e.g. AAPL-USA). Every match is also checked on the first word of the company name, and the
mismatches are returned so that no stock is tagged on a ticker collision.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

MASTER, FOCUS = "Master list", "Focus List"
US_SUFFIX = re.compile(r"\s(UW|UN|UQ|UA|UR|UP|US)\s+Equity$")


def _first(name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(name).upper().split()[0]) if isinstance(name, str) and name.strip() else ""


def load_lists(path: str | Path) -> dict[str, dict[str, str]]:
    """{list name: {ticker root: company name as in the workbook}}."""
    m = pd.read_excel(path, sheet_name="Master_list_F")
    m = m[m["Grouping"].astype(str).str.strip() == "North America"]
    f = pd.read_excel(path, sheet_name="Focus List").dropna(subset=["FACTSET ID"])
    f = f[f["COUNTRIES"].astype(str).str.strip() == "United States"]
    return {MASTER: {str(i).strip().lstrip("*"): n for i, n in zip(m["Factset ID"], m["Name Security"])},
            FOCUS: {str(i).strip().split("-")[0]: n for i, n in zip(f["FACTSET ID"], f["COMPANY_NAME"])}}


def tag_universe(universe: pd.DataFrame, lists: dict[str, dict[str, str]], aliases: dict[str, str] | None = None
                 ) -> tuple[pd.Series, list[str]]:
    """Series ticker -> '; '-joined list names ('' when none), plus name mismatches left untagged."""
    aliases = aliases or {}
    tags, issues = {}, []
    for t, nm in zip(universe.ticker, universe.name):
        found = []
        if US_SUFFIX.search(t):
            root = t.split()[0]
            for lst, ids in lists.items():
                if root in ids:
                    theirs = _first(ids[root])
                    if theirs in (_first(nm), _first(aliases.get(t, ""))) or _first(nm) in _first(ids[root]):
                        found.append(lst)
                    else:
                        issues.append(f"{t} ({nm}) vs {lst} '{ids[root]}': name differs, not tagged")
        tags[t] = "; ".join(found)
    return pd.Series(tags), issues
