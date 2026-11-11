# JOURNAL — CapitolAlpha

> Dated log of decisions, pivots, incidents, and quotes. Add entries as
> things happen — retrospectives need this raw material to land.
> Reverse-chronological; one paragraph max per entry.

## 2026-11-10 — Redo the headline as a pre-planned event study #decision #incident

An audit of the +2.58% result found that it rests on 220 Senate-only trades. The notebook matched purchases with `Purchase|buy`, which drops every House `P` row, and priced only the 50 most-traded tickers. It measured returns from the transaction date, although the methodology says disclosure, and its "alpha" is trade return minus SPY with an implied beta of 1. The committed trade CSVs had also been replaced with three-line test output in `aac906f`. The full extract is restored from `821d6e5` as `data/snapshots/legislative_trades_821d6e5.csv`, and a hash test guards it. `docs/specs/event-study.md` fixes the sample, factor model, calendar-time test, and multiple-testing correction before any new return is computed. The new sample has 4,586 disclosed purchases for the primary test. The README and site still show the old number until the redo is finished.

## 2026-11-06 — Offline committee/sector correlations and activity signals #milestone #decision

The committee trade correlation milestone has no accompanying `docs/specs/` specification. Acceptance is a backend analysis command over the existing canonical trades, explicit historical committee intervals and sector/jurisdiction reference CSVs, reproducible contingency counts and phi correlation, and sector-specific purchase/sale activity signals with an insufficient-data threshold. Added `pipeline/committee_signals.py` without changing ingestion, the canonical schema, frontend, or submitted findings. Membership is evaluated on transaction dates while eligibility uses an explicit trailing disclosure window and as-of cutoff; intervals are unioned to prevent duplicate counts. References remain operator-supplied public data rather than hard-coded current rosters or inferred jurisdictions. Signals use transaction counts, never dollar midpoints, and are descriptive rather than validated return forecasts. The methodology records roster completeness, exact member-name reconciliation, static sector-map hindsight, and missing-data limitations; offline tests verify formulas, membership changes, window boundaries, duplicate references, invalid inputs, and atomic output publication.

## 2026-11-06 — Automated ticker resolution and corporate entity mapping #milestone #decision

Added `pipeline/entity_linking.py` to automate ticker symbol resolution and corporate entity mapping across raw Congressional disclosure filings. Raw House and Senate disclosures frequently lack standardized CUSIP or ticker identifiers, embedding symbols in descriptions (parentheses, brackets, prefixes, or standalone text) or disclosing company names without tickers. The module extracts valid exchange tickers using targeted regex heuristics and bidirectional corporate mapping (e.g. Apple Inc. -> AAPL, The Boeing Company -> BA), while strictly excluding non-equity assets (municipal bonds, treasury bills, corporate debt with coupon/maturity terms, and cryptocurrencies). Integrated entity linking into `pipeline/merge_to_csv.py` via `clean_dataframe`, added `corporate_entity` to canonical `COLUMN_ORDER`, and updated methodology documentation with 100% test coverage across all pipeline modules.

## 2026-11-06: Remove dead Stock Watcher S3 endpoints from configuration #cleanup #decision

Issue #29 reported that the third-party Stock Watcher S3 buckets return 403 and its GitHub repository is stale. Live ingestion has already migrated to the official House Clerk and Senate eFD scrapers via `--use-official` (and automatic fallback when local JSON is missing). Cleaned up the unused `HOUSE_S3_URL`, `SENATE_S3_URL`, and `SENATE_RAW_URL` constants along with unused `requests` imports from `pipeline/config.py`, `pipeline/house_fetcher.py`, and `pipeline/senate_fetcher.py`.

## 2026-11-06: Make the social preview image absolute #fix

The page set `og:image` to `/social-card.png`. Link preview crawlers don't resolve a relative path, so shared links showed no card. The tag now points at the production origin, and `og:url`, the image size and `twitter:image` are set to match. The 1200x630 image is unchanged, and the Playwright suite passes.

## 2026-10-27: Enforce Ruff formatting in CI #ci #decision

Ruff format failures now stop CI. Ruff also checks the `UP` rules for outdated Python syntax.

## 2026-10-21: Redraw the pipeline figure from the code #decision

The old figure baked its title into the image, left most of the canvas empty, and set prose in monospace. The new one in `assets/diagrams/` shows only what `run_pipeline.py` and the notebooks do: two fetchers merge into the trade CSV, and only the financial notebook adds yfinance prices. The research outputs box is gone because no code produces it.

## 2026-10-13: Replace the README Mermaid diagram #decision

The README now uses a static diagram with an editable HTML source at `assets/pipeline.html`. PNG keeps the GitHub rendering consistent. The separate Senate and House fetch paths converge on the normalized trade CSV. EDA and financial analysis branch from that dataset; SPY and ticker prices feed the financial branch. Jensen's alpha and Sharpe tests are grouped with financial analysis, and the final documents are grouped as research outputs.

