# Event study plan: do disclosed Congressional purchases beat the market?

Status: draft, 2026-11-10. This plan fixes the sample, the model, and the
tests before any new return is computed. Changes after the first estimate
must be logged in `JOURNAL.md` with the reason, and the paper must say which
choices came after seeing results.

## Why the published result is being redone

An audit of the current headline (+2.58% over 90 days, p = 0.013, n = 220)
found these problems:

1. **The committed dataset is a stub.** Commit `aac906f` replaced
   `data/legislative_trades.csv`, `house_trades.csv`, and `senate_trades.csv`
   with three-line test output. The last full dataset is
   `data/legislative_trades.csv` at commit `821d6e5` (16,202 rows, SHA-256
   `c1e6526c7d8954094d2fa2859938b7308b1f512c7cf0634bb2c1a3f8ece87fb2`).
2. **That file needs `skipinitialspace=True` to parse.** Fields are padded,
   so a default CSV reader splits quoted names such as "Beyond Meat, Inc."
   and shifts later columns.
3. **The House was left out.** The notebook selects purchases with
   `Purchase|buy`. The House codes purchases as `P`, so all 7,040 House
   purchase rows were dropped. The published sample is Senate only.
4. **Only the 50 most-traded tickers were priced.** That, plus point 3, is
   where n = 220 comes from. The README's explanation (trades with "clear
   ticker symbols") is not what the code does.
5. **Returns start at the transaction date.** `docs/METHODOLOGY.md` says
   returns follow disclosure. Transaction-date returns measure what the
   member knew; nobody else could trade on them until disclosure.
6. **The "alpha" is not risk-adjusted.** The notebook reports trade return
   minus SPY return, which assumes a beta of 1. `pipeline/fama_french.py`
   subtracts two fixed constants as a "Fama-French" adjustment and falls back
   to a hard-coded benchmark of 0.1116.
7. **The t-test treats trades as independent.** Trades share members,
   dates, and overlapping 90-day windows, so the p-value is too small.
8. **Three horizons were tested with no correction.**

Correctly parsed, the snapshot has 5,652 purchases with a valid ticker
(House 5,041, Senate 611; 1,435 tickers; 150 members).

## Questions

- **Q1 (primary).** After disclosure, does a portfolio that copies
  Congressional stock purchases earn a positive four-factor alpha?
- **Q2.** From the transaction date, do purchased stocks earn positive
  abnormal returns? The gap between Q2 and Q1 is what the filing delay
  costs an outside investor.
- **Q3 (descriptive).** How long do members take to disclose, and how often
  do they miss the 45-day deadline in the STOCK Act?

Q1 is the one confirmatory test. Everything else is reported as exploratory.

## Data

- **Trades.** The `821d6e5` snapshot, re-saved as a plain CSV by
  `pipeline.event_sample.normalize_padded_csv` at
  `data/snapshots/legislative_trades_821d6e5.csv` (SHA-256
  `2073e06f19fb5bd01ccff3455302ce9709e3cbf8b1eb2f733f86a0a17e1276a8`). A test
  fails if that file changes. The upstream Stock Watcher buckets now return 403, so this
  snapshot is the only copy of this extract. A fresh scrape of the official
  House and Senate sites can serve as a later replication.
- **Senate disclosure dates are missing** from the snapshot. Senate rows go
  into Q2 only, unless the filing date is recovered from each `ptr_link`.
- **Prices.** Open decision, see below.
- **Factors.** Daily Fama-French three factors and momentum from Kenneth
  French's data library, with the download date recorded. The five-factor
  model is a robustness check.

## Sample

An event is one purchase (`P` or `Purchase`) of a listed common stock by a
member, spouse, or dependent, with:

- a ticker that matches a security in the price source on the event date;
- a transaction date from 2020-01-01 to 2025-12-31 (filings for trades in
  early 2026 were still arriving when the snapshot was taken);
- for Q1, a disclosure date on or after the transaction date and no more
  than 365 days later. Negative lags (14 in the House rows) and longer
  lags are data errors, and the sample-flow table counts them.

Duplicates (same member, owner, ticker, transaction date, and amount band)
collapse to one event. Every exclusion is counted in a sample-flow table.

`python -m pipeline.event_sample` applies these rules. On the snapshot it
gives:

| Step | Rows left |
| --- | ---: |
| Rows in snapshot | 16,202 |
| Purchases (`P` or `Purchase`) | 7,722 |
| Valid ticker | 5,652 |
| Stock (no options or other securities) | 5,545 |
| Transaction date 2020-01-01 to 2025-12-31 | 5,162 |
| After removing duplicates | 5,137 |
| No disclosure date (Senate rows) | 494 |
| Disclosed before the trade | 12 |
| Disclosed more than 365 days later | 45 |
| Eligible for Q1 | 4,586 |

Price matching will remove more events. That count is reported once the
price source is chosen.

## Model

- **Event-level returns.** Estimate market-model and four-factor betas over
  trading days −250 to −30 before the event, requiring at least 100
  returns. Cumulative abnormal returns run over trading days [0, +20],
  [0, +62], and [0, +125], roughly 30, 90, and 180 calendar days.
- **Calendar-time portfolio (primary test for Q1).** Each day, hold equal
  weights in every stock purchased and disclosed within the last H trading
  days (H = 62 primary; 20 and 125 secondary). Regress the daily portfolio
  excess return on the four factors. The intercept is the alpha. Use
  Newey-West standard errors. This handles overlapping windows and trades
  that cluster on the same dates.
- **Event-level inference.** Standard errors clustered by member and by
  event month.
- **Multiple testing.** Holm correction across the 3 horizons × 2 event
  dates. The Q1 test at H = 62 is the single pre-declared primary result.

## Robustness

Leave out 2020; House and Senate separately; drop the five most active
members; weight by the midpoint of the disclosed amount band; members' own
trades only (no spouse or dependent); sales as a separate event type. A
check that is worse than the primary result is reported next to it.

## What the paper will claim

Whatever the primary estimate shows, including no effect. Prior work
disagrees about whether members outperform, so a careful null result is a
contribution. The paper will not claim insider trading. Abnormal returns
can come from many sources, and the data cannot separate them.

## Open decisions

- **Price source.** CRSP through WRDS includes delisted stocks and avoids
  survivorship bias. Yahoo Finance is free, but it is missing delisted
  tickers and its terms do not allow redistributing prices. If Yahoo is
  used, report how many events are lost to missing tickers.
- **Senate disclosure dates.** Recover them from the PTR pages, or limit
  Q1 to the House.

## Release

Release code, the cleaned trade snapshot (public records), the factor
download script, and the sample-flow table. Do not release price data.
Results go to SSRN and Zenodo after the paper is drafted.
