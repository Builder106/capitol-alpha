# Literature notes

Each summary below comes from the paper's abstract, retrieved on 2026-11-10
from Crossref, OpenAlex, or NBER. Read the full paper before citing a number
from it. Keys refer to `references.bib`.

## Before the STOCK Act (2012)

- `ziobrowski2004senate`: Senate trades, 1993 to 1998. A portfolio that
  mimics senators' purchases beats the market by 85 basis points a month,
  and one that mimics their sales lags it by 12.
- `ziobrowski2011house`: the same method applied to more than 16,000 House
  trades by about 300 members, 1985 to 2001. Mimicking purchases beats the
  market by 55 basis points a month.
- `eggers2013capitol`: reinterprets both Ziobrowski studies and analyzes
  2004 to 2008. Finds no information advantage in either period, and the
  average member would have done better in a passive index fund.
- `eggers2014political`: members invest more in local firms and campaign
  contributors. Those connected holdings do better than members' other
  holdings, and the other holdings explain the poor overall returns.

## Around the STOCK Act

- `karadas2019trading`: 2004 to 2010. Buy-minus-sell portfolios of powerful
  Republicans earn the highest abnormal returns, over 35% a year at a
  one-week holding period. The abnormal returns disappear after the STOCK
  Act passed.
- `huang2016trading` (working paper): 2010 to 2013. Members earn
  significant abnormal returns before the Act and none after. Firms owned
  by politicians lose 1.4% in value around the Act's passage.
- `karadas2021macro`: 101,191 trades, 2004 to 2014. Members' aggregate
  trades predict market returns before the Act, and less so after it.
- `cherry2017change` (working paper): abstract not retrieved. Read before
  citing.

## After the STOCK Act

- `belmont2020relief` (NBER w26975, April 2020; full text read 2026-11-12)
  and its published version `belmont2022senators` (not read; its title adds
  House members, so its scope may differ). The working paper hand-collects
  senators' trades, 2012 to March 2020: 4,378 purchases and 3,881 sales of
  CRSP common stock. Returns run from the trade date. Buy-and-hold abnormal
  returns use the CRSP value-weighted index, industry-size portfolios and
  DGTW portfolios; CARs use the WRDS event tool with three-factor and Carhart
  loadings. Purchases slightly underperform industry-size benchmarks (11,
  28 and 17 basis points at 1, 3 and 6 months). A daily calendar-time
  portfolio of stocks bought in the past year, weighted by trade size, gives
  an insignificant Carhart alpha (-0.35 basis points a day). Stocks senators
  bought had underperformed over the 100 days before purchase.
- `zhou2026illusion` (working paper): uses an LLM to match firms to
  committee jurisdictions. Finds no abnormal returns on committee-aligned
  trades and no change after hearings. The result holds across trade sizes
  and reporting delays.
- `fischer2025democracy` (working paper dated 2025-12-23; full text read
  2026-11-12). Extends the Belmont et al. data with House and Senate trades
  to 2023: 331 members, 69,905 transactions from 2012 to 2023. Covers all
  members and also singles out the 15 most active traders. Returns run from
  the purchase date: BHAR(0,20), (0,60) and (0,127), raw and DGTW-adjusted,
  with no calendar-time regression. Congress does not significantly
  outperform in any period; mean BHARs are somewhat higher from 2020 to 2023.

## Where this paper fits

The large abnormal returns are in data from before 2008. Studies of the
years after the STOCK Act mostly find none. Fischer and Sacerdote (2025)
already cover all members from 2020 to 2023 at nearly the same horizons as
this paper's plan, so the post-2020 period alone is not new. Both close
studies measure from the trade date (confirmed in the full texts). What
this paper adds:

- returns from the disclosure date, which is what an outside investor can
  earn;
- a calendar-time factor regression from that date as the single
  confirmatory test; Belmont et al. run one only from the trade date and
  only for senators to 2020, and Fischer and Sacerdote run none;
- 2024 and 2025;
- a plan fixed before estimation;
- how long members take to disclose, and how often they file late.

## Methods references

Factor models: `fama1993common`, `carhart1997persistence`, `fama2015five`.
Calendar-time portfolios for long-horizon events: `fama1998market`,
`lyon1999improved`, `mitchell2000managerial`. Inference: `newey1987simple`,
`newey1994automatic`, `cameron2011robust`, `holm1979simple`.
