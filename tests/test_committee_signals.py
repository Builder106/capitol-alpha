from datetime import date
from math import sqrt
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from pipeline.committee_signals import (
    ASSIGNMENT_COLUMNS,
    OUTPUT_COLUMNS,
    TRADE_COLUMNS,
    generate_committee_signals,
    main,
)

AS_OF = date(2024, 4, 30)


@pytest.fixture
def inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    trades = pd.DataFrame(
        [
            ["House", "Alice", "2024-04-01", "2024-04-10", "AAA", "Purchase"],
            ["House", "Alice", "2024-04-02", "2024-04-10", "AAA", "Purchase"],
            ["House", "Alice", "2024-04-03", "2024-04-10", "AAA", "Sale"],
            ["House", "Alice", "2024-04-04", "2024-04-10", "BBB", "Purchase"],
            ["House", "Bob", "2024-04-01", "2024-04-10", "AAA", "Sale"],
            ["House", "Bob", "2024-04-02", "2024-04-10", "BBB", "Purchase"],
            ["House", "Bob", "2024-04-03", "2024-04-10", "BBB", "Sale"],
            ["House", "Bob", "2024-04-04", "2024-04-10", "BBB", "Sale"],
            ["Senate", "Alice", "2024-04-01", "2024-04-10", "AAA", "Sale"],
        ],
        columns=TRADE_COLUMNS,
    )
    assignments = pd.DataFrame(
        [["House", "Alice", "Science", "2024-04-01", "2024-04-30"]],
        columns=ASSIGNMENT_COLUMNS,
    )
    sectors = pd.DataFrame({"ticker": ["AAA", "BBB"], "sector": ["Technology", "Energy"]})
    jurisdictions = pd.DataFrame(
        {"chamber": ["House"], "committee": ["Science"], "sector": ["Technology"]}
    )
    return trades, assignments, sectors, jurisdictions


def test_correlation_and_signal(inputs) -> None:
    originals = tuple(frame.copy(deep=True) for frame in inputs)
    result = generate_committee_signals(*inputs, as_of=AS_OF, lookback_days=30)
    assert tuple(result.columns) == OUTPUT_COLUMNS
    row = result.iloc[0]
    assert row["as_of"] == "2024-04-30"
    assert row["window_start"] == "2024-04-01"
    assert row["eligible_trades"] == 8  # Senate namesakes are a separate cohort.
    assert row["member_sector_trades"] == 3
    assert row["member_other_trades"] == 1
    assert row["nonmember_sector_trades"] == 1
    assert row["nonmember_other_trades"] == 3
    assert row["phi"] == pytest.approx((3 * 3 - 1 * 1) / sqrt(4 * 4 * 4 * 4))
    assert row["purchases"] == 2
    assert row["sales"] == 1
    assert row["net_purchase_ratio"] == pytest.approx(1 / 3)
    assert row["signal"] == "buy"
    assert row["min_trades"] == 3
    for original, frame in zip(originals, inputs, strict=True):
        assert_frame_equal(frame, original)


@pytest.mark.parametrize(
    ("directions", "minimum", "expected"),
    [
        (["Sale", "Sale", "Purchase"], 3, "sell"),
        (["Sale", "Purchase", "Exchange"], 2, "neutral"),
        (["Purchase", "Purchase", "Purchase"], 4, "insufficient_data"),
    ],
)
def test_signal_directions(inputs, directions, minimum, expected) -> None:
    inputs[0].loc[:2, "transaction_type"] = directions
    row = generate_committee_signals(*inputs, as_of=AS_OF, min_trades=minimum).iloc[0]
    assert row["signal"] == expected


def test_negative_association(inputs) -> None:
    inputs[1].loc[0, "legislator_name"] = "Bob"
    row = generate_committee_signals(*inputs, as_of=AS_OF, min_trades=1).iloc[0]
    assert row["phi"] == pytest.approx(-0.5)
    assert row["net_purchase_ratio"] == -1
    assert row["signal"] == "sell"


