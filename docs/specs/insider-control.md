# Positive control plan: does the same test find alpha in corporate insider purchases?

Status: draft, 2026-11-25. This plan fixes the sample, the test, and how the
result will be read before any insider return is computed. Changes after the
first estimate must be logged in `JOURNAL.md`, and the paper must say which
choices came after seeing results.

## Why a control

The primary result is a null: a portfolio that copies disclosed Congressional
purchases earns no four-factor alpha (`docs/specs/event-study.md`). A null can
mean there is nothing to find, or that the test is too weak to find it. A
control separates the two. Run the same procedure on a group that earlier
studies found earns abnormal returns after trading, and see whether it finds
them.

Corporate insiders are that group. Officers and directors who buy their own
company's stock in the open market have been found to earn positive abnormal
returns in studies of earlier periods (Seyhun 1986; Lakonishok and Lee 2001;
Jeng, Metrick and Zeckhauser 2003; Cohen, Malloy and Pomorski 2012). Their
filings carry the same kind of information as Congressional disclosures: a
trade date, a public filing date, and a ticker.

## Question

**C1.** Over the same years and with the same procedure as Q1, does a
portfolio that copies insider open-market purchases from the day after the
filing earn a positive four-factor alpha?

C1 is the only confirmatory test in this plan. Everything else is exploratory.

## Data

- **Insider trades.** The SEC's Insider Transactions Data Sets, quarterly
  files `2020q1` through `2026q1` (`form345.zip`). They hold every Form 4
  transaction as filed. The `2026q1` file catches filings for late-2025
  trades. The Wesleyan WRDS subscription does not include the Thomson Reuters
  insider tables (checked 2026-11-25: permission denied), which is why the
  SEC files are used. Filings are public records.
- **Prices and factors.** The same CRSP extract rules and the same Kenneth
  French factors as the event study. Returns end on 2025-12-31.
- **Matching to CRSP.** The ticker in the filing (`ISSUERTRADINGSYMBOL`) is
  matched to the `permno` whose record covers the transaction date, with the
  common-stock rules of the event study (`pipeline.crsp.link_events`).

## Sample

An event is one open-market purchase of a listed common stock by an officer or
director of the issuer, with:

- a Form 4 as originally filed (`DOCUMENT_TYPE = 4`; amendments and Form 5 are
  left out because their filing date is not when the trade became public);
- transaction code `P` and acquired (`TRANS_ACQUIRED_DISP_CD = A`);
- a security title containing "common" (case-insensitive);
- no equity swap involved;
- a positive share count and a positive price;
- a reporting owner whose relationship includes `Director` or `Officer`.
  Owners who are only ten-percent holders or "Other" are left out;
- a ticker that fits the event study's rule (one to five capital letters);
- a transaction date from 2020-01-01 to 2025-12-31;
- a filing date on or after the transaction date and no more than 365 days
  later, the same window as Q1.

Duplicates (same issuer, reporting owner, ticker and transaction date)
collapse to one event, so a purchase reported on several lines counts once.
No minimum trade size is applied. Every exclusion is counted in a
sample-flow table.

## Test

The calendar-time copy portfolio of Q1, unchanged: each stock enters on the
first trading day strictly after the filing date, is held for H trading days
with equal weight by stock, and the daily excess return is regressed on
market, size, value and momentum. The intercept is the alpha, with
Newey-West errors. H = 62 is the primary holding period; 20 and 125 are
secondary.

## Robustness

Two checks, both at H = 62:

- leave out purchases made in 2020;
- keep only purchases at $5 a share or more, since equal weighting gives
  low-priced stocks as much weight as large ones.

## How the result will be read

Decided now, before any return is seen.

- **The control detects an effect** if the H = 62 alpha is positive and its
  two-sided p-value is below 0.05. The paper then says the procedure finds
  abnormal returns in a group known to earn them, so the Congressional null
  is not simply a failure of the method. It will not say that the control
  proves Congress has no information.
- **The control does not detect an effect** if the alpha is not positive and
  significant. The paper then says the procedure could not detect the known
  effect in this period, and that the Congressional null is therefore less
  informative than it looked. It will not call the null stronger.
- The paper reports the control in both cases, next to the Congressional
  result, with the standard error of each alpha.
- The paper will not read the size of the insider alpha as a forecast of what
  Congress would earn. The groups differ in firm size, trade size, and how
  many stocks are held.

## Limits

- Insider purchases cluster in small, thinly traded stocks. An equal-weighted
  portfolio leans toward them, and transaction costs for those stocks are
  larger than the alpha may be. The control tests whether the method finds
  abnormal returns, not whether an investor could profit.
- Form 4 filings are due two business days after the trade, so the filing lag
  is much shorter than Congress's median of 13 days. That favors the insiders
  and is part of why the two results are not directly comparable.
- The SEC files hold what companies reported. Ticker symbols can be missing
  or stale, and events that fail to match CRSP are counted and dropped.

## Release

Release the code, the sample-flow table, and the cleaned list of insider
events (public records). Do not release price data.
