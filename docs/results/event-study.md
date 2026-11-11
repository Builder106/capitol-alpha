# Event study results (Q1 and Q2)

First full run of the plan in `docs/specs/event-study.md`, on 2026-11-11.
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

The matched events cover 1,010 stocks. Q1 uses the matched events that also
have a disclosure 0 to 365 days after the trade. Those are House trades,
because the snapshot has no Senate disclosure dates.

## Q1: copy portfolio from the disclosure date

Equal-weight portfolio of every stock bought and disclosed in the last H
trading days, entering the day after disclosure. Four-factor alpha with
Newey-West errors. H = 62 is the pre-declared primary test.

| Holding days | Primary | Alpha (annual) | t | p | Days |
| ---: | :---: | ---: | ---: | ---: | ---: |
| 20 | | 1.93% | 0.60 | 0.550 | 1,505 |
| 62 | yes | -1.82% | -0.74 | 0.460 | 1,505 |
| 125 | | -1.81% | -0.79 | 0.431 | 1,505 |

## Event-level CARs

Four-factor betas from trading days -250 to -30, cumulative abnormal returns
over [0, h] trading days. Standard errors are clustered by member and by
event month. Holm correction across the six tests.

| Event date | Horizon | Events | Mean CAR | t | p | Holm p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Disclosure | 20 | 3,795 | 0.00% | 0.01 | 0.989 | 1.000 |
| Disclosure | 62 | 3,630 | -0.34% | -0.83 | 0.406 | 1.000 |
| Disclosure | 125 | 3,140 | -0.68% | -1.90 | 0.057 | 0.343 |
| Transaction | 20 | 4,372 | -0.04% | -0.18 | 0.855 | 1.000 |
| Transaction | 62 | 4,161 | -0.04% | -0.12 | 0.905 | 1.000 |
| Transaction | 125 | 3,932 | -0.21% | -0.58 | 0.562 | 1.000 |

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

## Not yet done

- The robustness checks in the plan: leave out 2020, House and Senate
  separately, drop the five most active members, amount weighting, own
  trades only, and sales.
- The market-model version of the CARs.
- Recovering Senate disclosure dates, which would add Senate trades to Q1.
- Listing the 365 unmatched tickers to confirm they are funds and not
  ticker errors.
