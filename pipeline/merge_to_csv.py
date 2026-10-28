import pandas as pd

from .config import OUTPUT_CSV
from .senate_fetcher import get_senate_df
from .house_fetcher import get_house_df

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
    df.replace(r"^\s*$", pd.NA, regex=True, inplace=True)

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

    for col in ["amount_min", "amount_max", "amount_avg"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def merge_to_csv(
    senate_df=None,
    house_df=None,
    output_path=None,
    use_cache=True,
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
    existing = [c for c in COLUMN_ORDER if c in merged.columns]
    merged = merged[existing]

    merged = clean_dataframe(merged)

    merged.to_csv(output_path, index=False, date_format="%Y-%m-%d")
    return merged
