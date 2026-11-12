"""Tests for the purchase event sample (pipeline.event_sample)."""

import hashlib

import pandas as pd
import pytest

from pipeline.event_sample import (
    SNAPSHOT,
    build_events,
    format_flow,
    load_snapshot,
    main,
    normalize_padded_csv,
)

SNAPSHOT_SHA256 = "2073e06f19fb5bd01ccff3455302ce9709e3cbf8b1eb2f733f86a0a17e1276a8"
COLUMNS = [
    "legislator_name",
    "owner",
    "ticker",
    "transaction_date",
    "disclosure_date",
    "asset_description",
    "asset_type",
    "transaction_type",
    "amount_range",
]


def trade(**overrides: str) -> dict[str, str]:
    row = {
        "legislator_name": "A Member",
        "owner": "Sp",
        "ticker": "AAPL",
        "transaction_date": "03/02/2021",
        "disclosure_date": "03/16/2021",
        "asset_description": "Apple Inc.",
        "asset_type": "",
        "transaction_type": "P",
        "amount_range": "$1,001 - $15,000",
    }
    row.update(overrides)
    return row


def test_committed_snapshot_is_unchanged():
    assert hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest() == SNAPSHOT_SHA256


def test_normalize_padded_csv(tmp_path):
    src = tmp_path / "padded.csv"
    src.write_text(
        'chamber ,ticker ,asset_description          \nSenate  ,BYND   , "Beyond Meat, Inc."     \n'
    )
    dst = tmp_path / "out" / "clean.csv"
    assert normalize_padded_csv(src, dst) == 1
    assert dst.read_text().splitlines() == [
        "chamber,ticker,asset_description",
        'Senate,BYND,"Beyond Meat, Inc."',
    ]


def test_normalize_padded_csv_rejects_ragged_rows(tmp_path):
    src = tmp_path / "ragged.csv"
    src.write_text("a,b\n1,2\n3\n")
    with pytest.raises(ValueError, match="1 rows do not have 2 fields, first at line 3"):
        normalize_padded_csv(src, tmp_path / "clean.csv")


def test_build_events_applies_rules_in_order():
    rows = [
        trade(),
        trade(transaction_type="Purchase", ticker="MSFT"),
        trade(transaction_type="S"),
        trade(ticker="BRK.B"),
        trade(asset_type="Stock Option"),
        trade(asset_description="AAPL call options"),
        trade(transaction_date="12/31/2019"),
        trade(),
        trade(ticker="NVDA", disclosure_date=""),
        trade(ticker="AMD", disclosure_date="03/01/2021"),
        trade(ticker="TSLA", disclosure_date="06/01/2022"),
    ]
    events, flow = build_events(pd.DataFrame(rows, columns=COLUMNS))

    assert flow == [
        ("rows in snapshot", 11),
        ("purchases (P or Purchase)", 10),
        ("valid ticker", 9),
        ("stock (no options or other securities)", 7),
        ("transaction date 2020-01-01 to 2025-12-31", 6),
        ("after removing duplicates", 5),
        ("  no disclosure date", 1),
        ("  disclosed before the trade", 1),
        ("  disclosed more than 365 days later", 1),
        ("eligible for Q1 (disclosure lag 0 to 365 days)", 2),
    ]
    assert list(events["ticker"]) == ["AAPL", "MSFT", "NVDA", "AMD", "TSLA"]
    assert list(events["q1_eligible"]) == [True, True, False, False, False]
    assert events.loc[0, "lag_days"] == 14
    assert pd.isna(events.loc[2, "lag_days"])


def test_format_flow_aligns_counts():
    assert format_flow([("rows", 16202), ("kept", 5)]).splitlines() == [
        "rows  16,202",
        "kept       5",
    ]


def test_main_writes_events(tmp_path, capsys):
    snapshot = tmp_path / "snapshot.csv"
    pd.DataFrame([trade()], columns=COLUMNS).to_csv(snapshot, index=False)
    out = tmp_path / "events.csv"

    main(["--snapshot", str(snapshot), "--out", str(out)])

    assert "eligible for Q1" in capsys.readouterr().out
    written = load_snapshot(out)
    assert written.loc[0, "transaction_date"] == "2021-03-02"
    assert written.loc[0, "q1_eligible"] == "True"


def test_build_events_sale_side():
    rows = [trade(transaction_type=code) for code in ("S", "s (partial)", "Sale", "P")]
    rows = [{**row, "ticker": ticker} for row, ticker in zip(rows, ["A", "B", "C", "D"])]
    events, flow = build_events(pd.DataFrame(rows, columns=COLUMNS), side="sale")
    assert flow[1] == ("sales (S, S (partial), or Sale)", 3)
    assert set(events["side"]) == {"sale"}
