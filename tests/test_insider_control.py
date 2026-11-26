"""Tests for the insider-purchase control (pipeline.insider_control).

The SEC archives, returns and factors here are constructed test fixtures (a
fixed seed for the numbers). None of it is SEC or market data.
"""

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pipeline import insider_control as control
from pipeline.event_study import FOUR_FACTOR
from tests.test_crsp import RETURN_ROWS, FakeConnection

TRADE = {
    "SECURITY_TITLE": "Common Stock",
    "TRANS_DATE": "02-MAR-2021",
    "TRANS_CODE": "P",
    "EQUITY_SWAP_INVOLVED": "0",
    "TRANS_SHARES": "100",
    "TRANS_PRICEPERSHARE": "120.5",
    "TRANS_ACQUIRED_DISP_CD": "A",
}
FILING = {
    "FILING_DATE": "16-MAR-2021",
    "DOCUMENT_TYPE": "4",
    "ISSUERCIK": "1",
    "ISSUERTRADINGSYMBOL": "AAPL",
}
OWNER = {"RPTOWNERCIK": "11", "RPTOWNER_RELATIONSHIP": "Director,Officer"}


def tsv(rows: list[dict[str, str]]) -> str:
    columns = list(rows[0])
    lines = ["\t".join(columns)] + ["\t".join(row[c] for c in columns) for row in rows]
    return "\n".join(lines) + "\n"


def write_archive(path: Path, cases: list[tuple[dict, dict, dict]]) -> None:
    """One accession per case: (trade changes, filing changes, owner changes)."""
    trades, filings, owners = [], [], []
    for number, (trade, filing, owner) in enumerate(cases):
        accession = f"0000000000-21-{number:06d}"
        trades.append({"ACCESSION_NUMBER": accession, **TRADE, **trade})
        filings.append({"ACCESSION_NUMBER": accession, **FILING, **filing})
        owners.append({"ACCESSION_NUMBER": accession, **OWNER, **owner})
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("NONDERIV_TRANS.tsv", tsv(trades))
        archive.writestr("SUBMISSION.tsv", tsv(filings))
        archive.writestr("REPORTINGOWNER.tsv", tsv(owners))


FIRST_QUARTER = [
    ({}, {}, {}),
    ({}, {}, {}),
    ({}, {"DOCUMENT_TYPE": "4/A"}, {}),
    ({"TRANS_ACQUIRED_DISP_CD": "D"}, {}, {}),
    ({"SECURITY_TITLE": "Preferred Stock"}, {}, {}),
    ({"EQUITY_SWAP_INVOLVED": "1"}, {}, {}),
    ({"TRANS_SHARES": "0"}, {}, {}),
    ({}, {}, {"RPTOWNER_RELATIONSHIP": "TenPercentOwner"}),
    ({}, {"ISSUERTRADINGSYMBOL": "BRK.B"}, {}),
    ({"TRANS_DATE": "02-JAN-2019"}, {}, {}),
    ({}, {"FILING_DATE": "01-MAR-2021", "ISSUERCIK": "2", "ISSUERTRADINGSYMBOL": "MSFT"}, {}),
    ({}, {"FILING_DATE": "03-MAR-2022", "ISSUERCIK": "3", "ISSUERTRADINGSYMBOL": "TSLA"}, {}),
    ({"TRANS_CODE": "S"}, {}, {}),
]
SECOND_QUARTER = [
    (
        {"TRANS_DATE": "05-MAY-2021", "TRANS_PRICEPERSHARE": "3.2"},
        {"FILING_DATE": "07-MAY-2021"},
        {"RPTOWNERCIK": "22", "RPTOWNER_RELATIONSHIP": "Officer"},
    )
]


@pytest.fixture
def sec_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "sec"
    directory.mkdir()
    write_archive(directory / "2021q1_form345.zip", FIRST_QUARTER)
    write_archive(directory / "2021q2_form345.zip", SECOND_QUARTER)
    return directory


def test_read_form4_keeps_purchase_lines_from_every_quarter(sec_dir):
    raw = control.read_form4(sec_dir)
    assert len(raw) == 13
    assert set(raw["TRANS_CODE"]) == {"P"}


def test_read_form4_needs_files(tmp_path):
    with pytest.raises(FileNotFoundError):
        control.read_form4(tmp_path)


