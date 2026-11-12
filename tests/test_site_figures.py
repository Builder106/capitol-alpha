"""Tests for the site figure data (pipeline.site_figures).

Returns and factors come from the constructed fixtures in
test_run_event_study. None of it is market data.
"""

import json

import pandas as pd

from pipeline import site_figures
from tests.test_run_event_study import constructed_inputs

SNAPSHOT_ROWS = [
    ["House", "A", "Sp", "AAPL", "01/04/2021", "01/14/2021", "P", "$1,001 - $15,000", "a.pdf"],
    ["House", "B", "", "MSFT", "02/01/2021", "05/03/2021", "S", "$1,001 - $15,000", "b.pdf"],
]
SNAPSHOT_COLUMNS = [
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


def test_car_path_has_one_point_per_day():
    returns, factors, events = constructed_inputs()
    purchases = events[events["side"] == "purchase"]
    path = site_figures.car_path(returns, factors, purchases, "transaction_date", last_day=5)
    assert [point["day"] for point in path] == [0, 1, 2, 3, 4, 5]
    assert all(point["events"] == 6 for point in path)
    assert all(point["se"] >= 0 for point in path)


def test_car_path_skips_days_without_events():
    returns, factors, events = constructed_inputs()
    late = events.assign(transaction_date=returns.index[-2])
    path = site_figures.car_path(returns, factors, late, "transaction_date", last_day=3)
    assert [point["day"] for point in path] == [0, 1]


def test_lag_histogram_bins_and_tail():
    lags = pd.Series([0, 4, 5, 13, 89, 90, 300])
    bins = site_figures.lag_histogram(lags, width=5, cap=90)
    assert bins[0] == {"from": 0, "to": 4, "trades": 2}
    assert bins[1] == {"from": 5, "to": 9, "trades": 1}
    assert bins[-2] == {"from": 85, "to": 89, "trades": 1}
    assert bins[-1] == {"from": 90, "to": 300, "trades": 2}
    assert sum(b["trades"] for b in bins) == len(lags)


def test_records_turns_missing_values_into_none():
    frame = pd.DataFrame({"check": ["a", "b"], "alpha_annual": [0.1, float("nan")]})
    assert site_figures.records(frame) == [
        {"check": "a", "alpha_annual": 0.1},
        {"check": "b", "alpha_annual": None},
    ]


def test_main_writes_valid_json(tmp_path, capsys):
    returns, factors, events = constructed_inputs()
    events.to_csv(tmp_path / "events.csv", index_label="event_id", date_format="%Y-%m-%d")
    long = returns.stack().rename("dlyret").rename_axis(["dlycaldt", "permno"]).reset_index()
    long.to_csv(tmp_path / "returns.csv.gz", index=False)
    factors.to_csv(tmp_path / "french_daily.csv")
    snapshot = tmp_path / "snapshot.csv"
    pd.DataFrame(SNAPSHOT_ROWS, columns=SNAPSHOT_COLUMNS).to_csv(snapshot, index=False)
    out = tmp_path / "site" / "figures.json"

    site_figures.main(["--data-dir", str(tmp_path), "--snapshot", str(snapshot), "--out", str(out)])

    data = json.loads(out.read_text())
    assert len(data["car_disclosure"]) == 126
    assert data["car_transaction"][0]["events"] == 6
    assert data["lag"]["median_days"] == 50.5
    assert data["lag"]["trades"] == 2
    assert [row["holding_days"] for row in data["calendar"]] == [20, 62, 125]
    assert len(data["robustness"]) == 8
    assert data["robustness"][2]["alpha_annual"] is None
    assert "wrote" in capsys.readouterr().out
