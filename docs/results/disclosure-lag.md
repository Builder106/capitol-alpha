# Disclosure lag (Q3)

How long House members took to report stock trades, from the `821d6e5`
snapshot. The STOCK Act requires a periodic transaction report no later than
45 days after the trade. Reproduce with:

```sh
uv run python -m pipeline.disclosure_lag
```

The table covers all transaction types with a transaction date from
2020-01-01 to 2025-12-31, after removing duplicate rows. A filing is one
report (`ptr_link`). It counts as late when at least one trade in it was
reported more than 45 days after the trade date.

| Year | Trades | Median days | 90th pct days | Late trades | Late share | Filings | Late filings | Members | Members ever late |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020 | 2,678 | 9 | 31 | 73 | 2.7% | 488 | 24 | 92 | 18 |
| 2021 | 2,047 | 8 | 32 | 59 | 2.9% | 398 | 17 | 90 | 13 |
| 2022 | 1,405 | 8 | 32 | 6 | 0.4% | 308 | 4 | 74 | 4 |
| 2023 | 1,816 | 22 | 31 | 95 | 5.2% | 255 | 11 | 72 | 10 |
| 2024 | 1,203 | 17 | 292 | 217 | 18.0% | 238 | 14 | 71 | 13 |
| 2025 | 3,501 | 14 | 50 | 383 | 10.9% | 318 | 9 | 75 | 9 |
| All | 12,650 | 13 | 34 | 833 | 6.6% | 1,965 | 69 | 210 | 48 |

Yearly filing counts add up to more than 1,965 because one report can list
trades from two years.

Set aside before the table: 1,325 trades with no disclosure date (mostly
Senate rows, which have none), 34 dated before the trade, and 100 dated more than 365 days
after it. The last two groups are probably data entry errors.

## Reading the table

- Most trades are reported well inside the deadline. The median is 8 to 22
  days in every year.
- Late trades cluster in a few reports. In 2024, 217 late trades come from
  14 filings, and one filing lists 68 of them. In 2025, one filing lists
  234 late trades. Trade counts overstate how often members file late, so
  the paper should lead with filing counts.
- The 2024 jump in the 90th percentile comes from those few long-delayed
  reports. The median fell from 22 days in 2023 to 17 in 2024.

## Limits

- House only. The snapshot has no disclosure dates for Senate trades.
- Some late filings may be amendments that re-list trades already reported
  on time. The snapshot does not mark amendments, so this needs a check of
  the filings themselves before the paper calls them late.
- 2025 is right-censored. The snapshot was taken in April 2026, so reports
  for late-2025 trades that were filed after that are missing, and the 2025
  late share is a lower bound.
