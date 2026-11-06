# Capitol Alpha – Data collection & pipeline

Pipeline for fetching and merging U.S. Congress (Senate and House) stock trade disclosures into a single CSV.

## Setup

```bash
uv sync --frozen --group dev
```

**For official-site scraping (recommended):** install Playwright browsers once:

```bash
uv run playwright install chromium
```

## Run

**Option 1 – Scrape official government sites (efd.senate.gov and clerk.house.gov):**

```bash
uv run python -m pipeline.run_pipeline --use-official
```

- **Senate:** Opens efdsearch.senate.gov, accepts the disclosure agreement, searches for PTRs by date range, visits each report URL, and parses the transaction table into rows.
- **House:** Opens disclosures-clerk.house.gov/FinancialDisclosure, searches by filing year, and parses every transaction table on every page of the linked PTR PDFs. Scanned PDFs that need OCR stop ingestion with an explicit error.

### Reliability contract

- Source operations retry up to three times, waiting one and then two seconds.
  Exhausted retries, malformed transaction rows, and unreadable PTRs raise an
  `IngestionError` and produce a nonzero CLI exit. A listing is never a trade.
- Each report URL is processed once per scrape. Senate pagination waits for the
  table to change and fails if a page repeats.
- Date searches select disclosure/filing years. Transactions from a prior year
  remain attached to their report; transaction and disclosure years stay separate.
- Both requested chambers must finish before any official CSV is published.
  Empty chamber results or results with no valid trades preserve existing outputs
  and require operator inspection before retrying.
- All output CSVs are staged and flushed before publication. Each destination is
  replaced atomically. Replacement of all three files is not a single filesystem
  transaction; a crash during replacement can leave files from different runs.
- Amount ranges retain their lower and upper bounds and a derived midpoint.
  Open-ended ranges have no upper bound or midpoint. Unknown tickers remain unknown.
- Rerunning a successful scrape yields the same normalized rows for unchanged
  reports. A failed run can be retried with the same command; it re-reads reports.

Official scraping requires Python 3.12+, the development dependency group
(Playwright), Chromium, and access to both public disclosure sites. It does not
bypass access controls. The tests use synthetic local HTML/PDF fixtures rather
than live government requests.

**Option 2 – Use local pre-aggregated JSON (no browser when caches exist):**

```bash
uv run python -m pipeline.run_pipeline
```

- Reads `data/senate_all_transactions.json` and `data/house_all_transactions.json`.
  If a requested chamber's JSON is missing, the pipeline switches to official
  scraping. `--fresh` re-reads local JSON; it does not download an aggregator feed.

Options:

- `--fresh` – Re-read local JSON (official scraping always reads the sources).
- `--senate-only` – Only Senate (scrape or API).
- `--house-only` – Only House (scrape or API).
- `--use-official` – Scrape **efdsearch.senate.gov**and**disclosures-clerk.house.gov** (requires Playwright).

## Data sources

- **Official (--use-official):**Direct scraping of**efdsearch.senate.gov**(Senate) and**disclosures-clerk.house.gov/FinancialDisclosure** (House), as in your problem statement.
- **Cached input (default):** Local pre-aggregated Senate/House JSON. The checked-in Senate cache originated from Senate Stock Watcher. Missing caches select official scraping.

## Output schema

`data/legislative_trades.csv` columns:

- chamber
- legislator_name
- transaction_date
- disclosure_date
- ticker
- corporate_entity
- asset_description
- asset_type
- transaction_type
- amount_range
- amount_min
- amount_max
- amount_avg
- owner
- ptr_link
- office
- party
- state
- transaction_year
- disclosure_year
- comment

### Normalized Asset Entity Linking

The pipeline automatically resolves ticker symbols and links transactions to canonical corporate entities (`pipeline/entity_linking.py`):

- **Ticker Symbol Resolution**: Normalizes explicit tickers, extracts embedded tickers via regex heuristics (parentheses, brackets, prefixes, labels, standalone tokens), and maps corporate entity names to standard ticker symbols.
- **Corporate Entity Mapping**: Maps resolved tickers and descriptive company names to canonical corporate entities (e.g. `AAPL` -> `Apple Inc.`, `MSFT` -> `Microsoft Corporation`).
- **Non-Equity Exclusion**: Filters out municipal bonds, treasury bills, corporate debt with coupons/maturities, and cryptocurrencies from equity ticker resolution.

## Committee/sector analysis

Run the backend analysis after creating the normalized trade CSV and preparing
historical membership, ticker-sector, and committee-jurisdiction reference CSVs:

```bash
uv run python -m pipeline.committee_signals \
  --trades data/legislative_trades.csv \
  --assignments /path/to/assignments.csv \
  --ticker-sectors /path/to/ticker_sectors.csv \
  --committee-sectors /path/to/committee_sectors.csv \
  --as-of 2024-04-30 --lookback-days 90 --min-trades 3 \
  --output /path/to/committee_signals.csv
```

Reference headers (all three files are required):

```text
assignments.csv:       chamber,legislator_name,committee,start_date,end_date
ticker_sectors.csv:    ticker,sector
committee_sectors.csv: chamber,committee,sector
```

Membership dates use `YYYY-MM-DD`; blank `end_date` means ongoing. Supply complete
historical membership for the trade cohort, with names reconciled to the canonical
CSV. Sector labels must share one taxonomy across both sector files. The command
uses local inputs, produces a separate CSV, and preserves an existing output on
validation or serialization failure. The output directory must already exist;
the output must differ from every input path.

Each output row contains the chamber, committee, jurisdiction sector, disclosure
window, eligible trade count, four membership/sector contingency counts, phi
correlation, member-sector purchases and sales, net purchase ratio, threshold,
and `buy`, `sell`, `neutral`, or `insufficient_data` activity signal. No amount
weighting or price downloads are involved. See [the methodology](../docs/METHODOLOGY.md#4-committee-trade-correlation-analysis)
for eligibility rules, equations, reference requirements, and limitations.

## Tests

```bash
uv run --frozen pytest tests/ -v
```
