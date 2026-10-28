import json
import requests
import pandas as pd

from .config import DATA_DIR, HOUSE_S3_URL, MIN_YEAR, MAX_YEAR
from .senate_fetcher import _parse_party_state

HOUSE_JSON_PATH = DATA_DIR / "house_all_transactions.json"


def _parse_date(s):
    """Convert date string to year integer, supporting multiple formats."""
    if not s or not isinstance(s, str):
        return None
    from datetime import datetime

    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(s.strip(), fmt).year
        except ValueError:
            continue
    return None


def _parse_amount_range(value):
    if not value or not isinstance(value, str):
        return None, None
    s = value.strip().replace("$", "").replace(",", "").lower()
    if s in ("", "n/a", "unknown", "--"):
        return None, None
    if " - " in s:
        try:
            lo, hi = s.split(" - ", 1)
            return float(lo), float(hi)
        except ValueError:
            return None, None
    if s.endswith("+"):
        try:
            return float(s[:-1]), None
        except ValueError:
            return None, None
    try:
        v = float(s)
        return v, v
    except ValueError:
        return None, None


def _normalize_house_row(r):
    trans_date = r.get("transaction_date") or r.get("disclosure_date") or r.get("date_received")
    name = r.get("representative") or r.get("legislator_name") or r.get("name") or ""
    if not name and (r.get("first_name") or r.get("last_name")):
        name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
    amount_raw = r.get("amount") or r.get("amount_range")
    amount_min, amount_max = _parse_amount_range(amount_raw)
    amount_avg = None
    if amount_min is not None and amount_max is not None:
        amount_avg = (amount_min + amount_max) / 2
    office = r.get("office")
    party, state = _parse_party_state(office)
    return {
        "chamber": "House",
        "legislator_name": name,
        "disclosure_date": r.get("disclosure_date") or r.get("date_received"),
        "transaction_date": trans_date,
        "ticker": (r.get("ticker") or "").strip() or None,
        "asset_description": r.get("asset_description") or r.get("asset_name"),
        "asset_type": r.get("asset_type") or r.get("type"),
        "transaction_type": r.get("type") or r.get("transaction_type"),
        "amount_range": amount_raw,
        "amount_min": amount_min,
        "amount_max": amount_max,
        "amount_avg": amount_avg,
        "owner": r.get("owner"),
        "ptr_link": r.get("ptr_link") or r.get("disclosure_link") or r.get("link"),
        "office": office,
        "party": party,
        "state": state,
        "comment": r.get("comment"),
    }


def fetch_house(save_raw=True, timeout=120):
    if not HOUSE_JSON_PATH.exists():
        raise FileNotFoundError(
            f"Local House data file not found at {HOUSE_JSON_PATH}. "
            "Please run with --use-official to scrape or place the JSON file there."
        )
    with open(HOUSE_JSON_PATH) as f:
        raw = json.load(f)
    if not raw:
        return pd.DataFrame()
    if isinstance(raw, list):
        rows = [_normalize_house_row(r) for r in raw]
    else:
        rows = [_normalize_house_row(r) for r in raw.get("transactions", raw.get("data", []))]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["transaction_year"] = df["transaction_date"].apply(_parse_date)
    df["disclosure_year"] = df["disclosure_date"].apply(_parse_date)
    mask = df["transaction_year"].notna()
    df = df.loc[mask & (df["transaction_year"] >= MIN_YEAR) & (df["transaction_year"] <= MAX_YEAR)]
    return df


def get_house_df(from_cache=True):
    if HOUSE_JSON_PATH.exists():
        with open(HOUSE_JSON_PATH) as f:
            raw = json.load(f)
        if isinstance(raw, list):
            rows = [_normalize_house_row(r) for r in raw]
        else:
            rows = [_normalize_house_row(r) for r in raw.get("transactions", raw.get("data", []))]
        df = pd.DataFrame(rows)
        if not df.empty:
            df["transaction_year"] = df["transaction_date"].apply(_parse_date)
            df["disclosure_year"] = df["disclosure_date"].apply(_parse_date)
            mask = df["transaction_year"].notna()
            df = df.loc[
                mask & (df["transaction_year"] >= MIN_YEAR) & (df["transaction_year"] <= MAX_YEAR)
            ]
            return df
    raise FileNotFoundError(
        f"Local House data file not found at {HOUSE_JSON_PATH}. "
        "Please provide it first or run --use-official to scrape official sources."
    )