def test_distinct_canonical_records_survive_deduplication(inputs) -> None:
    trades, assignments, sectors, jurisdictions = inputs
    trades["owner"] = "Self"
    trades["amount_avg"] = 1000
    spouse_trade = trades.iloc[[0]].assign(owner="Spouse", amount_avg=1000000)
    row = generate_committee_signals(
        pd.concat([trades, spouse_trade, spouse_trade]),
        assignments,
        sectors,
        jurisdictions,
        as_of=AS_OF,
    ).iloc[0]
    assert row["eligible_trades"] == 9
    assert row["member_sector_trades"] == 4
    assert row["purchases"] == 3
    assert row["net_purchase_ratio"] == 0.5  # Equal trade weights despite amount disparity.


def test_membership_dates_normalization_and_duplicate_references(inputs) -> None:
    trades, assignments, sectors, jurisdictions = inputs
    trades.loc[0, "legislator_name"] = "  ALICE  "
    trades.loc[0, "ticker"] = " aaa "
    trades.loc[0, "transaction_type"] = " purchase "
    assignments.loc[0, "legislator_name"] = "alice"
    assignments.loc[0, "chamber"] = " HOUSE "
    assignments.loc[0, "end_date"] = "2024-04-02"
    inputs_with_duplicates = (
        pd.concat([trades, trades.iloc[[1]]]),
        pd.concat([assignments, assignments, assignments.assign(start_date="2024-04-02")]),
        pd.concat([sectors, sectors]),
        pd.concat([jurisdictions, jurisdictions]),
    )
    row = generate_committee_signals(*inputs_with_duplicates, as_of=AS_OF, min_trades=2).iloc[0]
    assert row["eligible_trades"] == 8
    assert row["member_sector_trades"] == 2  # Both interval endpoints are inclusive.
    assert row["sales"] == 0
    assert row["nonmember_sector_trades"] == 2  # April 3 sale is after departure.
    assert row["signal"] == "buy"


def test_future_assignment_and_late_disclosure(inputs) -> None:
    trades, assignments, sectors, jurisdictions = inputs
    assignments.loc[0, "start_date"] = "2024-04-03"
    assignments.loc[0, "end_date"] = None
    # Later disclosure cannot make an earlier transaction fall within membership.
    row = generate_committee_signals(*inputs, as_of=AS_OF, min_trades=1).iloc[0]
    assert row["member_sector_trades"] == 1
    assert row["sales"] == 1
    assert row["signal"] == "sell"
    assignments.loc[0, "start_date"] = "2025-01-01"
    row = generate_committee_signals(*inputs, as_of=AS_OF).iloc[0]
    assert row["member_sector_trades"] == 0
    assert pd.isna(row["phi"])
    assert pd.isna(row["net_purchase_ratio"])
    assert row["signal"] == "insufficient_data"


def test_eligibility_and_disclosure_window(inputs) -> None:
    trades, assignments, sectors, jurisdictions = inputs
    template = trades.iloc[0].to_dict()
    changes = [
        {"disclosure_date": "2024-05-01"},
        {"disclosure_date": "2024-03-31", "transaction_date": "2024-03-01"},
        {"disclosure_date": None},
        {"disclosure_date": "bad"},
        {"transaction_date": None},
        {"transaction_date": "bad"},
        {"transaction_date": "2024-05-01"},
        {"transaction_type": "Exchange"},
        {"ticker": "UNKNOWN"},
        {"ticker": None},
        {"legislator_name": "  "},
        {"chamber": "Other"},
    ]
    invalid = pd.DataFrame([template | change for change in changes])
    # First and last disclosure days count; an older transaction disclosed now counts.
    boundary = pd.DataFrame(
        [
            template | {"disclosure_date": "2024-04-01"},
            template | {"disclosure_date": "2024-04-30"},
            template | {"transaction_date": "2024-03-01"},
        ]
    )
    row = generate_committee_signals(
        pd.concat([trades, invalid, boundary]),
        assignments,
        sectors,
        jurisdictions,
        as_of=AS_OF,
        lookback_days=30,
    ).iloc[0]
    assert row["eligible_trades"] == 11
    assert row["member_sector_trades"] == 5
    assert row["nonmember_sector_trades"] == 2


