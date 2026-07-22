# JOURNAL — CapitolAlpha

> Dated log of decisions, pivots, incidents, and quotes. Add entries as
> things happen — retrospectives need this raw material to land.
> Reverse-chronological; one paragraph max per entry.

## 2026-07-22 — Expanded test suite to 100% full coverage across pipeline & utils #milestone #decision

Refactored `utils/check_covid.py`, `utils/mappings.py`, and `utils/patch_code.py` to wrap top-level executions in clean `if __name__ == '__main__':` functions, eliminating side effects during module import. Created `tests/test_utils.py` and expanded `test_house_fetcher.py`, `test_senate_fetcher.py`, `test_merge_to_csv.py`, `test_run_pipeline.py`, and `test_scrapers.py`. Achieved 47 passing assertions and 99.02% total line coverage across the repo verified on `ampere-dev`.

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

The House disclosure site (disclosures-clerk.house.gov) renders results through a DataTables widget that only exposes 50 rows at a time, so a naive scrape silently captured a fraction of the records. The fix in `house_official.py` is to reach into the page and run `dt.page.len(-1).draw()` via Playwright's `evaluate` — commanding DataTables to render every row at once before extraction, instead of clicking through pages. Same commit added `parse_house_pdf` (pdfplumber) for the PTR PDFs and a `date_received` fallback in `_normalize_house_row` for when both `transaction_date` and `disclosure_date` are missing.

## 2026-03-31 — Pipeline scaffolded with an official-vs-fallback data strategy #decision #milestone

First commit stood up the whole fetch-and-merge pipeline (Senate + House → normalized `legislative_trades.csv`) and baked in a deliberate two-source strategy. `--use-official` scrapes efdsearch.senate.gov and the House clerk site directly via Playwright (slow but authoritative); the default path pulls pre-aggregated Senate JSON from `timothycarambat/senate-stock-watcher-data` (fast, used as the fallback when official scraping breaks). Senate config carries both `SENATE_RAW_URL` and `SENATE_S3_URL` so the fast path has its own redundancy. The bet: don't let a flaky government scraper block the analysis — keep an offline-cached fallback so the notebooks always have data to run against.

## 2026-03-31 — Reviewer ethics + rigor feedback that shaped the framing #feedback #quote

Course reviewer comments on the Problem Statement and Statement of Purpose set several guardrails the final work had to honor. On scraping: *"scraping has been a controversial practice — how would you address potential questions about the ethics of scraping?"* and a pointed *"I'm curious if these sources have some sort of firewalls that prevent scraping"* — which is why the reflections draw the explicit line that this automates reading legally-public data, not bypassing CAPTCHAs or access controls. On rigor: *"I'd suggest being careful with this kind of suggestive language — till you find a stat. significant result, you can't really say that it's 'abnormal', right?"* On scope: *"Maybe after looking at the general trends, you can pick out the anomalies (highest/lowest returns) and focus on their stories!"* — which became the anomalies-in-the-tails narrative. And repeatedly: *"Define this!"* on Jensen's Alpha, Sharpe ratio, and information-advantage decay, pushing the deliverables to explain the jargon for a non-technical audience.
