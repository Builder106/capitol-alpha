"""Fetch CRSP daily returns from WRDS for the purchase events.

Usage, with WRDS credentials in ~/.pgpass:
    uv run --with "psycopg[binary]" python -m pipeline.crsp --user NAME --out-dir DIR

Writes events.csv (with a CRSP permno per event) and returns.csv.gz to DIR.
CRSP data is licensed through WRDS: keep DIR outside the repository.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

import pandas as pd

from .event_sample import END, SNAPSHOT, START, Flow, build_events, format_flow, load_snapshot

WRDS = {
    "host": "wrds-pgdata.wharton.upenn.edu",
    "port": 9737,
    "dbname": "wrds",
    "sslmode": "require",
}
LINKS_SQL = """
SELECT ticker, permno, secinfostartdt, secinfoenddt, sharetype
FROM crsp.stksecurityinfohist
WHERE ticker = ANY(%s)
  AND securitytype = 'EQTY' AND securitysubtype = 'COM'
  AND secinfoenddt >= %s AND secinfostartdt <= %s
"""
RETURNS_SQL = """
SELECT permno, dlycaldt, dlyret
FROM crsp.dsf_v2
WHERE permno = ANY(%s) AND dlycaldt BETWEEN %s AND %s
"""
COMMON_SHARE = "NS"
ADR_SHARE = "AD"
ESTIMATION_BUFFER = pd.Timedelta(days=400)
RETURNS_END = pd.Timestamp("2026-12-31")


class Cursor(Protocol):
    description: Sequence[tuple]

    def execute(self, query: str, params: tuple) -> object: ...

    def fetchall(self) -> list[tuple]: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...

    def close(self) -> None: ...


def connect(user: str) -> Connection:
    import psycopg

    return psycopg.connect(user=user, connect_timeout=120, **WRDS)


def query(conn: Connection, sql: str, params: tuple) -> pd.DataFrame:
    cursor = conn.cursor()
    cursor.execute(sql, params)
    columns = [column[0] for column in cursor.description]
    return pd.DataFrame(cursor.fetchall(), columns=columns)


def link_events(events: pd.DataFrame, links: pd.DataFrame) -> tuple[pd.DataFrame, Flow]:
    """Attach the permno whose record covers each transaction date.

    Returns common-stock events with a ``security`` column, and the counts.
    """
    links = links.assign(
        secinfostartdt=pd.to_datetime(links["secinfostartdt"]),
        secinfoenddt=pd.to_datetime(links["secinfoenddt"]),
    )
    merged = events.reset_index(names="event_id").merge(links, on="ticker", how="left")
    covered = merged["transaction_date"].between(merged["secinfostartdt"], merged["secinfoenddt"])
    matched = (
        merged[covered]
        .sort_values(["event_id", "sharetype"], ascending=[True, False])
        .drop_duplicates("event_id")
    )
    common = matched[matched["sharetype"] == COMMON_SHARE]

    flow: Flow = [
        ("events", len(events)),
        ("  no CRSP common or ADR record on the trade date", len(events) - len(matched)),
        ("  ADR (excluded)", int((matched["sharetype"] == ADR_SHARE).sum())),
        (
            "  other share type (excluded)",
            int((~matched["sharetype"].isin([COMMON_SHARE, ADR_SHARE])).sum()),
        ),
        ("matched to CRSP common stock", len(common)),
    ]
    linked = common.drop(columns=["secinfostartdt", "secinfoenddt", "sharetype"])
    linked = linked.rename(columns={"permno": "security"}).astype({"security": int})
    linked = linked.set_index("event_id")
    linked.index.name = None
    return linked.sort_index(), flow


def wide_returns(long: pd.DataFrame) -> pd.DataFrame:
    """Daily returns with one column per permno."""
    frame = long.assign(
        dlycaldt=pd.to_datetime(long["dlycaldt"]), dlyret=pd.to_numeric(long["dlyret"])
    )
    wide = frame.pivot_table(index="dlycaldt", columns="permno", values="dlyret", aggfunc="first")
    wide.index.name = None
    wide.columns.name = None
    return wide.sort_index()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Fetch CRSP returns for the purchase events.")
    parser.add_argument("--user", default=os.environ.get("WRDS_USER"))
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    args = parser.parse_args(argv)
    if not args.user:
        parser.error("--user or WRDS_USER is required")

    events, sample_flow = build_events(load_snapshot(args.snapshot))
    conn = connect(args.user)
    tickers = sorted(events["ticker"].unique())
    links = query(conn, LINKS_SQL, (tickers, START.date(), END.date()))
    linked, link_flow = link_events(events, links)

    first = linked["transaction_date"].min() - ESTIMATION_BUFFER
    permnos = sorted(int(p) for p in linked["security"].unique())
    returns = query(conn, RETURNS_SQL, (permnos, first.date(), RETURNS_END.date()))
    conn.close()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    linked.to_csv(args.out_dir / "events.csv", index_label="event_id", date_format="%Y-%m-%d")
    returns.to_csv(args.out_dir / "returns.csv.gz", index=False)
    print(format_flow(sample_flow + link_flow))
    print(f"\n{len(returns):,} daily returns for {len(permnos):,} stocks -> {args.out_dir}")


if __name__ == "__main__":
    main()
