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

- `belmont2022senators`: the NBER working paper version (w26975, April
  2020) covers senators from 2012 to March 2020. Their purchases slightly
  underperform stocks of the same industry and size, by 11, 28, and 17
  basis points at 1, 3, and 6 months. There is no committee-specific skill.
  Check the published version's sample and numbers. Its title includes
  House members, so the scope may have grown.
- `zhou2026illusion` (working paper): uses an LLM to match firms to
  committee jurisdictions. Finds no abnormal returns on committee-aligned
  trades and no change after hearings. The result holds across trade sizes
  and reporting delays.
- `fischer2025democracy` (working paper, posted 2025-12-25, revised
  2026-01-21; abstract read on SSRN on 2026-11-10): the closest recent
  study. It follows the 15 largest traders by volume and treats 2020 as a
  break, arguing that the dropped COVID-19 insider trading investigations
  may have weakened deterrence. Congress does not significantly outperform
  the market in any period. Mean buy-and-hold abnormal returns, for Congress
  and for the high-volume traders, rose at 20, 60, and 127 days, and their
  spread widened in 2020 to 2023 compared with 2012 to 2020. Sacerdote is
  also an author of `belmont2022senators`.

## Where this paper fits

The large abnormal returns are in data from before 2008. Studies of the
years after the STOCK Act mostly find none. Fischer and Sacerdote (2025)
already cover 2020 to 2023 at nearly the same horizons as this paper's
plan (20, 62, and 125 trading days), so the post-2020 period alone is not
new. What this paper can add, pending a read of their full text:

- returns from the disclosure date, which is what an outside investor can
  earn, if they measure from the transaction date;
- a calendar-time factor regression in place of mean buy-and-hold
  abnormal returns, whose inference problems `lyon1999improved` and
  `mitchell2000managerial` document;
- every member with a disclosed purchase, where they follow the 15
  largest traders;
- 2024 and 2025;
- how long members take to disclose, and how often they file late.

Before writing the introduction, read the full texts of
`fischer2025democracy` and `belmont2022senators` and confirm which event
date and benchmark each uses.

## Methods references

Factor models: `fama1993common`, `carhart1997persistence`, `fama2015five`.
Calendar-time portfolios for long-horizon events: `fama1998market`,
`lyon1999improved`, `mitchell2000managerial`. Inference: `newey1987simple`,
`newey1994automatic`, `cameron2011robust`, `holm1979simple`.
