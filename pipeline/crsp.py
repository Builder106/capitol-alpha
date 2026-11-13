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

from .event_sample import (
    END,
    SIDES,
    SNAPSHOT,
    START,
    Flow,
    build_events,
    format_flow,
    load_snapshot,
)

WRDS = {
    "host": "wrds-pgdata.wharton.upenn.edu",
    "port": 9737,
    "dbname": "wrds",
    "sslmode": "require",
}
LINKS_SQL = """
SELECT ticker, permno, secinfostartdt, secinfoenddt, sharetype, usincflg
FROM crsp.stksecurityinfohist
WHERE ticker = ANY(%s)
  AND securitytype = 'EQTY' AND securitysubtype = 'COM'
  AND secinfoenddt >= %s AND secinfostartdt <= %s
"""
RETURNS_SQL = """
SELECT permno, dlycaldt, dlyret, dlyopen, dlyclose
FROM crsp.dsf_v2
WHERE permno = ANY(%s) AND dlycaldt BETWEEN %s AND %s
"""
COMMON_SHARE = "NS"
ADR_SHARE = "AD"
# Prefer ordinary shares, then ADRs, then anything else, whatever the codes' sort order.
SHARE_PRIORITY = {COMMON_SHARE: 0, ADR_SHARE: 1}
ESTIMATION_BUFFER = pd.Timedelta(days=400)
NO_RECORD = "no CRSP common or ADR record on the trade date"
OTHER_SHARE = "other share type"
COMMON_REASON = "common"
SHARE_REASONS = {COMMON_SHARE: COMMON_REASON, ADR_SHARE: "ADR"}
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


def link_events(
    events: pd.DataFrame, links: pd.DataFrame
) -> tuple[pd.DataFrame, Flow, pd.DataFrame]:
    """Attach the permno whose record covers each transaction date.

    Returns common-stock events with a ``security`` column, the counts, and
    the excluded events with the reason for each.
    """
    links = links.assign(
        secinfostartdt=pd.to_datetime(links["secinfostartdt"]),
        secinfoenddt=pd.to_datetime(links["secinfoenddt"]),
    )
    merged = events.reset_index(names="event_id").merge(links, on="ticker", how="left")
    covered = merged["transaction_date"].between(merged["secinfostartdt"], merged["secinfoenddt"])
    candidates = (
        merged[covered]
        .assign(_priority=lambda frame: frame["sharetype"].map(SHARE_PRIORITY).fillna(2))
        .sort_values(["event_id", "_priority", "permno"], kind="stable")
        .drop(columns="_priority")
    )
    matched = candidates.drop_duplicates("event_id")
    common_candidates = candidates[candidates["sharetype"] == COMMON_SHARE]
    ambiguous = int(common_candidates["event_id"].duplicated().sum())
    common = matched[matched["sharetype"] == COMMON_SHARE]

    flow: Flow = [
        ("events", len(events)),
        (f"  {NO_RECORD}", len(events) - len(matched)),
        ("  ADR (excluded)", int((matched["sharetype"] == ADR_SHARE).sum())),
        (
            "  other share type (excluded)",
            int((~matched["sharetype"].isin([COMMON_SHARE, ADR_SHARE])).sum()),
        ),
        ("matched to CRSP common stock", len(common)),
        ("  of which had more than one common record (lowest permno kept)", ambiguous),
    ]
    linked = common.drop(columns=["secinfostartdt", "secinfoenddt", "sharetype"])
    linked = linked.rename(columns={"permno": "security"}).astype({"security": int})
    linked = linked.set_index("event_id")
    linked.index.name = None

    share = matched.set_index("event_id")["sharetype"]
    reason = pd.Series(NO_RECORD, index=events.index)
    reason[share.index] = share.map(lambda s: SHARE_REASONS.get(s, OTHER_SHARE))
    labelled = events[["ticker"]].assign(reason=reason)
    excluded = labelled[labelled["reason"] != COMMON_REASON]
    return linked.sort_index(), flow, excluded


def wide_returns(long: pd.DataFrame) -> pd.DataFrame:
    """Daily returns with one column per permno."""
    frame = long.assign(
        dlycaldt=pd.to_datetime(long["dlycaldt"]), dlyret=pd.to_numeric(long["dlyret"])
    )
    wide = frame.pivot_table(index="dlycaldt", columns="permno", values="dlyret", aggfunc="first")
    wide.index.name = None
    wide.columns.name = None
    return wide.sort_index()


def wide_open_to_close(long: pd.DataFrame) -> pd.DataFrame | None:
    """Open-to-close returns (``dlyclose / dlyopen - 1``), one column per permno.

    This is what a copier who buys at the open earns on the day they buy.
    Returns None for an extract fetched before opening prices were added.
    """
    if not {"dlyopen", "dlyclose"} <= set(long.columns):
        return None
    opened = pd.to_numeric(long["dlyopen"])
    ratio = pd.to_numeric(long["dlyclose"]) / opened.where(opened > 0)
    return wide_returns(long.assign(dlyret=ratio - 1)[["permno", "dlycaldt", "dlyret"]])


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Fetch CRSP returns for purchase and sale events.")
    parser.add_argument("--user", default=os.environ.get("WRDS_USER"))
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    args = parser.parse_args(argv)
    if not args.user:
        parser.error("--user or WRDS_USER is required")

    snapshot = load_snapshot(args.snapshot)
    built = [build_events(snapshot, side) for side in SIDES]
    events = pd.concat([frame for frame, _ in built], ignore_index=True)
    conn = connect(args.user)
    tickers = sorted(events["ticker"].unique())
    links = query(conn, LINKS_SQL, (tickers, START.date(), END.date()))

    flows: Flow = []
    linked_parts, excluded_parts = [], []
    for (_, sample_flow), side in zip(built, SIDES, strict=True):
        linked_side, link_flow, excluded_side = link_events(events[events["side"] == side], links)
        flows += [(f"[{side}] {label}", count) for label, count in sample_flow + link_flow]
        linked_parts.append(linked_side)
        excluded_parts.append(excluded_side)
    linked = pd.concat(linked_parts).sort_index()
    excluded = pd.concat(excluded_parts).join(events[["side", "asset_description"]])

    first = linked["transaction_date"].min() - ESTIMATION_BUFFER
    permnos = sorted(int(p) for p in linked["security"].unique())
    returns = query(conn, RETURNS_SQL, (permnos, first.date(), RETURNS_END.date()))
    conn.close()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    linked.to_csv(args.out_dir / "events.csv", index_label="event_id", date_format="%Y-%m-%d")
    returns.to_csv(args.out_dir / "returns.csv.gz", index=False)
    excluded.to_csv(args.out_dir / "excluded.csv", index_label="event_id")
    print(format_flow(flows))
    print(f"\n{len(returns):,} daily returns for {len(permnos):,} stocks -> {args.out_dir}")


if __name__ == "__main__":
    main()
