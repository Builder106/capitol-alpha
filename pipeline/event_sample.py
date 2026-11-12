"""Build the purchase event sample defined in docs/specs/event-study.md.

Usage:
    python -m pipeline.event_sample [--snapshot PATH] [--out PATH]

Prints the sample-flow table and writes one row per purchase event.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import pandas as pd

from .config import DATA_DIR

SNAPSHOT = DATA_DIR / "snapshots" / "legislative_trades_821d6e5.csv"
EVENTS = DATA_DIR / "purchase_events.csv"

PURCHASE_CODES = {"p", "purchase"}
SIDES = {
    "purchase": (PURCHASE_CODES, "purchases (P or Purchase)"),
    "sale": ({"s", "s (partial)", "sale"}, "sales (S, S (partial), or Sale)"),
}
NON_STOCK_TYPES = {"stock option", "other securities"}
TICKER = r"[A-Z]{1,5}"
OPTION = r"\boptions?\b"
DATE_FORMAT = "%m/%d/%Y"
START = pd.Timestamp("2020-01-01")
END = pd.Timestamp("2025-12-31")
MAX_LAG_DAYS = 365
EVENT_KEY = ["legislator_name", "owner", "ticker", "transaction_date", "amount_range"]

Flow = list[tuple[str, int]]


def normalize_padded_csv(src: Path, dst: Path) -> int:
    """Rewrite a space-padded CSV as a plain CSV and return the row count.

    The original export pads every field, so a quoted field starts with a
    space and only parses with ``skipinitialspace``.
    """
    with src.open(newline="", encoding="utf-8") as handle:
        rows = [[cell.strip() for cell in row] for row in csv.reader(handle, skipinitialspace=True)]
    width = len(rows[0])
    bad = [i for i, row in enumerate(rows) if len(row) != width]
    if bad:
        raise ValueError(f"{len(bad)} rows do not have {width} fields, first at line {bad[0] + 1}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(rows)
    return len(rows) - 1


def load_snapshot(path: Path = SNAPSHOT) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def build_events(trades: pd.DataFrame, side: str = "purchase") -> tuple[pd.DataFrame, Flow]:
    """Apply the sample rules in order and count the rows left after each."""
    codes, side_label = SIDES[side]
    df = trades
    flow: Flow = [("rows in snapshot", len(df))]

    def keep(mask: pd.Series, label: str) -> None:
        nonlocal df
        df = df[mask]
        flow.append((label, len(df)))

    keep(df["transaction_type"].str.lower().isin(codes), side_label)
    keep(df["ticker"].str.fullmatch(TICKER), "valid ticker")
    keep(
        ~df["asset_type"].str.lower().isin(NON_STOCK_TYPES)
        & ~df["asset_description"].str.contains(OPTION, case=False, regex=True),
        "stock (no options or other securities)",
    )
    transacted = pd.to_datetime(df["transaction_date"], format=DATE_FORMAT, errors="coerce")
    keep(transacted.between(START, END), "transaction date 2020-01-01 to 2025-12-31")
    keep(~df.duplicated(EVENT_KEY), "after removing duplicates")

    events = df.assign(side=side)
    events["transaction_date"] = pd.to_datetime(events["transaction_date"], format=DATE_FORMAT)
    events["disclosure_date"] = pd.to_datetime(
        events["disclosure_date"], format=DATE_FORMAT, errors="coerce"
    )
    lag = (events["disclosure_date"] - events["transaction_date"]).dt.days
    events["lag_days"] = lag.astype("Int64")
    events["q1_eligible"] = lag.between(0, MAX_LAG_DAYS)

    flow += [
        ("  no disclosure date", int(events["disclosure_date"].isna().sum())),
        ("  disclosed before the trade", int((lag < 0).sum())),
        (f"  disclosed more than {MAX_LAG_DAYS} days later", int((lag > MAX_LAG_DAYS).sum())),
        ("eligible for Q1 (disclosure lag 0 to 365 days)", int(events["q1_eligible"].sum())),
    ]
    return events.reset_index(drop=True), flow


def format_flow(flow: Flow) -> str:
    width = max(len(label) for label, _ in flow)
    return "\n".join(f"{label:<{width}}  {count:>6,}" for label, count in flow)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build the purchase event sample.")
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    parser.add_argument("--out", type=Path, default=EVENTS)
    args = parser.parse_args(argv)

    events, flow = build_events(load_snapshot(args.snapshot))
    print(format_flow(flow))
    events.to_csv(args.out, index=False, date_format="%Y-%m-%d")
    print(f"\n{len(events):,} events -> {args.out}")


if __name__ == "__main__":
    main()
