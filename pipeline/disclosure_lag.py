"""Measure how long members take to disclose trades (Q3 in docs/specs/event-study.md).

Usage:
    python -m pipeline.disclosure_lag [--snapshot PATH]

The STOCK Act requires a periodic transaction report no later than 45 days
after the transaction. Prints Markdown tables for the paper.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .event_sample import DATE_FORMAT, END, EVENT_KEY, MAX_LAG_DAYS, SNAPSHOT, START, load_snapshot

DEADLINE_DAYS = 45


def disclosure_lags(trades: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Return trades with a usable lag, plus counts of the rows set aside."""
    df = trades.drop_duplicates(EVENT_KEY + ["transaction_type"]).copy()
    df["transaction_date"] = pd.to_datetime(
        df["transaction_date"], format=DATE_FORMAT, errors="coerce"
    )
    df["disclosure_date"] = pd.to_datetime(
        df["disclosure_date"], format=DATE_FORMAT, errors="coerce"
    )
    df = df[df["transaction_date"].between(START, END)]
    dated = df[df["disclosure_date"].notna()].copy()
    dated["lag_days"] = (dated["disclosure_date"] - dated["transaction_date"]).dt.days

    set_aside = {
        "no disclosure date": int(df["disclosure_date"].isna().sum()),
        "disclosed before the trade": int((dated["lag_days"] < 0).sum()),
        f"disclosed more than {MAX_LAG_DAYS} days later": int(
            (dated["lag_days"] > MAX_LAG_DAYS).sum()
        ),
    }
    lags = dated[dated["lag_days"].between(0, MAX_LAG_DAYS)].copy()
    lags["late"] = lags["lag_days"] > DEADLINE_DAYS
    return lags.reset_index(drop=True), set_aside


def summarize(lags: pd.DataFrame, by: str | None = None) -> pd.DataFrame:
    """Lag statistics overall, or for each value of ``by``."""
    key = by or "sample"
    data = lags if by else lags.assign(sample="All")
    table = data.groupby(key).agg(
        trades=("lag_days", "size"),
        median_days=("lag_days", "median"),
        p90_days=("lag_days", lambda s: s.quantile(0.9)),
        late=("late", "sum"),
        filings=("ptr_link", "nunique"),
        members=("legislator_name", "nunique"),
    )
    late_rows = data[data["late"]].groupby(key)
    for column, source in (("late_filings", "ptr_link"), ("members_ever_late", "legislator_name")):
        table[column] = late_rows[source].nunique().reindex(table.index, fill_value=0)
    table["late_share"] = table["late"] / table["trades"]
    return table


def to_markdown(table: pd.DataFrame, label: str) -> str:
    header = (
        f"| {label} | Trades | Median days | 90th pct days | Late trades (>45 days) "
        "| Late share | Filings | Late filings | Members | Members ever late |"
    )
    lines = [header, "| --- |" + " ---: |" * 9]
    for row in table.itertuples():
        lines.append(
            f"| {row.Index} | {row.trades:,} | {row.median_days:g} | {row.p90_days:g} "
            f"| {row.late:,} | {row.late_share:.1%} | {row.filings:,} | {row.late_filings:,} "
            f"| {row.members:,} | {row.members_ever_late:,} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Summarize disclosure lags.")
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    args = parser.parse_args(argv)

    lags, set_aside = disclosure_lags(load_snapshot(args.snapshot))
    lags["year"] = lags["transaction_date"].dt.year
    print("Set aside:", ", ".join(f"{label} {count:,}" for label, count in set_aside.items()))
    for label, by in (("Sample", None), ("Chamber", "chamber"), ("Year", "year")):
        print()
        print(to_markdown(summarize(lags, by), label))


if __name__ == "__main__":
    main()
