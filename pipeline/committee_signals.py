"""Offline, disclosure-time committee/sector associations and directional signals."""

import argparse
from datetime import date, timedelta
from math import sqrt
from pathlib import Path

import pandas as pd

from .ingestion import publish_csvs

TRADE_COLUMNS = (
    "chamber",
    "legislator_name",
    "transaction_date",
    "disclosure_date",
    "ticker",
    "transaction_type",
)
ASSIGNMENT_COLUMNS = ("chamber", "legislator_name", "committee", "start_date", "end_date")
OUTPUT_COLUMNS = (
    "as_of",
    "window_start",
    "chamber",
    "committee",
    "sector",
    "eligible_trades",
    "member_sector_trades",
    "member_other_trades",
    "nonmember_sector_trades",
    "nonmember_other_trades",
    "phi",
    "purchases",
    "sales",
    "net_purchase_ratio",
    "min_trades",
    "signal",
)


def _columns(frame: pd.DataFrame, columns: tuple[str, ...], label: str) -> pd.DataFrame:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{label}: missing columns: {', '.join(missing)}")
    return frame.loc[:, list(columns)].copy()


def _normalize(frame: pd.DataFrame, columns: tuple[str, ...]) -> None:
    for column in columns:
        frame[column] = (
            frame[column]
            .astype("string")
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
            .str.casefold()
            .replace("", pd.NA)
        )


def _dates(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values, format="%Y-%m-%d", errors="coerce")