def test_build_insider_events_counts_each_rule(sec_dir):
    events, flow = control.build_insider_events(control.read_form4(sec_dir))
    assert dict(flow) == {
        "purchase lines (code P), one per reporting owner": 13,
        "Form 4 as originally filed": 12,
        "acquired": 11,
        "common stock": 10,
        "no equity swap": 9,
        "positive shares and price": 8,
        "officer or director": 7,
        "valid ticker": 6,
        "transaction date 2020-01-01 to 2025-12-31": 5,
        "after removing duplicates": 4,
        "  disclosed before the trade": 1,
        "  disclosed more than 365 days later": 1,
        "filing lag 0 to 365 days": 2,
    }
    assert list(events["ticker"]) == ["AAPL", "AAPL"]
    assert list(events["disclosure_date"]) == list(pd.to_datetime(["2021-03-16", "2021-05-07"]))
    assert list(events["price"]) == [120.5, 3.2]


def test_fetch_matches_crsp_and_writes_files(sec_dir, tmp_path, monkeypatch, capsys):
    connection = FakeConnection()
    monkeypatch.setattr(control.crsp, "connect", lambda user: connection)

    out = tmp_path / "out"
    control.fetch(sec_dir, "someone", out)

    assert connection.closed
    events = pd.read_csv(out / "events.csv")
    assert list(events["security"]) == [14593, 14593]
    assert len(pd.read_csv(out / "returns.csv.gz")) == len(RETURN_ROWS)
    assert pd.read_csv(out / "excluded.csv").empty
    text = capsys.readouterr().out
    assert "filing lag 0 to 365 days" in text
    assert "matched to CRSP common stock" in text


def constructed_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(17)
    days = pd.bdate_range("2020-01-02", periods=600)
    factors = pd.DataFrame(rng.normal(0, 0.01, (600, 4)), index=days, columns=list(FOUR_FACTOR))
    factors["RF"] = 0.0001
    returns = pd.DataFrame(
        {
            permno: factors["RF"] + 0.0004 + factors["Mkt-RF"] + rng.normal(0, 0.005, 600)
            for permno in (101, 202, 303)
        }
    )
    positions = [60, 300, 320, 380, 440, 480]
    events = pd.DataFrame(
        {
            "security": [101, 202, 303, 101, 202, 303],
            "transaction_date": [days[p] for p in positions],
            "disclosure_date": [days[p + 2] for p in positions],
            "price": [2.0, 8.0, 40.0, 3.0, 12.0, 25.0],
        }
    )
    return returns, factors, events


def test_control_table_marks_primary_holding():
    returns, factors, events = constructed_inputs()
    table = control.control_table(returns, factors, events)
    assert list(table["holding_days"]) == [20, 62, 125]
    assert list(table["primary"]) == [False, True, False]
    assert table["alpha_annual"].notna().all()


def test_robustness_table_applies_both_checks():
    returns, factors, events = constructed_inputs()
    table = control.robustness_table(returns, factors, events)
    assert list(table["events"]) == [6, 5, 4]
    assert table["check"].tolist()[2] == "Price of $5 a share or more"
    assert table["alpha_annual"].notna().all()


def test_main_prints_both_tables(tmp_path, monkeypatch, capsys):
    returns, factors, events = constructed_inputs()
    events.to_csv(tmp_path / "events.csv", index_label="event_id", date_format="%Y-%m-%d")
    long = returns.stack().rename("dlyret").rename_axis(["dlycaldt", "permno"]).reset_index()
    long.to_csv(tmp_path / "returns.csv.gz", index=False)
    monkeypatch.setattr(control, "download_factors", lambda path: factors)

    control.main(["--data-dir", str(tmp_path)])

    out = capsys.readouterr().out
    assert out.startswith("6 purchases, 3 stocks, returns 2020-01-02 to")
    assert "C1: insider copy portfolio" in out
    assert "| 62 | yes |" in out
    assert "| Leave out trades made in 2020 | 5 |" in out


class StopAfterFetch(Exception):
    pass


def test_main_fetches_first_when_given_sec_files(tmp_path, monkeypatch):
    calls = []

    def stop(data_dir):
        raise StopAfterFetch

    monkeypatch.setattr(control, "fetch", lambda *args: calls.append(args))
    monkeypatch.setattr(control, "load_inputs", stop)
    with pytest.raises(StopAfterFetch):
        control.main(["--data-dir", str(tmp_path), "--sec-dir", "sec", "--user", "someone"])
    assert calls == [(Path("sec"), "someone", tmp_path)]


def test_main_requires_user_with_sec_files(tmp_path):
    with pytest.raises(SystemExit):
        control.main(["--data-dir", str(tmp_path), "--sec-dir", "sec"])
