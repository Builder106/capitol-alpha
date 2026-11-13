# Contributing

This repo is the submission for **QAC 420 (*Data for Good*)** at Wesleyan, Spring 2025. The findings and the deliverables in `docs/` reflect what was submitted at end of term and are not changing.

The pipeline is open source and reusable. Bug fixes, fetcher resilience improvements, and follow-on analyses are welcome.

## Development setup

```bash
uv sync --group dev
uv run playwright install chromium
```

Run the full pipeline (official-source mode is slow but authoritative):

```bash
python -m pipeline.run_pipeline --use-official
```

Or use the pre-aggregated Senate JSON fallback (no Playwright needed):

```bash
python -m pipeline.run_pipeline
```

Run the tests:

```bash
pytest
```

Pipeline-level options (`--fresh`, `--senate-only`, `--house-only`, `--use-official`) are documented in [`pipeline/README_PIPELINE.md`](pipeline/README_PIPELINE.md).

## Project-specific guardrails

- **The official scrapers are the contract.** `efdsearch.senate.gov` and `disclosures-clerk.house.gov` change their HTML and PDF layouts roughly twice a year. When a fetcher breaks, fix it next to the selector logic in `pipeline/senate_fetcher.py` or `pipeline/house_fetcher.py`. Don't make a third-party paid API the primary source; the *Data for Good* frame is "public data, public methods."
- **PTR amount ranges are ranges, not point estimates.** Many disclosure forms report a band ("$15,001 &ndash; $50,000"). The pipeline keeps `amount_min`, `amount_max`, and a derived `amount_avg`; analyses should declare which one they use and never silently swap.
- **Ticker resolution is best-effort.** Asset descriptions are free text. The current matcher resolves common cases and drops ambiguous ones. Don't introduce fuzzy matching without a deliberate audit; false matches can corrupt the alpha calculation without an obvious error.
- **Tests use cached HTML/PDF fixtures, not live HTTP.** New fetcher tests should add a fixture under `tests/fixtures/`, not hit the network.
- **The cleaned `data/legislative_trades.csv` is the analysis surface.** Notebooks read from it, not from the raw scraper output. If you change the schema, update the notebooks in the same PR.

## Commit conventions

The existing log uses short imperative subjects. Examples:

```text
Add Final Reflection document on U.S. Congress Stock Trade Analysis
Update flourish_captions.csv to correct date ranges and improve timeline accuracy
Add CapitolAlpha abstract LaTeX source and compiled PDF
```

Match that. No Conventional Commits prefix. No AI co-author trailer.

## PR process

1. Open an issue first for anything beyond a one-file fix &mdash; the project is course-frozen but you and I should still agree on scope before code review.
2. Run `pytest` locally before opening the PR.
3. CI (ruff + pytest) must be green.
4. Squash-merge into `main`.

## Scope

**In scope:**

- Bug fixes in `pipeline/senate_fetcher.py`, `pipeline/house_fetcher.py`, `pipeline/merge_to_csv.py`.
- Resilience against HTML/PDF layout changes on the official disclosure sites.
- Test coverage expansions (new fixture-based tests).
- Performance improvements that don't change results.
- New analyses in `notebooks/` that use the existing `legislative_trades.csv` schema unchanged.
- Documentation and README clarifications.

**Out of scope:**

- Replacing the headline findings, the Jensen's-alpha specification, or the cohort definitions. Those are part of the course submission and are not changing.
- Switching the analysis stack (e.g. R or Julia rewrite). The point of the repo is the reproducible Python pipeline as submitted.
- Re-running against newer disclosure data and rewriting the findings. That's a fork, not a PR.
- Adding non-public data sources (paid PTR aggregators, brokerage-leak datasets). The "public data, public methods" frame is load-bearing.

If you're unsure where your change lands, open an issue and ask before coding.
