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

## Tests

```bash
uv run --frozen pytest tests/ -v
```
