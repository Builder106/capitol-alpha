"""Positive control from docs/specs/insider-control.md: copy insider purchases.

Usage:
    python -m pipeline.insider_control --data-dir DIR [--sec-dir SEC --user NAME]

With --sec-dir and --user, reads the SEC Insider Transactions Data Sets in SEC,
builds the purchase events, matches them to CRSP through WRDS (credentials in
~/.pgpass), and writes events.csv, returns.csv.gz and excluded.csv to DIR. It
then runs the Q1 copy portfolio on those events and prints Markdown tables.
The SEC files and the CRSP extract are not part of the repository.
"""

from __future__ import annotations

import argparse
import csv
import zipfile
from pathlib import Path

import pandas as pd

from . import crsp
from .event_sample import END, START, Flow, format_flow
from .event_study import HORIZONS, calendar_time_alpha, download_factors
from .run_event_study import (
    ANALYSIS_END,
    DAYS_PER_YEAR,
    PRIMARY_HOLDING,
    format_calendar,
    format_robustness,
)

SEC_FILES = "*_form345.zip"
TRADE_COLUMNS = [
    "ACCESSION_NUMBER",
    "SECURITY_TITLE",
    "TRANS_DATE",
    "TRANS_CODE",
    "EQUITY_SWAP_INVOLVED",
    "TRANS_SHARES",
    "TRANS_PRICEPERSHARE",
    "TRANS_ACQUIRED_DISP_CD",
]
FILING_COLUMNS = [
    "ACCESSION_NUMBER",
    "FILING_DATE",
    "DOCUMENT_TYPE",
    "ISSUERCIK",
    "ISSUERTRADINGSYMBOL",
]
OWNER_COLUMNS = ["ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNER_RELATIONSHIP"]
SEC_DATE = "%d-%b-%Y"
TICKER = r"[A-Z]{1,5}"
ROLES = r"\b(?:Director|Officer)\b"
SWAP_YES = {"1", "true"}
MAX_LAG_DAYS = 365
PRICE_FLOOR = 5.0
EVENT_KEY = ["issuer", "owner", "ticker", "transaction_date"]


def read_table(archive: zipfile.ZipFile, name: str, columns: list[str]) -> pd.DataFrame:
    return pd.read_csv(
        archive.open(name),
        sep="\t",
        dtype=str,
        usecols=columns,
        keep_default_na=False,
        quoting=csv.QUOTE_NONE,
    )


def read_form4(sec_dir: Path) -> pd.DataFrame:
    """One row per purchase line (code P) and reporting owner across the quarterly files."""
    paths = sorted(sec_dir.glob(SEC_FILES))
    if not paths:
        raise FileNotFoundError(f"no {SEC_FILES} files in {sec_dir}")
    frames = []
    for path in paths:
        with zipfile.ZipFile(path) as archive:
            trades = read_table(archive, "NONDERIV_TRANS.tsv", TRADE_COLUMNS)
            filings = read_table(archive, "SUBMISSION.tsv", FILING_COLUMNS)
            owners = read_table(archive, "REPORTINGOWNER.tsv", OWNER_COLUMNS)
        purchases = trades[trades["TRANS_CODE"] == "P"]
        merged = purchases.merge(filings, on="ACCESSION_NUMBER")
        frames.append(merged.merge(owners, on="ACCESSION_NUMBER"))
    return pd.concat(frames, ignore_index=True)


def build_insider_events(raw: pd.DataFrame) -> tuple[pd.DataFrame, Flow]:
    """Apply the sample rules in docs/specs/insider-control.md and count the rows left."""
    df = raw.assign(
        transaction_date=pd.to_datetime(raw["TRANS_DATE"], format=SEC_DATE, errors="coerce"),
        disclosure_date=pd.to_datetime(raw["FILING_DATE"], format=SEC_DATE, errors="coerce"),
        shares=pd.to_numeric(raw["TRANS_SHARES"], errors="coerce"),
        price=pd.to_numeric(raw["TRANS_PRICEPERSHARE"], errors="coerce"),
    )
    flow: Flow = [("purchase lines (code P), one per reporting owner", len(df))]

    def keep(mask: pd.Series, label: str) -> None:
        nonlocal df
        df = df[mask]
        flow.append((label, len(df)))

    keep(df["DOCUMENT_TYPE"] == "4", "Form 4 as originally filed")
    keep(df["TRANS_ACQUIRED_DISP_CD"] == "A", "acquired")
    keep(df["SECURITY_TITLE"].str.contains("common", case=False), "common stock")
    keep(~df["EQUITY_SWAP_INVOLVED"].str.lower().isin(SWAP_YES), "no equity swap")
    keep((df["shares"] > 0) & (df["price"] > 0), "positive shares and price")
    keep(df["RPTOWNER_RELATIONSHIP"].str.contains(ROLES, regex=True), "officer or director")
    keep(df["ISSUERTRADINGSYMBOL"].str.fullmatch(TICKER), "valid ticker")
    keep(df["transaction_date"].between(START, END), "transaction date 2020-01-01 to 2025-12-31")
    df = df.rename(
        columns={"ISSUERTRADINGSYMBOL": "ticker", "ISSUERCIK": "issuer", "RPTOWNERCIK": "owner"}
    )
    keep(~df.duplicated(EVENT_KEY), "after removing duplicates")
    lag = (df["disclosure_date"] - df["transaction_date"]).dt.days
    flow += [
        ("  disclosed before the trade", int((lag < 0).sum())),
        (f"  disclosed more than {MAX_LAG_DAYS} days later", int((lag > MAX_LAG_DAYS).sum())),
    ]
    keep(lag.between(0, MAX_LAG_DAYS), "filing lag 0 to 365 days")
    columns = ["ticker", "issuer", "owner", "transaction_date", "disclosure_date", "price"]
    return df[columns].reset_index(drop=True), flow


