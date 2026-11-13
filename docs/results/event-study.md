# Event study results (Q1 and Q2)

Results of the plan in `docs/specs/event-study.md`, first run on 2026-11-11
and rerun on 2026-11-12 after an outside review found an entry-timing bug
(see "Changes after review" below). Portfolio numbers here are from the
rerun.
Prices are CRSP daily returns (CIZ, through 2025-12-31) from WRDS. Factors
are Kenneth French's daily three factors and momentum, downloaded the same
day. Reproduce on a machine with WRDS access:

```sh
uv run --with "psycopg[binary]" python -m pipeline.crsp --user NAME --out-dir DIR
uv run python -m pipeline.run_event_study --data-dir DIR
```

## Answer

Congressional stock purchases from 2020 to 2025 do not beat a four-factor
model, whether returns are measured from the trade or from its disclosure.
A portfolio that copies purchases once they are disclosed earns no
detectable alpha.

## Sample

| Step | Events |
| --- | ---: |
| Purchases after the rules in the plan | 5,137 |
| No CRSP common stock or ADR record on the trade date | 365 |
| ADRs (excluded) | 191 |
| Other share types (excluded) | 125 |
| Matched to CRSP common stock | 4,456 |

Q1 uses the 3,942 matched purchases with a disclosure 0 to 365 days after
the trade. Those are House trades, because the snapshot has no Senate
disclosure dates. In 14 purchases, two CRSP common-stock records cover the
trade date, and the lowest `permno` is kept.

The 365 purchases with no record span 221 tickers. 108 of them have a fund,
ETF, or trust description (SPY, IBIT, TNA, JEPI, ProShares short funds).
Most of the rest are over-the-counter foreign shares (Nestle, Roche,
Tencent, Fanuc) and closed-end funds or BDCs (Hercules Capital, Cohen &
Steers). None of the most frequent ones is a listed US common stock with a
wrong ticker. `excluded.csv` from `pipeline.crsp` lists every excluded event
with its reason.

## Q1: copy portfolio from the disclosure date

Portfolio of every stock bought and disclosed in the last H trading days,
equal-weighted by stock, entering on the first trading day strictly after the
disclosure date. Four-factor alpha with
Newey-West errors. H = 62 is the pre-declared primary test.

| Holding days | Primary | Alpha (annual) | t | p | Days |
| ---: | :---: | ---: | ---: | ---: | ---: |
| 20 | | 2.08% | 0.64 | 0.520 | 1,505 |
| 62 | yes | -1.63% | -0.66 | 0.509 | 1,505 |
| 125 | | -1.67% | -0.72 | 0.470 | 1,505 |

95% interval for the primary alpha: -6.48% to +3.22% a year. Of the 3,942
purchases, 39 are disclosed after the data end and never enter; 237 are held
for fewer than 62 days.

## Event-level CARs

Four-factor betas from trading days -250 to -30, cumulative abnormal returns
over [0, h] trading days. Standard errors are clustered by member and by
event month. Holm correction across the six tests.

| Event date | Horizon | Events | Mean CAR | t | p | Holm p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Disclosure | 20 | 3,795 | 0.00% | 0.01 | 0.988 | 1.000 |
| Disclosure | 62 | 3,630 | -0.34% | -0.83 | 0.404 | 1.000 |
| Disclosure | 125 | 3,139 | -0.68% | -1.90 | 0.057 | 0.343 |
| Transaction | 20 | 4,372 | -0.04% | -0.18 | 0.860 | 1.000 |
| Transaction | 62 | 4,161 | -0.04% | -0.11 | 0.913 | 1.000 |
| Transaction | 125 | 3,931 | -0.20% | -0.57 | 0.568 | 1.000 |

With the market model in place of four factors, every CAR is also
insignificant (means from -0.34% to +0.36%, all Holm p = 1.000).

Fewer events have long-horizon CARs because CRSP ends on 2025-12-31.

## A change made after the first run

