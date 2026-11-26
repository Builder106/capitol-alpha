# Insider-purchase control (C1)

Results of the plan in `docs/specs/insider-control.md`. The plan was committed
on 2026-11-25 before any insider return was computed, and the run was made the
same day. It was written after the Congressional results were known; the
insider rules were not tuned to them, and nothing in the plan changed after
the first run.

Insider trades are the SEC's Insider Transactions Data Sets (`2020q1` to
`2026q1`, downloaded 2026-11-25). Prices are the same CRSP daily returns used
in the event study (CIZ, through 2025-12-31). Factors are Kenneth French's
daily three factors and momentum, downloaded the same day; the SHA-256 of the
joined file is `a15652ef7d2ea1d3f41f863fabf04dfb0da9269bf2be29ca55c4cb007cd632fe`.
Reproduce on a machine with WRDS access, with the SEC files in `SEC`:

```sh
uv run --with "psycopg[binary]" python -m pipeline.insider_control \
  --data-dir DIR --sec-dir SEC --user NAME
```

## Answer

The control detects an effect. A portfolio that copies insider open-market
purchases from the day after the filing earns a four-factor alpha of 8.50% a
year at the primary 62-day holding period (t = 2.64, p = 0.008). By the
reading rule fixed in advance (positive and p below 0.05), the procedure finds
abnormal returns in a group that earlier studies found to earn them.

## Sample

| Step | Rows left |
| --- | ---: |
| Purchase lines (code P), one per reporting owner | 259,936 |
| Form 4 as originally filed | 249,827 |
| Acquired | 249,270 |
| Common stock | 238,937 |
| No equity swap | 238,910 |
| Positive shares and price | 233,303 |
| Officer or director | 133,868 |
| Valid ticker | 132,033 |
| Transaction date 2020-01-01 to 2025-12-31 | 127,841 |
| After removing duplicates | 90,772 |
| Disclosed before the trade | 11 |
| Disclosed more than 365 days later | 615 |
| Filing lag 0 to 365 days | 90,146 |
| No CRSP common or ADR record on the trade date | 14,707 |
| ADRs (excluded) | 2 |
| Other share types (excluded) | 1,451 |
| Matched to CRSP common stock | 73,986 |

The matched events cover 4,170 stocks. Of the matches, 192 had more than one
common record and the lowest `permno` was kept. For comparison, the Congress
primary sample has 3,942 purchases.

## Copy portfolio from the filing date

| Holding days | Primary | Alpha (annual) | Daily alpha | NW s.e. | t | p | Days | Lags |
| ---: | :---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 20 |  | 24.94% | 0.00099 | 0.00015 | 6.60 | 0.000 | 1,506 | 7 |
| 62 | yes | 8.50% | 0.00034 | 0.00013 | 2.64 | 0.008 | 1,506 | 7 |
| 125 |  | 4.54% | 0.00018 | 0.00013 | 1.39 | 0.165 | 1,506 | 7 |

The estimate shrinks as the holding period grows, from 24.94% at 20 days to
4.54% at 125 days, and is not significant at 125 days. Most of the return
comes in the first weeks after the filing.

## Robustness at 62 days

| Check | Events | Alpha (annual) | t | p | Days |
| --- | ---: | ---: | ---: | ---: | ---: |
| Primary: all purchases | 73,986 | 8.50% | 2.64 | 0.008 | 1,506 |
| Leave out trades made in 2020 | 58,487 | 6.57% | 2.10 | 0.035 | 1,254 |
| Price of $5 a share or more | 50,106 | 5.25% | 2.19 | 0.029 | 1,506 |

Both checks stay positive and significant at the 5% level, with smaller
estimates. The $5 check matters because equal weighting gives low-priced
stocks the same weight as large ones.

## Next to the Congress result

| | Alpha (annual, 62 days) | t | 95% interval |
| --- | ---: | ---: | --- |
| Congress, copy from disclosure | -1.63% | -0.66 | -6.48% to +3.22% |
| Insiders, copy from filing | 8.50% | 2.64 | about 2.2% to 14.8% |
| Insiders, price of $5 or more | 5.25% | 2.19 | about 0.5% to 10.0% |

The Congress interval excludes both insider estimates. Where the Congress test
could see 8.50% or even 5.25% a year, it saw neither. The insider intervals
are the estimate plus or minus 1.96 standard errors, with each standard error
taken as alpha divided by t.

## What this does and does not show

- It shows the procedure (same years, same factors, same portfolio rule, same
  standard errors) can find alpha in a group where earlier studies found it. A
  failure of the method is therefore not a likely reason for the Congress null.
- It does not show that Congress has no information, and it does not predict
  what Congress would earn. The two groups differ in firm size, trade size,
  number of stocks held and filing lag (two business days for Form 4, a median
  of 13 days for the House).
- It does not show that an investor could profit. Insider purchases cluster in
  small, thinly traded stocks, and the portfolio is equal-weighted and ignores
  trading costs.
- The Form 4 filing date is the date in the SEC files. A filing that became
  visible later would delay entry, which can only lower the insider estimate.

## Not done

The plan says to release the cleaned list of insider events. That has not
been done: the event file carries CRSP identifiers, so it needs a decision on
what is safe to publish.