def fetch(sec_dir: Path, user: str, out_dir: Path) -> None:
    """Build the events, match them to CRSP and save events, returns and exclusions."""
    events, flow = build_insider_events(read_form4(sec_dir))
    conn = crsp.connect(user)
    tickers = sorted(events["ticker"].unique())
    links = crsp.query(conn, crsp.LINKS_SQL, (tickers, START.date(), END.date()))
    linked, link_flow, excluded = crsp.link_events(events, links)
    first = linked["transaction_date"].min() - crsp.ESTIMATION_BUFFER
    permnos = sorted(int(p) for p in linked["security"].unique())
    returns = crsp.query(conn, crsp.RETURNS_SQL, (permnos, first.date(), crsp.RETURNS_END.date()))
    conn.close()

    out_dir.mkdir(parents=True, exist_ok=True)
    linked.to_csv(out_dir / "events.csv", index_label="event_id", date_format="%Y-%m-%d")
    returns.to_csv(out_dir / "returns.csv.gz", index=False)
    excluded.to_csv(out_dir / "excluded.csv", index_label="event_id")
    print(format_flow(flow + link_flow))
    print(f"\n{len(returns):,} daily returns for {len(permnos):,} stocks -> {out_dir}")


def load_inputs(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    events = pd.read_csv(
        data_dir / "events.csv",
        index_col="event_id",
        parse_dates=["transaction_date", "disclosure_date"],
    )
    returns = crsp.wide_returns(pd.read_csv(data_dir / "returns.csv.gz"))
    return events, returns.loc[:ANALYSIS_END]


def control_table(
    returns: pd.DataFrame, factors: pd.DataFrame, events: pd.DataFrame
) -> pd.DataFrame:
    """C1: four-factor alpha of the insider copy portfolio from the filing date."""
    rows = []
    for holding in HORIZONS:
        result = calendar_time_alpha(returns, factors, events, "disclosure_date", holding)
        rows.append(
            {
                "holding_days": holding,
                "primary": holding == PRIMARY_HOLDING,
                "alpha_annual": result["alpha_daily"] * DAYS_PER_YEAR,
                **result,
            }
        )
    return pd.DataFrame(rows)


def robustness_table(
    returns: pd.DataFrame, factors: pd.DataFrame, events: pd.DataFrame
) -> pd.DataFrame:
    """The plan's two checks on the primary test (62-day copy portfolio)."""
    checks = [
        ("Primary: all purchases", events),
        ("Leave out trades made in 2020", events[events["transaction_date"].dt.year != 2020]),
        (f"Price of ${PRICE_FLOOR:.0f} a share or more", events[events["price"] >= PRICE_FLOOR]),
    ]
    rows = []
    for label, sample in checks:
        result = calendar_time_alpha(returns, factors, sample, "disclosure_date", PRIMARY_HOLDING)
        rows.append(
            {
                "check": label,
                "events": len(sample),
                "alpha_annual": result["alpha_daily"] * DAYS_PER_YEAR,
                **result,
            }
        )
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the insider-purchase positive control.")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--sec-dir", type=Path)
    parser.add_argument("--user")
    args = parser.parse_args(argv)
    if args.sec_dir:
        if not args.user:
            parser.error("--user is required with --sec-dir")
        fetch(args.sec_dir, args.user, args.data_dir)

    events, returns = load_inputs(args.data_dir)
    factors = download_factors(args.data_dir / "french_daily.csv")
    print(f"{len(events):,} purchases, {returns.shape[1]:,} stocks, ", end="")
    print(f"returns {returns.index.min():%Y-%m-%d} to {returns.index.max():%Y-%m-%d}")
    print("\nC1: insider copy portfolio from the filing date (four-factor alpha)\n")
    print(format_calendar(control_table(returns, factors, events)))
    print("\nRobustness: 62-day copy portfolio, four-factor alpha\n")
    print(format_robustness(robustness_table(returns, factors, events)))


if __name__ == "__main__":
    main()
