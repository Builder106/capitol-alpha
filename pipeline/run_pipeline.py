import argparse

import pandas as pd

from .config import DATA_DIR, OUTPUT_CSV, MIN_YEAR, MAX_YEAR
from .senate_fetcher import SENATE_JSON_PATH, fetch_senate, get_senate_df
from .house_fetcher import HOUSE_JSON_PATH, fetch_house, get_house_df
from .merge_to_csv import merge_to_csv


def run(
    fresh=False,
    senate_only=False,
    house_only=False,
    use_official=False,
):
    """Run the legislative trades pipeline.

    This function coordinates the entire workflow:
    - official scraping path when --use-official or when local JSON is missing
    - cached local JSON-based path when available
    - per-chamber output modes (senate-only, house-only)
    - final merge to combined CSV for both chambers

    fresh: if True, ignore local caches and re-fetch.
    senate_only: process only Senate data.
    house_only: process only House data.
    use_official: scrape official sites with Playwright.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    use_cache = not fresh

    if not use_official:
        senate_missing = not SENATE_JSON_PATH.exists()
        house_missing = not HOUSE_JSON_PATH.exists()

        if (
            (not senate_only and not house_only and (senate_missing or house_missing))
            or (senate_only and senate_missing)
            or (house_only and house_missing)
        ):
            print("Local raw JSON missing; switching to official scraper to gather data.")
            return run(
                fresh=fresh,
                senate_only=senate_only,
                house_only=house_only,
                use_official=True,
            )

    if use_official:
        from .scrapers import SenateOfficialScraper, HouseOfficialScraper

        senate_df = None
        house_df = None
        if not house_only:
            print("Scraping efdsearch.senate.gov ...")
            with SenateOfficialScraper(headless=True) as scraper:
                senate_df = scraper.scrape()
            out_s = DATA_DIR / "senate_trades.csv"
            if senate_df is not None and not senate_df.empty:
                from .merge_to_csv import clean_dataframe

                senate_df = clean_dataframe(senate_df)
                senate_df.to_csv(out_s, index=False)
                print(f"Senate: {len(senate_df)} trades -> {out_s}")
        if not senate_only:
            print("Scraping disclosures-clerk.house.gov ...")
            with HouseOfficialScraper(headless=True) as scraper:
                house_df = scraper.scrape()
            out_h = DATA_DIR / "house_trades.csv"
            if house_df is not None and not house_df.empty:
                from .merge_to_csv import clean_dataframe

                house_df = clean_dataframe(house_df)
                house_df.to_csv(out_h, index=False)
                print(f"House: {len(house_df)} disclosure records -> {out_h}")
        if not senate_only and not house_only:
            merged = merge_to_csv(
                senate_df=senate_df
                if senate_df is not None and not senate_df.empty
                else pd.DataFrame(),
                house_df=house_df
                if house_df is not None and not house_df.empty
                else pd.DataFrame(),
            )
            merged.to_csv(OUTPUT_CSV, index=False)
            print(f"Merged: {len(merged)} rows -> {OUTPUT_CSV}")
        return

    if senate_only:
        df = get_senate_df(from_cache=use_cache) if use_cache else fetch_senate(save_raw=True)
        out = DATA_DIR / "senate_trades.csv"
        df.to_csv(out, index=False)
        print(f"Senate: {len(df)} trades -> {out}")
        return
    if house_only:
        df = get_house_df(from_cache=use_cache) if use_cache else fetch_house(save_raw=True)
        out = DATA_DIR / "house_trades.csv"
        df.to_csv(out, index=False)
        print(f"House: {len(df)} trades -> {out}")
        return
    merged = merge_to_csv(use_cache=use_cache)
    print(f"Total: {len(merged)} trades ({MIN_YEAR}-{MAX_YEAR}) -> {OUTPUT_CSV}")
    if not merged.empty:
        by_chamber = merged.groupby("chamber").size()
        for chamber, count in by_chamber.items():
            print(f"  {chamber}: {count}")


def main():
    p = argparse.ArgumentParser(
        description="Capitol Alpha: fetch legislative trades and merge to CSV"
    )
    p.add_argument("--fresh", action="store_true", help="Re-download data instead of using cache")
    p.add_argument("--senate-only", action="store_true", help="Fetch only Senate data")
    p.add_argument("--house-only", action="store_true", help="Fetch only House data")
    p.add_argument(
        "--use-official",
        action="store_true",
        help="Scrape clerk.house.gov and efd.senate.gov (requires Playwright)",
    )
    args = p.parse_args()
    run(
        fresh=args.fresh,
        senate_only=args.senate_only,
        house_only=args.house_only,
        use_official=args.use_official,
    )


if __name__ == "__main__":
    main()
