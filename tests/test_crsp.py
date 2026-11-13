"""Tests for the CRSP adapter (pipeline.crsp). The database is a fake."""

import sys
import types
from decimal import Decimal

import pandas as pd
import pytest

from pipeline import crsp

LINK_COLUMNS = ["ticker", "permno", "secinfostartdt", "secinfoenddt", "sharetype", "usincflg"]
LINKS = [
    ("AAPL", 14593, "2017-12-28", "2025-12-31", "NS", "Y"),
    ("META", 13407, "2022-06-09", "2025-12-31", "NS", "Y"),
    ("TSM", 85442, "2000-01-01", "2025-12-31", "AD", "N"),
    ("XYZ", 11111, "2000-01-01", "2025-12-31", "UG", "Y"),
    ("AAA", 22222, "2000-01-01", "2025-12-31", "AD", "N"),
    ("AAA", 33333, "2000-01-01", "2025-12-31", "NS", "N"),
    ("AAA", 44444, "2000-01-01", "2025-12-31", "NS", "Y"),
]
RETURN_COLUMNS = ["permno", "dlycaldt", "dlyret", "dlyopen", "dlyclose"]
RETURN_ROWS = [
    (14593, "2021-03-02", Decimal("0.010"), Decimal("100"), Decimal("102")),
    (14593, "2021-03-03", Decimal("-0.005"), Decimal("0"), Decimal("101")),
    (33333, "2021-03-02", Decimal("0.002"), None, Decimal("50")),
]


class FakeCursor:
    def __init__(self) -> None:
        self.description: list[tuple[str]] = []
        self.rows: list[tuple] = []

    def execute(self, sql: str, params: tuple) -> None:
        if "stksecurityinfohist" in sql:
            self.description = [(name,) for name in LINK_COLUMNS]
            self.rows = LINKS
        else:
            self.description = [(name,) for name in RETURN_COLUMNS]
            self.rows = RETURN_ROWS

    def fetchall(self) -> list[tuple]:
        return self.rows


class FakeConnection:
    closed = False

    def cursor(self) -> FakeCursor:
        return FakeCursor()

    def close(self) -> None:
        self.closed = True


def events_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": ["AAPL", "META", "TSM", "XYZ", "AAA", "ZZZ"],
            "transaction_date": pd.to_datetime(["2021-03-02"] * 6),
            "legislator_name": ["A"] * 6,
        }
    )


def test_query_builds_frame():
    frame = crsp.query(FakeConnection(), crsp.LINKS_SQL, ([], None, None))
    assert list(frame.columns) == LINK_COLUMNS
    assert len(frame) == len(LINKS)


def test_link_events_matches_by_date_and_share_type():
    links = pd.DataFrame(LINKS, columns=LINK_COLUMNS)
    linked, flow, excluded = crsp.link_events(events_frame(), links)

    assert list(linked["ticker"]) == ["AAPL", "AAA"]
    assert list(linked["security"]) == [14593, 33333]
    assert list(linked["usincflg"]) == ["Y", "N"]
    assert list(linked.index) == [0, 4]
    assert flow == [
        ("events", 6),
        ("  no CRSP common or ADR record on the trade date", 2),
        ("  ADR (excluded)", 1),
        ("  other share type (excluded)", 1),
        ("matched to CRSP common stock", 2),
        ("  of which had more than one common record (lowest permno kept)", 1),
    ]
    assert excluded.to_dict("index") == {
        1: {"ticker": "META", "reason": crsp.NO_RECORD},
        2: {"ticker": "TSM", "reason": "ADR"},
        3: {"ticker": "XYZ", "reason": "other share type"},
        5: {"ticker": "ZZZ", "reason": crsp.NO_RECORD},
    }


def test_wide_returns_pivots_decimal_returns():
    long = pd.DataFrame(RETURN_ROWS, columns=RETURN_COLUMNS)
    wide = crsp.wide_returns(long)
    assert list(wide.columns) == [14593, 33333]
    assert wide.loc["2021-03-03", 14593] == pytest.approx(-0.005)
    assert pd.isna(wide.loc["2021-03-03", 33333])


def test_wide_open_to_close():
    long = pd.DataFrame(RETURN_ROWS, columns=RETURN_COLUMNS)
    wide = crsp.wide_open_to_close(long)
    assert wide is not None
    wide = wide.reindex(index=pd.to_datetime(["2021-03-02", "2021-03-03"]), columns=[14593, 33333])
    assert wide.loc["2021-03-02", 14593] == pytest.approx(0.02)
    assert pd.isna(wide.loc["2021-03-03", 14593])
    assert pd.isna(wide.loc["2021-03-02", 33333])
    assert crsp.wide_open_to_close(long[["permno", "dlycaldt", "dlyret"]]) is None


def test_link_events_prefers_ordinary_shares_over_other_codes():
    links = pd.DataFrame(
        [
            ("DOC", 55555, "2000-01-01", "2025-12-31", "SB", "Y"),
            ("DOC", 66666, "2000-01-01", "2025-12-31", "NS", "Y"),
        ],
        columns=LINK_COLUMNS,
    )
    events = pd.DataFrame(
        {
            "ticker": ["DOC"],
            "transaction_date": pd.to_datetime(["2021-03-02"]),
            "legislator_name": ["A"],
        }
    )
    linked, flow, excluded = crsp.link_events(events, links)
    assert list(linked["security"]) == [66666]
    assert excluded.empty


def test_connect_uses_wrds_settings(monkeypatch):
    fake = types.ModuleType("psycopg")
    fake.connect = lambda **kwargs: kwargs  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "psycopg", fake)
    settings = crsp.connect("someone")
    assert settings["user"] == "someone"
    assert settings["host"] == "wrds-pgdata.wharton.upenn.edu"
    assert settings["sslmode"] == "require"


def test_main_writes_outputs(tmp_path, monkeypatch, capsys):
    snapshot = tmp_path / "snapshot.csv"
    row = {
        "legislator_name": "A",
        "owner": "Sp",
        "ticker": "AAPL",
        "transaction_date": "03/02/2021",
        "disclosure_date": "03/16/2021",
        "asset_description": "Apple Inc.",
        "asset_type": "",
        "transaction_type": "P",
        "amount_range": "$1,001 - $15,000",
    }
    sale = {**row, "ticker": "ZZZ", "asset_description": "Unknown Fund", "transaction_type": "S"}
    pd.DataFrame([row, sale]).to_csv(snapshot, index=False)
    connection = FakeConnection()
    monkeypatch.setattr(crsp, "connect", lambda user: connection)

    out = tmp_path / "crsp"
    crsp.main(["--user", "someone", "--out-dir", str(out), "--snapshot", str(snapshot)])

    assert connection.closed
    events = pd.read_csv(out / "events.csv")
    assert list(events["security"]) == [14593]
    assert list(events["side"]) == ["purchase"]
    excluded = pd.read_csv(out / "excluded.csv")
    assert excluded.loc[0, ["ticker", "side", "reason"]].tolist() == ["ZZZ", "sale", crsp.NO_RECORD]
    assert len(pd.read_csv(out / "returns.csv.gz")) == len(RETURN_ROWS)
    out_text = capsys.readouterr().out
    assert "[purchase] matched to CRSP common stock" in out_text
    assert "[sale] events" in out_text


def test_main_requires_user(tmp_path, monkeypatch):
    monkeypatch.delenv("WRDS_USER", raising=False)
    with pytest.raises(SystemExit):
        crsp.main(["--out-dir", str(tmp_path)])
