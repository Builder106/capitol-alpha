# JOURNAL — CapitolAlpha

> Dated log of decisions, pivots, incidents, and quotes. Add entries as
> things happen — retrospectives need this raw material to land.
> Reverse-chronological; one paragraph max per entry.

## 2026-11-13 — Second review: entry price, domicile, delay sensitivity #decision #milestone

A second outside review asked whether the copy strategy earns returns an investor could not capture: CRSP daily returns are close to close, so the entry day includes the overnight move before the open. Buying at the close of the entry day instead gives -2.23% a year at 62 days (t = -0.90), slightly more negative, so the null holds; it is reported beside the primary result, which stays as planned. The CRSP filter does not check issuer domicile; `pipeline.crsp` now fetches `usincflg`, 240 primary purchases (89 stocks) are non-US issuers, and dropping them gives -1.10% (t = -0.45). The refetch matched the first extract exactly. The 6.6% share past 45 days is no longer called a lower bound, since amendments could push it the other way; with the 100 trades disclosed after more than a year it is 7.3%, and with an earliest-filing duplicate rule 6.7%. Factor-file checksums are recorded in the results doc. The review's claim that the paper had no Zenodo DOI was stale: the draft records exist (paper 10.5281/zenodo.24185824, code 10.5281/zenodo.24197346) but are not yet published.

## 2026-11-12 — Review fixes: entry timing, five-factor, trade-to-entry #fix #decision

An outside review of the paper draft found that the copy portfolio entered one trading day after the first trading day on or after disclosure, so weekend and holiday disclosures entered a day late. `entry_day` (first trading day strictly after the date) fixes it; the primary alpha moved from -1.82% (t = -0.74) to -1.63% (t = -0.66), still null, and the day-0 CARs are unchanged. The planned five-factor check finally ran (62 days: -1.25%, t = -0.53). Added as exploratory: CARs over the holding window, Newey-West lags 21 and 62, an amount-minus-equal weight test (8.83%, t = 1.65), and the abnormal return from the trade to the copier's entry (-0.24%, t = -1.99, p = 0.046), which replaces the paper's claim that the gap between the two CAR series is the cost of waiting. The analysis now stops at `ANALYSIS_END` (2025-12-31). The paper also now says the House deadline is the earlier of 30 days after notification and 45 days after the trade, so the 6.6% is the share past the 45-day outer limit, and the sales check holds sold stocks long rather than shorting them. Resumes and other materials that quote -1.82% need updating.

## 2026-11-12 — Paper drafted for Zenodo #milestone #decision

`docs/paper/paper.tex` (12 pages) reports the event study as a working paper. Zenodo will hold its one DOI, so SSRN, if used, should link to that DOI instead of minting a second one. Reading the full texts changed the framing: Fischer and Sacerdote cover all 331 members to 2023, not only the top 15, and both they and Belmont et al. measure from the trade date, so the contribution is the disclosure-date calendar-time test, 2024 and 2025, and the pre-written plan. Q1 stays House-only, since Senate disclosure dates were not recovered. The five-factor check in the plan was not run, and the paper lists it as a departure. A rerun on 2026-11-12 reproduced every table; the projected intercept over 63 days averages +1.67% (median +0.79%) for disclosure-date events, which the paper uses in place of the earlier +1.65% / +0.83%. Figures are TikZ written by `docs/paper/make_figures.py` from `site/data/figures.json`, so the PDF builds without pgfplots or CRSP access. Funding, competing-interest and AI-use statements are left for the author to fill in.

## 2026-11-11 — Site v2: one dot per purchase #decision #pivot

The first rebuild read as timid once it was live: for half the page the plot was an empty grid with one dot on a line, and a flat mean line alone does not show why the null result is interesting. The stage is now a canvas where each of the 3,942 disclosed purchases is a dot. The dots fall onto the ground under the dome, leave for day 0 in filing order (drawn from the real lag histogram), then fan out into the day's spread of abnormal returns while the mean stays on zero; at day 62 the plot zooms in 18 times to the mean and its 95% band. `pipeline.site_figures` now also writes the 1st to 99th percentiles per day, still aggregates only. The palette went dark navy so the dots read as points of light. A shimmer on the dots was dropped because it cost too much frame time on phones.

## 2026-11-11 — Site rebuilt around event time #milestone #decision

The findings page still led with the retracted +2.58%, so it was rebuilt instead of patched. The page is now one event-study plot: scrolling moves through event time from the estimation window to day +125, and the mean abnormal return after disclosure draws itself inside its 95% band, which covers zero on all 126 days. The data comes from `pipeline.site_figures`, which writes aggregates only to `site/data/figures.json`; no CRSP stock-level return leaves the build machine. The Capitol dome, the filing stamp and the alpha mark were drawn in Glaxnimate; the stamp is a hand-keyed SMIL timeline that GSAP scrubs. Finance green went with the old claim, since it signalled a gain the study does not find. The spring 2025 PDFs stay on the site as a labelled archive. The GSAP files live in `site/lib/` because some sync tools skip folders named `vendor`, and the e2e server moved from port 8080 to 4317 to avoid a common clash.

## 2026-11-11 — Robustness checks hold the null; permno ties fixed #milestone #fix

Every robustness check in the plan is insignificant, and so are the market-model CARs. Amount weighting gives the largest positive estimate (7.12% a year, t = 1.43). Two fetches gave slightly different results (20-day alpha 1.93% vs 1.96%) because 14 purchases had two CRSP common-stock records on the trade date and an unstable sort picked between them. The lowest permno now wins and the count is printed. The 365 unmatched purchases are mostly ETFs, over-the-counter foreign shares, and closed-end funds.

## 2026-11-11 — No outperformance; CARs now use betas only #milestone #decision

The primary test is a null: the copy portfolio from disclosure earns -1.82% a year in four-factor alpha (t = -0.74, H = 62). The first run's event-level CARs were significantly negative, but that came from subtracting each stock's pre-event intercept, which the plan does not call for. Members buy stocks that had been beating the factor model, so the projected intercept averaged +1.65% over 63 days. `abnormal_returns` now removes factor exposure only, matching the plan's "betas", and every corrected CAR is insignificant. This change was made after seeing results, so the runner keeps printing the first run's table and `docs/results/event-study.md` reports both.

## 2026-11-11 — CRSP through WRDS is the price source #decision

WRDS access through Wesleyan includes CRSP in the CIZ format, with daily data through 2025-12-31. Before computing any return, the plan now fixes how tickers map to `permno` (by the record that covers the transaction date, since `META` was an ETF before Meta took it), defines common stock as `EQTY`/`COM`/`NS` with ADRs counted and excluded, and keeps CIZ delisting rows because `dlyret` already includes the delisting return. CRSP prices stay on the build machine and never enter the repository.

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
