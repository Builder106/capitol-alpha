import json
from datetime import datetime

import requests
import pandas as pd

from .config import SENATE_RAW_URL, SENATE_S3_URL, DATA_DIR, MIN_YEAR, MAX_YEAR

SENATE_JSON_PATH = DATA_DIR / "senate_all_transactions.json"


def _parse_date(s):
    """Convert date string to year integer.

    Supports several representations typically found in the raw data.
    Returns None for invalid or missing values.
    """
    if not s or not isinstance(s, str):
        return None
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


def _flatten_senate_raw(raw):
    """Flatten nested Senate JSON (reports with transaction arrays) into row list."""
    rows = []
    for item in raw:
        if "transactions" in item:
            senator = {k: v for k, v in item.items() if k != "transactions"}
            for t in item.get("transactions") or []:
                rows.append({**senator, **t})
        else:
            rows.append(item)
    return rows


def _parse_party_state(office):
    if not office or not isinstance(office, str):
        return None, None
    # common format: "D-CA", "R-OH", "I-VT"
    parts = office.strip().split("-")
    if len(parts) == 2 and len(parts[1]) == 2:
        party = parts[0].upper()
        state = parts[1].upper()
        return party, state
    return None, None


def _normalize_senate_row(r):
    trans_date = r.get("transaction_date") or r.get("transaction_date_date")
    name = (
        r.get("senator")
        or f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
        or r.get("senator_name")
        or r.get("office")
        or ""
    )
    amount_raw = r.get("amount") or r.get("amount_range")
    amount_min, amount_max = _parse_amount_range(amount_raw)
    amount_avg = None
    if amount_min is not None and amount_max is not None:
        amount_avg = (amount_min + amount_max) / 2

    office = r.get("office")
    party, state = _parse_party_state(office)

    return {
        "chamber": "Senate",
        "legislator_name": name,
        "disclosure_date": r.get("date_recieved") or r.get("date_received"),
        "transaction_date": trans_date,
        "ticker": (r.get("ticker") or "").strip() or None,
        "asset_description": r.get("asset_description"),
        "asset_type": r.get("asset_type"),
        "transaction_type": r.get("type"),
        "amount_range": amount_raw,
        "amount_min": amount_min,
        "amount_max": amount_max,
        "amount_avg": amount_avg,
        "owner": r.get("owner"),
        "ptr_link": r.get("ptr_link"),
        "office": office,
        "party": party,
        "state": state,
        "comment": r.get("comment"),
    }


def fetch_senate(save_raw=True):
    if not SENATE_JSON_PATH.exists():
        raise FileNotFoundError(
            f"Local Senate data file not found at {SENATE_JSON_PATH}. "
            "Please run with --use-official to scrape or place the JSON file there."
        )
    with open(SENATE_JSON_PATH) as f:
        raw = json.load(f)

    flat = _flatten_senate_raw(raw) if raw else []
    rows = [_normalize_senate_row(r) for r in flat]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["transaction_year"] = df["transaction_date"].apply(_parse_date)
    df["disclosure_year"] = df["disclosure_date"].apply(_parse_date)
    mask = df["transaction_year"].notna()
    df = df.loc[mask & (df["transaction_year"] >= MIN_YEAR) & (df["transaction_year"] <= MAX_YEAR)]
    return df


def get_senate_df(from_cache=True):
    if SENATE_JSON_PATH.exists():
        with open(SENATE_JSON_PATH) as f:
            raw = json.load(f)
        flat = _flatten_senate_raw(raw) if isinstance(raw, list) else []
        if not flat and isinstance(raw, list):
            flat = raw
        rows = [_normalize_senate_row(r) for r in flat]
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
        f"Local Senate data file not found at {SENATE_JSON_PATH}. "
        "Please provide it first or run --use-official to scrape official sources."
    )