## 2026-08-29: Gate the active Vercel project by branch #decision

The active Vercel project uses `site` as its root, so `site/vercel.json` now blocks all Git-triggered deployments except `main` and `staging`. `main` remains the Production Branch and `staging` is the only Preview branch.

## 2026-08-14: Accessible plain-English documentation update #decision

Refactored the README headline, summary tagline, and introductory section to articulate the core civic question: whether federal politicians have an unfair trading edge over ordinary investors. Removed em dashes from intro copy and preserved all academic PDFs and statistical findings.

## 2026-08-07 — Added Fama-French multi-factor risk model, disclosure monitor & methodology guide #milestone #docs

Extended the financial analysis pipeline with `pipeline/fama_french.py`for CAPM and Fama-French 3-Factor risk adjustment (Market, SMB, HML) to verify that outperformance holds up against systematic factor exposure. Added`pipeline/monitor.py`for automated PTR disclosure delta tracking, created`docs/METHODOLOGY.md`documenting normalization heuristics and risk model assumptions, and expanded the unit test suite with`tests/test_pipeline_additions.py`. Verified clean test execution on `ampere-dev`.

## 2026-07-22 — Expanded test suite to 100% full coverage across pipeline & utils #milestone #decision

Refactored `utils/check_covid.py`, `utils/mappings.py`, and `utils/patch_code.py`to wrap top-level executions in clean`if __name__ == '__main__':`functions, eliminating side effects during module import. Created`tests/test_utils.py`and expanded`test_house_fetcher.py`, `test_senate_fetcher.py`, `test_merge_to_csv.py`, `test_run_pipeline.py`, and `test_scrapers.py`. Achieved 47 passing assertions and 99.02% total line coverage across the repo verified on `ampere-dev`.

## 2026-05-19 — Three skins in one day, landing on equity-research note #decision #pivot

The findings page got reskinned three times in a single afternoon. First pass was a broadsheet/FT-investigation look (serif prose, IBM Plex Mono numbers, Congressional-Record §-prefixed headings, ticker tape). Within hours I tore that out and rebuilt it as an equity-research note instead: cool near-white paper, finance-green for the +2.58% headline with a ▲ arrow (positive numbers are green in finance, so the color does work), a verdict panel with a rating chip, numbered Exhibits with Source attributions, and a "not investment research" disclaimer in the footer. The favicon got redone the same day too — the original three-element CA + bar + arrow mark turned to mush at 16×16, so it's now a single bold serif α in finance-green. Lesson: a recognizable glyph at favicon size beats a clever composite every time.

## 2026-05-19 — Killed my own deploy workflow; Vercel already does it #incident #decision

Added a GitHub Actions deploy workflow to push the findings page, then deleted it the same day once I realized Vercel's GitHub integration already auto-deploys on every push to main — the Action was just a redundant second deploy racing the first. Also had to exclude `/_vercel/*` from the cache-header rules, because the catch-all cache config was shadowing Vercel's Web Analytics endpoint and silently swallowing the analytics beacon. Took a redeploy after toggling analytics on for it to actually start reporting.

## 2026-05-18 — LICENSE wouldn't trigger GitHub's MIT chip #incident

GitHub's license auto-detect refused to fire even with a LICENSE file at the root. The fix was stripping the non-canonical preamble text I'd added — GitHub matches the license against the exact canonical MIT body, and any extra wording above it breaks the match. Same day, served the README banner as SVG instead of PNG so it stays sharp on retina, after the raster version looked soft at higher zoom.

## 2026-05-18 — Repo renamed to CapitolAlpha, shipped the storefront baseline #milestone #decision

Renamed the project to CapitolAlpha and added the full repo baseline at once: README with light/dark SVG banner, MIT LICENSE, CONTRIBUTING with scope and guardrails, a CI workflow (Python compileall + pytest), and assets themed on the +2.58% Jensen's-alpha headline (1200×420 banner, 1200×630 social card). Had to chase the renamed-repo URLs through the README badges and the social-card meta afterward. The headline number became the whole visual identity — the alpha stat is the brand.

## 2026-04-30 — Final reflection: this was a data-engineering project wearing a stats hat #milestone #decision

Wrote the Final Reflection and named the real takeaway: the project was a data-engineering challenge as much as a statistical one. The disclosures are public but adversarial to work with — House data lives in PDF scans needing pdfplumber/OCR, Senate is digitized, and the two chambers use different filing formats and column conventions. Most of the effort went into regex normalization and column reconciliation to merge 16,000+ trades into one analysis-ready table, not into the t-test itself. Also recorded the honest framing of the headline: most legislators do NOT consistently beat the market — the +2.58% alpha lives in the tails, driven by a small subset of trades and traders, which is why the story focuses on anomalies rather than "Congress beats the market."

