"""Tests for the event study runner (pipeline.run_event_study).

All returns and factors are constructed test fixtures with a fixed seed. None
of it is market data.
"""

import numpy as np
import pandas as pd

from pipeline import run_event_study as runner
from pipeline.event_study import FOUR_FACTOR

N_DAYS = 600


def constructed_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(11)
    days = pd.bdate_range("2020-01-02", periods=N_DAYS)
    factors = pd.DataFrame(rng.normal(0, 0.01, (N_DAYS, 4)), index=days, columns=list(FOUR_FACTOR))
    factors["RF"] = 0.0001
    returns = pd.DataFrame(
        {
            permno: factors["RF"] + 0.0003 + factors["Mkt-RF"] + rng.normal(0, 0.005, N_DAYS)
            for permno in (101, 202, 303)
        }
    )
    positions = [300, 320, 340, 360, 380, 400, 310, 330]
    events = pd.DataFrame(
        {
            "security": [101, 202, 303, 101, 202, 303, 101, 202],
            "legislator_name": ["A", "B", "C", "A", "B", "C", "A", "B"],
            "transaction_date": [days[p] for p in positions],
            "disclosure_date": [days[p + 10] for p in positions],
            "q1_eligible": [True, True, True, True, True, False, True, True],
            "side": ["purchase"] * 6 + ["sale"] * 2,
            "chamber": ["House", "House", "Senate", "House", "House", "Senate", "House", "House"],
            "owner": ["", "Sp", "Self", "", "Jt", "", "", ""],
            "amount_range": ["$1,001 - $15,000"] * 4 + ["Over $50,000,000", "", "", ""],
        }
    )
    return returns, factors, events


def purchases_only(events: pd.DataFrame) -> pd.DataFrame:
    return events[events["side"] == "purchase"]


def test_calendar_time_table_marks_primary_holding():
    returns, factors, events = constructed_inputs()
    table = runner.calendar_time_table(returns, factors, purchases_only(events))
    assert list(table["holding_days"]) == [20, 62, 125]
    assert list(table["primary"]) == [False, True, False]
    assert (table["alpha_annual"] == table["alpha_daily"] * 252).all()
    assert "| 62 | yes |" in runner.format_calendar(table)


def test_car_table_adjusts_six_tests():
    returns, factors, events = constructed_inputs()
    table = runner.car_table(returns, factors, purchases_only(events))
    assert list(table["event_date"]) == ["disclosure"] * 3 + ["transaction"] * 3
    assert list(table["events"]) == [5, 5, 5, 6, 6, 6]
    assert (table["p_holm"] >= table["p"]).all()
    assert runner.format_cars(table).splitlines()[2].startswith("| disclosure | 20 | 5 |")


def test_main_reads_fetched_files(tmp_path, monkeypatch, capsys):
    returns, factors, events = constructed_inputs()
    events.to_csv(tmp_path / "events.csv", index_label="event_id", date_format="%Y-%m-%d")
    long = returns.stack().rename("dlyret").rename_axis(["dlycaldt", "permno"]).reset_index()
    long.to_csv(tmp_path / "returns.csv.gz", index=False)
    monkeypatch.setattr(runner, "download_factors", lambda path: factors)

    runner.main(["--data-dir", str(tmp_path)])

    out = capsys.readouterr().out
    assert out.startswith("6 purchases, 2 sales, 3 stocks, returns 2020-01-02 to")
    assert "Q1: copy portfolio" in out
    assert "| transaction | 125 | 6 |" in out
    assert "pre-event intercept projected" in out
    assert "market-model CARs" in out
    assert "| Sales from disclosure | 2 |" in out


def test_amount_midpoint():
    ranges = pd.Series(["$1,001 - $15,000", "Over $50,000,000", ""])
    values = runner.amount_midpoint(ranges)
    assert values[0] == 8000.5
    assert values[1] == 50_000_000
    assert np.isnan(values[2])


def test_robustness_table_runs_every_check():
    returns, factors, events = constructed_inputs()
    purchases = purchases_only(events)
    table = runner.robustness_table(returns, factors, purchases, events[events["side"] == "sale"])
    assert len(table) == 8
    counts = dict(zip(table["check"], table["events"], strict=True))
    assert counts["Primary: purchases from disclosure"] == 5
    assert counts["Drop the five most active members"] == 0
    assert counts["Members' own trades only"] == 3
    assert counts["Senate purchases from the trade date"] == 2
    lines = runner.format_robustness(table).splitlines()
    assert "| Drop the five most active members | 0 | n/a | | | |" in lines