The first run also subtracted each stock's pre-event intercept (its alpha
from days -250 to -30) when computing abnormal returns. The plan specifies
betas only. That run reported significantly negative CARs, for example
-1.98% at 62 days from disclosure (t = -3.86). A diagnostic showed the
projected intercept averaged +1.65% over 63 days (median +0.83%), because
members tend to buy stocks that had been beating the factor model. Removing
it brings the CARs to the values above, in line with the calendar-time test,
which has no pre-event intercept. The runner still prints the first run's
table so the change can be checked, and the paper must report both.

Members buying recent winners is itself a finding to report as exploratory.

## Robustness

The plan's checks, each on the 62-day copy portfolio with four-factor
alpha. None is significant.

| Check | Events | Alpha (annual) | t | p |
| --- | ---: | ---: | ---: | ---: |
| Primary: purchases from disclosure | 3,942 | -1.63% | -0.66 | 0.509 |
| Leave out trades made in 2020 | 3,234 | -3.60% | -1.49 | 0.137 |
| Drop the five most active members | 2,622 | -3.07% | -1.12 | 0.261 |
| Weight by disclosed amount | 3,942 | 7.19% | 1.45 | 0.148 |
| Members' own trades only | 1,861 | -5.00% | -1.51 | 0.131 |
| House purchases from the trade date | 3,996 | -1.38% | -0.59 | 0.557 |
| Senate purchases from the trade date | 460 | -0.95% | -0.10 | 0.920 |
| Stocks sold, held long from disclosure | 4,284 | 0.95% | 0.34 | 0.736 |

Two estimates are worth a sentence in the paper. Weighting by the disclosed
amount turns the alpha positive (7.19% a year, t = 1.45), a hint that
larger trades do better, though not a significant one. Members' own trades,
without spouses and dependents, have the most negative estimate (-5.00%,
t = -1.51). The Senate check has only 460 events over 288 trading days.

The sales row holds sold stocks long; it is not the return to shorting them.

## Changes after review (2026-11-12)

An outside review of the paper draft found:

- **Entry timing.** `event_day` returns the first trading day on or after a
  date, and the portfolio entered one day after that, so a weekend or
  holiday disclosure entered a day late. `entry_day` now gives the first
  trading day strictly after the disclosure date. The primary alpha moved
  from -1.82% (t = -0.74) to -1.63% (t = -0.66). The day-0 CARs and the
  first-run table do not use the entry day and are unchanged.
- **Cutoff.** `pipeline.crsp` requests returns through 2026-12-31, but the
  analysis stops at 2025-12-31 (`ANALYSIS_END` in `pipeline.run_event_study`).

Checks added after the review, all exploratory except the planned
five-factor model:

| Check | Estimate | t | p |
| --- | ---: | ---: | ---: |
| Five-factor model, H = 20 / 62 / 125 | 2.37% / -1.25% / -1.33% a year | 0.75 / -0.53 / -0.62 | 0.456 / 0.597 / 0.536 |
| Newey-West 21 and 62 lags, H = 62 | -1.63% a year | -0.71 / -0.75 | 0.479 / 0.454 |
| Amount-weighted minus equal-weighted, H = 62 | 8.83% a year | 1.65 | 0.099 |
| Holding-window CAR, days 1-20 / 1-62 / 1-125 | 0.05% / -0.27% / -0.62% | 0.25 / -0.64 / -1.64 | 0.802 / 0.521 / 0.101 |
| Trade to the copier's entry (3,863 events, median 11 days) | -0.24% | -1.99 | 0.046 |

The holding-window CARs start the day after disclosure, matching the
portfolio; their Holm-adjusted p-values are 1.000, 1.000 and 0.302. The
trade-to-entry return measures what a copier misses by waiting: it is
slightly negative, so waiting did not cost a gain. It is unadjusted and close
to the 5% line. The difference between the two CAR series in the table above
does not measure that cost, because the windows and samples differ.

## Not yet done

- Recovering Senate disclosure dates, which would add Senate trades to Q1.
- Notification dates, needed to check the 30-day reporting rule; only the
  45-day outer limit can be checked from the snapshot.
- Reading the full texts of the closest prior papers (see
  `docs/paper/literature.md`).