def test_multiple_committees_and_sectors_are_separate(inputs) -> None:
    trades, assignments, sectors, jurisdictions = inputs
    assignments = pd.concat([assignments, assignments.assign(committee="Resources")])
    jurisdictions = pd.concat(
        [
            jurisdictions,
            jurisdictions.assign(sector="Energy"),
            jurisdictions.assign(committee="Resources", sector="Energy"),
            jurisdictions.assign(chamber="Senate"),
        ]
    )
    result = generate_committee_signals(
        trades, assignments, sectors, jurisdictions, as_of=AS_OF, min_trades=1
    )
    assert list(zip(result["chamber"], result["committee"], result["sector"])) == [
        ("house", "resources", "energy"),
        ("house", "science", "energy"),
        ("house", "science", "technology"),
        ("senate", "science", "technology"),
    ]
    assert result["member_sector_trades"].tolist() == [1, 1, 3, 0]
    assert result["signal"].tolist() == ["buy", "buy", "buy", "insufficient_data"]


@pytest.mark.parametrize("empty_index", [0, 1, 2, 3])
def test_empty_inputs_have_stable_outputs(inputs, empty_index) -> None:
    frames = list(inputs)
    frames[empty_index] = frames[empty_index].iloc[:0]
    result = generate_committee_signals(*frames, as_of=AS_OF)
    assert tuple(result.columns) == OUTPUT_COLUMNS
    if empty_index == 3:
        assert result.empty
    else:
        assert result.iloc[0]["signal"] == "insufficient_data"
        assert pd.isna(result.iloc[0]["phi"])


@pytest.mark.parametrize("end_date", [None, "", "   "])
def test_open_membership_end(inputs, end_date) -> None:
    inputs[1].loc[0, "end_date"] = end_date
    assert generate_committee_signals(*inputs, as_of=AS_OF).iloc[0]["member_sector_trades"] == 3


@pytest.mark.parametrize(
    ("index", "column", "value", "message"),
    [
        (1, "legislator_name", " ", "reference keys"),
        (2, "sector", None, "reference keys"),
        (3, "committee", None, "reference keys"),
        (1, "chamber", "Other", "chamber"),
        (3, "chamber", "Other", "chamber"),
        (1, "start_date", "bad", "invalid dates"),
        (1, "start_date", None, "invalid dates"),
        (1, "end_date", "bad", "invalid dates"),
        (1, "end_date", "2024-03-31", "reversed membership"),
    ],
)
def test_invalid_references_fail(inputs, index, column, value, message) -> None:
    inputs[index].loc[0, column] = value
    with pytest.raises(ValueError, match=message):
        generate_committee_signals(*inputs, as_of=AS_OF)


def test_ambiguous_sector_mapping_fails(inputs) -> None:
    frames = list(inputs)
    frames[2] = pd.concat([frames[2], frames[2].iloc[[0]].assign(sector="Other")])
    with pytest.raises(ValueError, match="each ticker must map to one sector"):
        generate_committee_signals(*frames, as_of=AS_OF)


@pytest.mark.parametrize("index", range(4))
def test_missing_columns_fail(inputs, index) -> None:
    frames = list(inputs)
    frames[index] = frames[index].drop(columns=frames[index].columns[0])
    with pytest.raises(ValueError, match="missing columns"):
        generate_committee_signals(*frames, as_of=AS_OF)


@pytest.mark.parametrize("options", [{"lookback_days": 0}, {"min_trades": -1}])
def test_invalid_parameters(inputs, options) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        generate_committee_signals(*inputs, as_of=AS_OF, **options)


def test_cli_publishes_and_preserves_output_on_invalid_input(inputs, tmp_path: Path) -> None:
    argv: list[str] = []
    for option, frame in zip(
        ["trades", "assignments", "ticker-sectors", "committee-sectors"], inputs, strict=True
    ):
        path = tmp_path / f"{option}.csv"
        frame.to_csv(path, index=False)
        argv.extend([f"--{option}", str(path)])
    output = tmp_path / "signals.csv"
    argv.extend(
        [
            "--as-of",
            "2024-04-30",
            "--lookback-days",
            "30",
            "--min-trades",
            "3",
            "--output",
            str(output),
        ]
    )
    main(argv)
    expected = generate_committee_signals(*inputs, as_of=AS_OF, lookback_days=30)
    assert_frame_equal(pd.read_csv(output), expected)
    previous = output.read_bytes()
    inputs[1].loc[0, "start_date"] = "bad"
    inputs[1].to_csv(tmp_path / "assignments.csv", index=False)
    with pytest.raises(ValueError, match="invalid dates"):
        main(argv)
    assert output.read_bytes() == previous
    argv[-1] = str(tmp_path / "trades.csv")
    with pytest.raises(ValueError, match="must not overwrite"):
        main(argv)
