<picture>
  <source media="(prefers-color-scheme: dark)"  srcset="assets/banner-dark.svg"  type="image/svg+xml">
  <source media="(prefers-color-scheme: light)" srcset="assets/banner-light.svg" type="image/svg+xml">
  <source media="(prefers-color-scheme: dark)"  srcset="assets/banner-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="assets/banner-light.png">
  <img alt="CapitolAlpha: do members of Congress beat the market? No. The Capitol dome sits on a flat line that becomes the mean abnormal return after disclosure, which stays near zero." src="assets/banner-light.svg">
</picture>

[![CI](https://github.com/Builder106/capitol-alpha/actions/workflows/ci.yml/badge.svg)](https://github.com/Builder106/capitol-alpha/actions/workflows/ci.yml)
[![Live site](https://img.shields.io/badge/findings-live-success.svg)](https://capitolalpha.vercel.app)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/Playwright-scraping-2EAD33.svg?logo=playwright&logoColor=white)](https://playwright.dev/python/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](#license)
[![Course](https://img.shields.io/badge/Wesleyan-QAC%20420-CC0000.svg)](https://www.wesleyan.edu/qac/)

> **Do members of Congress beat the market?** An event study of 4,456 congressional stock purchases, 2020 to 2025, on CRSP data. Copying them once they were disclosed earned no four-factor alpha.

<p align="center">
  <img src="assets/screenshot.png" alt="The CapitolAlpha site: the question 'Do members of Congress beat the market?' beside a line drawing of the Capitol dome sitting on a long zero line, with the answer below." width="880">
</p>

## What is CapitolAlpha?

Members of Congress have to disclose their stock trades, and a popular claim says they beat the market. CapitolAlpha collects those disclosures from the House and Senate and tests the claim the way finance research tests events: it measures each purchase's return against what a four-factor model predicts, starting on the day the public could first see the trade.

The answer is no. A portfolio that buys every disclosed purchase the day after disclosure and holds it for 62 trading days, the test fixed in advance, earns a four-factor alpha of -1.82% a year (t = -0.74, p = 0.46). Average abnormal returns after disclosure stay inside a 95% band that covers zero on every one of the first 126 trading days, and eight robustness checks agree.

**Site:** [capitolalpha.vercel.app](https://capitolalpha.vercel.app) walks through the study in event time.

## Project history

CapitolAlpha started in spring 2025 as a semester project for **QAC 420 (Data for Good)** at Wesleyan University. That version reported that purchases beat the S&P 500. An audit in November 2026 found it did not hold: a text filter dropped every House purchase, leaving about 220 Senate trades; only the 50 most-traded tickers had prices; returns started on the trade date; and the "alpha" assumed a beta of one. The [journal](JOURNAL.md) records the details.

The redo follows a plan committed before any new return was computed: [`docs/specs/event-study.md`](docs/specs/event-study.md). One change was made after seeing results (abnormal returns now remove factor exposure only, as the plan says), and the first run's numbers are still printed and reported.

The spring 2025 course write-ups are kept as a record and are superseded by the event study: [abstract](docs/abstract/abstract.pdf), [final reflection](docs/Final_Reflection/Final_Reflection.pdf), [statistics](docs/statistics/statistics.pdf).

## Key findings

Full tables: [`docs/results/event-study.md`](docs/results/event-study.md) and [`docs/results/disclosure-lag.md`](docs/results/disclosure-lag.md).

| Question | Result |
| --- | --- |
| Copy portfolio from disclosure, 62-day hold (primary) | Alpha -1.82% a year, t = -0.74, p = 0.461, 3,942 House purchases |
| Same portfolio, 20 and 125 days | 1.95% (p = 0.547) and -1.81% (p = 0.433) |
| Mean CAR after disclosure, days 20, 62 and 125 | 0.00%, -0.34%, -0.68%; smallest Holm-adjusted p = 0.343 |
| Mean CAR after the trade date | No horizon significant after Holm correction |
| Eight robustness checks | All insignificant; largest is amount-weighted, 7.12% a year (t = 1.43) |
| Disclosure delay (House) | Median 13 days; 69 of 1,965 filings were late under the STOCK Act's 45 days |

Sample: 5,137 purchases after the plan's rules, of which 4,456 match CRSP common stock on the trade date. ETFs, funds, ADRs and over-the-counter foreign shares are excluded and listed with reasons.

One exploratory pattern: members tend to buy stocks that had been beating the factor model before the trade.

## Pipeline

Senate and House filings are fetched separately and merged into one 16,203-row trade CSV. Both notebooks read that CSV, and the financial one also pulls market prices.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/diagrams/pipeline-dark.png">
  <img src="assets/diagrams/pipeline.png" alt="senate_fetcher.py and house_fetcher.py each pull Stock Watcher JSON, or scrape the official site when it is missing. merge_to_csv.py cleans and dedupes both into the trade CSV. The EDA notebook reads it, and the financial analysis notebook reads it along with SPY and ticker prices from yfinance." width="880">
</picture>

[Edit the diagram](assets/diagrams/pipeline.html).

[`run_pipeline.py`](run_pipeline.py) orchestrates data extraction; individual modules live in [`pipeline/`](pipeline/). Automated tests for data extractors and data cleaning are in [`tests/`](tests/).

## Reproducing the analysis

```bash
uv sync --group dev
uv run playwright install chromium

python -m pipeline.run_pipeline --use-official
uv run python -m pipeline.disclosure_lag

uv run --with "psycopg[binary]" python -m pipeline.crsp --user WRDS_USER --out-dir DIR
uv run python -m pipeline.run_event_study --data-dir DIR
uv run python -m pipeline.site_figures --data-dir DIR

uv run pytest
```

The event study needs a WRDS account with CRSP access. `pipeline.crsp` reads the password from your own `~/.pgpass`. CRSP data is licensed, so the extract in `DIR` stays out of the repository; `pipeline.site_figures` writes only aggregates to `site/data/figures.json`.

Pipeline options (`--fresh`, `--senate-only`, `--house-only`) are documented in [`pipeline/README_PIPELINE.md`](pipeline/README_PIPELINE.md).

## Limits

- **House only for the primary test.** The Senate records in the snapshot carry no disclosure date, so Senate purchases appear only in the trade-date checks.
- **Late filings are right-censored.** The trade snapshot dates from April 2026, so some filings for late 2025 trades are missing.
- **Prices end on 31 December 2025.** Later purchases have shorter horizons, so fewer events reach day 125.
- **A null is not proof of no information.** The test asks whether a public follower could profit. It says nothing about what any member knew.

## Tech stack

- **Python 3.11+** with `pandas` and `numpy` for the event study, plus `scipy`, `matplotlib` and `seaborn` in the notebooks
- **CRSP through WRDS** for daily returns, and Kenneth French's data library for the factors
- **Playwright** for browser automation on JavaScript-rendered disclosure sites
- **pdfplumber** for House PTR PDF table extraction
- **yfinance** in the spring 2025 notebooks only
- **pytest** for unit tests on the fetchers and merge step
- **Jupyter** for the EDA and financial-analysis notebooks
- **GSAP** and Glaxnimate-drawn SVG for the site

## Acknowledgments

- The **Wesleyan QAC** for the *Data for Good* course frame and the methodological feedback through the semester.
- [`timothycarambat/senate-stock-watcher-data`](https://github.com/timothycarambat/senate-stock-watcher-data) as the JSON fallback when official scraping fails.
- The U.S. Senate Office of Public Records and the Office of the Clerk of the House for publishing the disclosure data that makes this analysis possible at all.

## License

Code released under the [MIT License](LICENSE). The underlying disclosure filings are public records in the public domain; the dataset assembled here (`data/legislative_trades.csv`) is released under the same terms.
