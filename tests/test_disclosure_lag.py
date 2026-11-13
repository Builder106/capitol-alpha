"""Tests for disclosure lag statistics (pipeline.disclosure_lag)."""

import pandas as pd
import pytest

from pipeline.disclosure_lag import (
    disclosure_lags,
    earliest_filing_only,
    late_share_sensitivity,
    main,
    summarize,
    to_markdown,
)

COLUMNS = [
    "chamber",
    "legislator_name",
    "owner",
    "ticker",
    "transaction_date",
    "disclosure_date",
    "transaction_type",
    "amount_range",
    "ptr_link",
]


def trade(name: str, tx: str, disclosed: str, ticker: str = "AAPL", kind: str = "P") -> list[str]:
    chamber = "Senate" if not disclosed else "House"
    link = f"{name}-{disclosed}.pdf"
    return [chamber, name, "Sp", ticker, tx, disclosed, kind, "$1,001 - $15,000", link]


ROWS = [
    trade("A", "01/01/2021", "01/11/2021"),
    trade("A", "02/01/2021", "04/01/2021", ticker="MSFT", kind="S"),
    trade("B", "03/01/2022", "03/31/2022"),
    trade("A", "01/01/2021", "01/11/2021"),
    trade("C", "05/01/2022", ""),
    trade("D", "06/01/2022", "05/01/2022"),
    trade("E", "01/01/2020", "06/01/2021"),
    trade("F", "12/31/2019", "01/10/2020"),
]


@pytest.fixture
def lags() -> pd.DataFrame:
    result, _ = disclosure_lags(pd.DataFrame(ROWS, columns=COLUMNS))
    return result


def test_disclosure_lags_sets_aside_bad_rows():
    lags, set_aside = disclosure_lags(pd.DataFrame(ROWS, columns=COLUMNS))
    assert list(lags["lag_days"]) == [10, 59, 30]
    assert list(lags["late"]) == [False, True, False]
    assert set_aside == {
        "no disclosure date": 1,
        "disclosed before the trade": 1,
        "disclosed more than 365 days later": 1,
    }


def test_summarize_whole_sample(lags):
    row = summarize(lags).loc["All"]
    assert row["trades"] == 3
    assert row["median_days"] == 30
    assert row["p90_days"] == pytest.approx(53.2)
    assert row["late"] == 1
    assert row["late_share"] == pytest.approx(1 / 3)
    assert row["filings"] == 3
    assert row["late_filings"] == 1
    assert row["members"] == 2
    assert row["members_ever_late"] == 1


def test_summarize_by_year_fills_members_never_late(lags):
    lags["year"] = lags["transaction_date"].dt.year
    table = summarize(lags, "year")
    assert list(table.index) == [2021, 2022]
    assert list(table["trades"]) == [2, 1]
    assert list(table["members_ever_late"]) == [1, 0]
    assert list(table["late_filings"]) == [1, 0]


def test_to_markdown(lags):
    lines = to_markdown(summarize(lags), "Sample").splitlines()
    assert lines[0].startswith("| Sample | Trades |")
    assert lines[1] == "| --- |" + " ---: |" * 9
    assert lines[2] == "| All | 3 | 30 | 53.2 | 1 | 33.3% | 3 | 1 | 2 | 1 |"


def test_main_prints_tables(tmp_path, capsys):
    snapshot = tmp_path / "snapshot.csv"
    pd.DataFrame(ROWS, columns=COLUMNS).to_csv(snapshot, index=False)
    main(["--snapshot", str(snapshot)])
    out = capsys.readouterr().out
    assert out.startswith("Set aside: no disclosure date 1, disclosed before the trade 1")
    assert "| Chamber | Trades |" in out
    assert "| 2022 | 1 | 30 |" in out
    assert (
        "Share past 45 days: 33.33%; counting trades disclosed more than a year later: 50.00%"
        in out
    )


def test_earliest_filing_only_keeps_same_filing_repeats():
    frame = pd.DataFrame(ROWS, columns=COLUMNS)
    amended = trade("A", "01/01/2021", "03/01/2021")
    blank_owner = trade("G", "02/01/2021", "02/05/2021")
    blank_owner[2] = None
    frame = pd.concat(
        [frame, pd.DataFrame([amended, blank_owner, blank_owner], columns=COLUMNS)],
        ignore_index=True,
    )
    kept = earliest_filing_only(frame)
    a_rows = kept[(kept["legislator_name"] == "A") & (kept["ticker"] == "AAPL")]
    assert list(a_rows["disclosure_date"]) == ["01/11/2021", "01/11/2021"]
    assert int((kept["legislator_name"] == "G").sum()) == 2


def test_late_share_sensitivity():
    shares = late_share_sensitivity(pd.DataFrame(ROWS, columns=COLUMNS))
    assert shares["main"] == pytest.approx(1 / 3)
    assert shares["with_over_a_year"] == pytest.approx(2 / 4)
    assert shares["earliest_filing_trades"] == 4
    assert shares["earliest_filing_dedupe"] == pytest.approx(1 / 4)