def generate_committee_signals(
    trades: pd.DataFrame,
    assignments: pd.DataFrame,
    ticker_sectors: pd.DataFrame,
    committee_sectors: pd.DataFrame,
    *,
    as_of: date,
    lookback_days: int = 90,
    min_trades: int = 3,
) -> pd.DataFrame:
    """Compare membership and sector trading within each chamber.

    Membership is evaluated on the transaction date (inclusive interval bounds).
    Only purchases/sales disclosed in the inclusive trailing disclosure window
    are eligible. Reference tables must describe complete historical membership
    for the cohort; unmatched members form the nonmember comparison group.
    See docs/METHODOLOGY.md for the equations and reference-data limitations.
    """
    if lookback_days < 1 or min_trades < 1:
        raise ValueError("lookback_days and min_trades must be positive")
    window_start = as_of - timedelta(days=lookback_days - 1)
    # Deduplicate complete canonical records, preserving distinct reported trades.
    clean = _columns(trades.drop_duplicates(), TRADE_COLUMNS, "trades")
    members = _columns(assignments, ASSIGNMENT_COLUMNS, "assignments")
    sectors = _columns(ticker_sectors, ("ticker", "sector"), "ticker_sectors")
    jurisdictions = _columns(
        committee_sectors, ("chamber", "committee", "sector"), "committee_sectors"
    )
    _normalize(clean, ("chamber", "legislator_name", "ticker", "transaction_type"))
    _normalize(members, ("chamber", "legislator_name", "committee"))
    _normalize(sectors, ("ticker", "sector"))
    _normalize(jurisdictions, ("chamber", "committee", "sector"))
    for label, frame, required in (
        ("assignments", members, ("chamber", "legislator_name", "committee")),
        ("ticker_sectors", sectors, ("ticker", "sector")),
        ("committee_sectors", jurisdictions, ("chamber", "committee", "sector")),
    ):
        if frame[list(required)].isna().any().any():
            raise ValueError(f"{label}: reference keys must be nonempty")
    for frame in (members, jurisdictions):
        if not frame["chamber"].isin(["house", "senate"]).all():
            raise ValueError("reference chamber must be House or Senate")
    members["start_date"] = _dates(members["start_date"])
    open_end = members["end_date"].isna() | members["end_date"].astype("string").str.strip().eq("")
    members["end_date"] = _dates(members["end_date"].mask(open_end))
    if (
        members["start_date"].isna().any()
        or (members["end_date"].isna() & ~open_end).any()
        or (members["end_date"] < members["start_date"]).any()
    ):
        raise ValueError("assignments: invalid dates or reversed membership interval")
    sectors = sectors.drop_duplicates()
    if sectors["ticker"].duplicated().any():
        raise ValueError("ticker_sectors: each ticker must map to one sector")
    jurisdictions = jurisdictions.drop_duplicates().sort_values(["chamber", "committee", "sector"])
    clean["transaction_date"] = _dates(clean["transaction_date"])
    clean["disclosure_date"] = _dates(clean["disclosure_date"])
    clean = clean[
        clean["chamber"].isin(["house", "senate"])
        & clean["legislator_name"].notna()
        & clean["transaction_type"].isin(["purchase", "sale"])
        & clean["disclosure_date"].between(pd.Timestamp(window_start), pd.Timestamp(as_of))
        & (clean["transaction_date"] <= clean["disclosure_date"])
    ].merge(sectors, on="ticker", how="inner", validate="many_to_one")
    clean = clean.reset_index(drop=True)
    rows: list[dict[str, str | int | float | None]] = []
    for jurisdiction in jurisdictions.itertuples(index=False):
        cohort = clean[clean["chamber"] == jurisdiction.chamber]
        intervals = members[
            (members["chamber"] == jurisdiction.chamber)
            & (members["committee"] == jurisdiction.committee)
        ]
        # Union intervals instead of expanding trades through a many-to-many join.
        is_member = pd.Series(False, index=cohort.index)
        for interval in intervals.itertuples(index=False):
            is_member |= (
                (cohort["legislator_name"] == interval.legislator_name)
                & (cohort["transaction_date"] >= interval.start_date)
                & (pd.isna(interval.end_date) | (cohort["transaction_date"] <= interval.end_date))
            ).fillna(False)
        in_sector = cohort["sector"] == jurisdiction.sector
        a = int((is_member & in_sector).sum())
        b = int((is_member & ~in_sector).sum())
        c = int((~is_member & in_sector).sum())
        d = int((~is_member & ~in_sector).sum())
        denominator = sqrt((a + b) * (c + d) * (a + c) * (b + d))
        matched = cohort[is_member & in_sector]
        purchases = int((matched["transaction_type"] == "purchase").sum())
        sales = a - purchases
        ratio = (purchases - sales) / a if a else None
        signal = "insufficient_data"
        if a >= min_trades:
            signal = "buy" if purchases > sales else "sell" if sales > purchases else "neutral"
        rows.append(
            {
                "as_of": as_of.isoformat(),
                "window_start": window_start.isoformat(),
                "chamber": jurisdiction.chamber,
                "committee": jurisdiction.committee,
                "sector": jurisdiction.sector,
                "eligible_trades": len(cohort),
                "member_sector_trades": a,
                "member_other_trades": b,
                "nonmember_sector_trades": c,
                "nonmember_other_trades": d,
                "phi": (a * d - b * c) / denominator if denominator else None,
                "purchases": purchases,
                "sales": sales,
                "net_purchase_ratio": ratio,
                "min_trades": min_trades,
                "signal": signal,
            }
        )
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", type=Path, required=True)
    parser.add_argument("--assignments", type=Path, required=True)
    parser.add_argument("--ticker-sectors", type=Path, required=True)
    parser.add_argument("--committee-sectors", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--lookback-days", type=int, default=90)
    parser.add_argument("--min-trades", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    inputs = [args.trades, args.assignments, args.ticker_sectors, args.committee_sectors]
    if args.output.resolve() in [path.resolve() for path in inputs]:
        raise ValueError("output must not overwrite an input CSV")
    result = generate_committee_signals(
        *(pd.read_csv(path, dtype="string") for path in inputs),
        as_of=args.as_of,
        lookback_days=args.lookback_days,
        min_trades=args.min_trades,
    )
    publish_csvs({args.output: result})


if __name__ == "__main__":
    main()
