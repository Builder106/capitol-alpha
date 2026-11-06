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
