from pathlib import Path

import pandas as pd

from .config import OUTPUT_CSV
from .senate_fetcher import _parse_amount_range, get_senate_df
from .house_fetcher import get_house_df
from .ingestion import publish_csvs

COLUMN_ORDER = [
    "chamber",
    "legislator_name",
    "transaction_date",
    "disclosure_date",
    "ticker",
    "asset_description",
    "asset_type",
    "transaction_type",
    "amount_range",
    "amount_min",
    "amount_max",
    "amount_avg",
    "owner",
    "ptr_link",
    "office",
    "party",
    "state",
    "transaction_year",
    "disclosure_year",
    "comment",
]


def clean_dataframe(df):
    """Clean and normalize a merged dataframe."""
    if df.empty:
        return df

    df = df.copy()

    # Convert completely empty strings or whitespace-only strings to genuine NaNs
    df = df.replace(r"^\s*$", pd.NA, regex=True)

    def _normalize_string(value):
        if pd.isna(value):
            return None
        v = str(value).strip()
        return v if v else None

    df["legislator_name"] = df["legislator_name"].apply(_normalize_string)
    df["ticker"] = df["ticker"].apply(
        lambda v: _normalize_string(v).upper() if _normalize_string(v) else None
    )
    df["ticker"] = df["ticker"].replace({"--": None, "N/A": None, "NA": None})

    transaction_map = {
        "p": "Purchase",
        "s": "Sale",
        "s (partial)": "Sale",
        "s (full)": "Sale",
        "e": "Exchange",
        "sale (full)": "Sale",
        "sale (partial)": "Sale",
        "sale": "Sale",
        "purchase": "Purchase",
        "exchange": "Exchange",
    }
    df["transaction_type"] = (
        df["transaction_type"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .map(transaction_map)
        .fillna(df["transaction_type"])
    )

    df["owner"] = df["owner"].fillna("").astype(str).str.strip().str.title().replace({"": None})

    df = df[
        df["transaction_date"].notna() & (df["ticker"].notna() | df["asset_description"].notna())
    ]

    df = df.drop_duplicates().copy()

    if "amount_range" in df.columns:
        ranges = df["amount_range"].apply(
            lambda value: _parse_amount_range(value) if isinstance(value, str) else (None, None)
        )
        for column, index in (("amount_min", 0), ("amount_max", 1)):
            parsed = ranges.apply(lambda bounds: bounds[index])
            df[column] = (
                pd.to_numeric(df[column], errors="coerce").fillna(parsed)
                if column in df.columns
                else parsed
            )
        midpoint = (df["amount_min"] + df["amount_max"]) / 2
        df["amount_avg"] = (
            pd.to_numeric(df["amount_avg"], errors="coerce").fillna(midpoint)
            if "amount_avg" in df.columns
            else midpoint
        )

    for col in ["amount_min", "amount_max", "amount_avg"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def merge_to_csv(
    senate_df=None,
    house_df=None,
    output_path=None,
    use_cache=True,
    write_output=True,
):
    """Merge Senate/House dataframes into canonical output CSV.

    If dataframes are not provided, this function loads from the fetcher
    utilities (with caching behavior controlled by use_cache).
    It ensures a stable column order and writes the merged dataset.
    """
    output_path = output_path or str(OUTPUT_CSV)
    if senate_df is None:
        senate_df = get_senate_df(from_cache=use_cache)
    if house_df is None:
        house_df = get_house_df(from_cache=use_cache)
    dfs = [d for d in (senate_df, house_df) if d is not None and not d.empty]
    if not dfs:
        merged = pd.DataFrame(columns=COLUMN_ORDER)
    else:
        merged = pd.concat(dfs, ignore_index=True)
    merged = clean_dataframe(merged)
    merged = merged.reindex(columns=COLUMN_ORDER).drop_duplicates().reset_index(drop=True)

    if write_output:
        publish_csvs({Path(output_path): merged})
    return merged