## 2026-04-06 — COVID pre-crash sell-timing analysis #milestone

Added `check_covid.py` to test the market-timing angle separately from the alpha number. It groups early-2020 sales by legislator, isolates the top 5% of sellers by dollar volume, and splits the rest into pre-crash (Jan 15–Feb 19) vs post-crash (Feb 20–Mar 31, after the S&P top on Feb 19) windows. The point was to show concentration: a thin slice of sellers accounts for the bulk of the pre-crash exit volume. Framed deliberately as suggestive, not causal — the disclosure data can't distinguish information advantage from sector concentration, wealth effects, or an advisor.

## 2026-04-01 — Beat the House DataTables 50-row pagination with injected JS #decision #incident

The House disclosure site (disclosures-clerk.house.gov) renders results through a DataTables widget that only exposes 50 rows at a time, so a naive scrape silently captured a fraction of the records. The fix in `house_official.py`is to reach into the page and run`dt.page.len(-1).draw()`via Playwright's`evaluate`— commanding DataTables to render every row at once before extraction, instead of clicking through pages. Same commit added`parse_house_pdf`(pdfplumber) for the PTR PDFs and a`date_received`fallback in`_normalize_house_row`for when both`transaction_date`and`disclosure_date` are missing.

## 2026-03-31 — Pipeline scaffolded with an official-vs-fallback data strategy #decision #milestone

First commit stood up the whole fetch-and-merge pipeline (Senate + House → normalized `legislative_trades.csv`) and baked in a deliberate two-source strategy. `--use-official`scrapes efdsearch.senate.gov and the House clerk site directly via Playwright (slow but authoritative); the default path pulls pre-aggregated Senate JSON from`timothycarambat/senate-stock-watcher-data`(fast, used as the fallback when official scraping breaks). Senate config carries both`SENATE_RAW_URL`and`SENATE_S3_URL` so the fast path has its own redundancy. The bet: don't let a flaky government scraper block the analysis — keep an offline-cached fallback so the notebooks always have data to run against.

## 2026-03-31 — Reviewer ethics + rigor feedback that shaped the framing #feedback #quote

Course reviewer comments on the Problem Statement and Statement of Purpose set several guardrails the final work had to honor. On scraping: *"scraping has been a controversial practice — how would you address potential questions about the ethics of scraping?"*and a pointed*"I'm curious if these sources have some sort of firewalls that prevent scraping"*— which is why the reflections draw the explicit line that this automates reading legally-public data, not bypassing CAPTCHAs or access controls. On rigor:*"I'd suggest being careful with this kind of suggestive language — till you find a stat. significant result, you can't really say that it's 'abnormal', right?"*On scope:*"Maybe after looking at the general trends, you can pick out the anomalies (highest/lowest returns) and focus on their stories!"*— which became the anomalies-in-the-tails narrative. And repeatedly:*"Define this!"* on Jensen's Alpha, Sharpe ratio, and information-advantage decay, pushing the deliverables to explain the jargon for a non-technical audience.

## 2026-10-23: Check all Python paths for Any annotations #decision

Ruff ANN401 now covers notebooks, pipeline code, tests, utilities, and `run_pipeline.py`. The unit-test job already treats Python warnings as errors.

## 2026-11-06 — Fail closed when official PTR ingestion is incomplete #decision

The House & Senate PTR milestone builds on the existing official scrapers rather
than replacing public sources or extending asset entity linking. The roadmap has
no accompanying `docs/specs/` directory, so acceptance is transaction-level data
from both existing source adapters, bounded retries, explicit errors instead of
silent omissions, preservation of existing outputs on source/serialization
failure, and offline regression coverage.

Source operations now retry three times with one- and two-second backoff. Failed
reports stop the run; House listing-only fallbacks and Senate report skipping are
removed. Empty official chamber results also stop publication because an empty
search can indicate source drift. Scanned House PDFs require operator attention
for OCR rather than being counted as successfully ingested transactions.

House parsing preserves blank header positions and visits every table and page.
Filing-year searches retain prior-year transactions disclosed late. Report URLs
are deduplicated, Senate pagination detects stalls, explicit tickers remain
separate from asset descriptions, and amount bands retain their bounds and derived
midpoints. Output keeps the existing canonical CSV columns.

Both chambers finish before publication. CSVs are staged and flushed on the
destination filesystem, then replaced atomically per file. This protects existing
data from source errors and failed serialization, but does not provide a
transaction across all three files during a process crash. Reruns read reports
again; durable per-report checkpoints and OCR are outside this focused change.

Synthetic local HTML and a multi-page PDF exercise parsing, normalization, rerun
idempotence, missing tickers, late disclosures, and failure preservation. No live
ingestion or research-data refresh is part of this milestone.
