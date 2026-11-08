# CLAUDE.md – syz-technicals

Read `BUILD_SPEC.md` before any change. It is the specification; this file only sets working rules.

## Who you work for
Florian Marini, CFA, CMT – Head of Research, Syz Private Banking. Senior technical analyst, not a developer. Explain decisions in analyst terms, keep code explanations short, never assume he will debug Python himself.

## Working rules
- Build in the order of the spec: Module 1 (trend engine) to its Definition of done, then Module 2, then Module 3. Do not start a later module early.
- Pure technical analysis: no fundamentals, macro series or news enter any rule or output.
- Bloomberg exports in `data/` are the only data source in the production path. Never fetch external data without being asked; never fill, extrapolate or invent values – return `insufficient_data` with the missing input named.
- Every verdict rule in §3 of the spec has a test in `tests/test_trend_rules.py`. Change a rule and its test together. `pytest` must pass before every commit.
- When a result contradicts the spec, or the spec is silent, stop and ask one precise question – do not pick a default silently. The known open decision is the flat-200-day branch (§3.3); implement the default and flag it.
- Keep `legacy/` untouched. Do not refactor it.
- Commit small, descriptive commits. Branch names `feat/trend-engine`, `feat/ledger`, `feat/regime`.

## Style conventions (outputs, charts, text)
- Nunito Sans everywhere; Syz colours: Mint `#3BAF90` bullish, Blueberry `#4B5F80` neutral, Mulberry `#AC5D85` bearish, orange `#FF6C0E → #FFA400`, navy `#202945`.
- En dashes only (U+2013). Decimals: 1 for equities/commodities/crypto, 2 for FX and yields, 4 where `universe.csv` says so.
- Chart source line: `Sources : Syz Research, Bloomberg`. Never name any external research provider in any output.
- Reports state facts and the rule that fired; no interpretation prose – the analyst writes that.

## Environment
Python 3.11+, pandas, numpy, openpyxl, matplotlib, pytest. Trading-day integer axis for all computations and charts.
