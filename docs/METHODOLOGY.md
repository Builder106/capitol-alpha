# CapitolAlpha Methodology Guide

This document details the data normalization heuristics, ticker resolution rules, and financial asset pricing assumptions used in the CapitolAlpha pipeline.

## 1. Data Normalization & Ingestion

Congressional stock disclosures are published under two distinct formats:

- **Senate PTRs** (`efdsearch.senate.gov`): Digitized HTML tables with standard fields (`Transaction Date`, `Owner`, `Asset Name`, `Ticker`, `Amount`). Scraped via Playwright form interaction with a fallback JSON cache.
- **House PTRs** (`disclosures-clerk.house.gov`): PDF scans containing structured tables. Extracted using `pdfplumber` table extraction and DataTables JavaScript execution overrides (`dt.page.len(-1).draw()`).

### Ticker Resolution & Corporate Entity Mapping Heuristics

Raw filings frequently omit standard ticker symbols or corporate entity identifiers (e.g. listing "Common Stock - Apple Inc." or "OWENS & MINOR Rate/Coupon: 3.875%"). The normalization and entity linking modules (`pipeline/entity_linking.py` and `pipeline/merge_to_csv.py`):

1. **Format Validation**: Validates tickers against standard 1–5 character exchange symbols (including share class suffixes like `.A`, `.B`, `-A`, `-B`).
2. **Regex Extraction**: Extracts embedded tickers from asset descriptions using parenthesized `(TICKER)`, bracketed `[TICKER]`, leading prefix `TICKER - Company`, or explicit label `Ticker: TICKER` patterns.
3. **Corporate Entity Lookup**: Maps known corporate entity names to canonical tickers and standardized corporate entity titles (e.g., `Apple Inc.` -> `AAPL`, `The Boeing Company` -> `BA`, `Microsoft Corporation` -> `MSFT`).
4. **Descriptive Entity Normalization**: Strips descriptive prefixes (`Common Stock`, `Shares of`, `Option on`), share class notations, HTML markup, and transaction annotations to produce clean corporate entity names for unmapped equities.
5. **Non-Equity Exclusion**: Excludes non-equity assets (municipal bonds, treasury notes/bills, corporate debentures with coupon/maturity metadata, cryptocurrencies, and scanned PDF placeholder notices) from equity ticker resolution.

## 2. Risk Adjustment Models

### Single-Factor CAPM (Jensen's Alpha)

Returns are measured over 30, 90, and 180-day buy-and-hold windows following disclosure:

$$\alpha = R_i - [R_f + \beta (R_m - R_f)]$$

Where $R_i$ represents the 90-day ROI of Congressional stock purchases and $R_m$ represents the S&P 500 benchmark return over the identical window.

### Fama-French Multi-Factor Adjustment

To test whether outperformance is driven by systematic factor exposures rather than information edge, returns are evaluated against small-cap ($SMB$) and value ($HML$) factor adjustments:

$$\alpha_{FF} = \alpha_{CAPM} - (s \cdot SMB + h \cdot HML)$$

## 3. Caveats & Ethical Guardrails

1. **Disclosure Lag**: Filings occur up to 30–45 days after trade execution.
2. **Selection Bias**: Only clean equity trades matching market price history are benchmarked.
3. **Public Data Ethos**: Automated ingestion processes legally public disclosures without bypassing CAPTCHAs or non-public endpoints.

## 4. Committee Trade Correlation Analysis

`pipeline/committee_signals.py` is a separate, offline analysis of the canonical
trade CSV. It does not change ingestion, the submitted research findings, or the
canonical schema. Its prerequisites are normalized trades and three explicit
reference CSVs supplied by the operator:

| Reference | Required columns | Meaning |
| --- | --- | --- |
| Assignments | `chamber,legislator_name,committee,start_date,end_date` | Historical membership intervals; dates are `YYYY-MM-DD`, both endpoints inclusive. A blank end date means ongoing membership. |
| Ticker sectors | `ticker,sector` | One sector per ticker. Conflicting mappings fail validation. |
| Committee sectors | `chamber,committee,sector` | Explicit committee jurisdictions; a committee may cover multiple sectors. |

Use public, dated membership records and a documented sector taxonomy. Archive
reference inputs with their source and retrieval date alongside each analysis.
No current committee roster or sector classification is inferred or downloaded.
All keys are compared after whitespace normalization and case folding; there is
no fuzzy name matching. The member key is `(chamber,legislator_name)`, so names
must be reconciled to the canonical trade table before running. Committee keys
are `(chamber,committee)`. Output labels use these normalized keys.

The assignment table must cover the historical membership of **all members in
the trade cohort**, including changes of committee and departures. An unmatched
member is counted as a nonmember. An incomplete roster or a name mismatch will
therefore bias the comparison. A committee with no matching members produces
`insufficient_data`. Empty reference tables are valid and do not invent matches.

### Eligibility and timing

The disclosure window is `[as_of - (lookback_days - 1), as_of]`, inclusive, with
90 days by default. Only canonical `Purchase` and `Sale` records with a known
ticker sector, member name, House/Senate chamber, and valid transaction and
disclosure dates count. Trades disclosed after `as_of`, disclosures before their
transactions, exchanges, unmapped assets, and malformed/missing dates are
excluded. The output's `eligible_trades` is the denominator after these filters
for that chamber; it is not the number of raw input records.

Membership is evaluated on the **transaction date**, even if disclosure occurs
after departure. An older transaction first disclosed inside the window counts;
an older disclosure does not. Exact duplicate input records are removed using
all supplied trade columns. Distinct canonical rows remain distinct, including
different owners or report links. Duplicate or overlapping assignment intervals
never multiply a trade. Multiple committees and jurisdiction sectors are
reported separately; their counts must not be added as unique trades.

### Association and directional signals

For each committee/jurisdiction sector, the comparison cohort consists of all
eligible trades in the same chamber. The exported contingency counts are:

| | Target sector | Other mapped sectors |
| --- | --- | --- |
| Committee member at transaction time | `a = member_sector_trades` | `b = member_other_trades` |
| Nonmember at transaction time | `c = nonmember_sector_trades` | `d = nonmember_other_trades` |

The descriptive association is the phi coefficient:

`phi = (a*d - b*c) / sqrt((a+b)*(c+d)*(a+c)*(b+d))`

Positive values indicate a greater concentration of sector trades among members;
negative values indicate a lower concentration. A zero denominator yields a
missing value, rather than an assumed zero correlation. Each jurisdiction gets
one output row, including when no eligible trades exist. No jurisdictions yields
an empty output with the same column headers.

Within the `a` member/sector trades, `net_purchase_ratio` is
`(purchases - sales) / (purchases + sales)`, ranging from -1 to +1. No trades
yields a missing ratio. With at least `min_trades` observations (default 3), the
`signal` is `buy` for a positive ratio, `sell` for a negative ratio, or `neutral`
for zero. Below the threshold it is `insufficient_data`; the observed ratio is
still reported. Counts and ratios weight each disclosure transaction equally;
**no amount midpoint or dollar weighting is used**.

These are descriptive activity signals, not return forecasts, statistical
significance tests, evidence of insider knowledge, or trading execution. Trades
from one member are not independent observations. Results depend on roster
completeness, mapped-sector coverage, disclosure delays, and the selected window.
The disclosure cutoff prevents use of later filings, but retrospective sector
maps and membership corrections can still introduce hindsight. Historical
evaluation requires reference snapshots available at each evaluation date;
the command does not certify those inputs as point-in-time data.
