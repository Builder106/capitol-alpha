"""Write the aggregate numbers behind the project site's figures.

Usage:
    python -m pipeline.site_figures --data-dir DIR [--out site/data/figures.json]

Reads the CRSP extract written by pipeline.crsp and the factor file saved by
pipeline.run_event_study in DIR. The output holds aggregates only: the mean
four-factor CAR on each trading day after the event, the disclosure-lag
histogram, the copy-portfolio alphas, and the robustness estimates. No
stock-level return leaves the build machine.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .disclosure_lag import DEADLINE_DAYS, disclosure_lags
from .event_sample import SNAPSHOT, load_snapshot
from .event_study import HORIZONS, abnormal_returns, two_way_clustered_mean
from .run_event_study import calendar_time_table, load_inputs, robustness_table

OUT = Path(__file__).resolve().parent.parent / "site" / "data" / "figures.json"
LAST_DAY = max(HORIZONS)
LAG_BIN_DAYS = 5
LAG_CAP_DAYS = 90
PERCENTILES = list(range(1, 100))


def car_path(
    returns: pd.DataFrame,
    factors: pd.DataFrame,
    events: pd.DataFrame,
    date_column: str,
    last_day: int = LAST_DAY,
    percentiles: bool = False,
) -> list[dict[str, object]]:
    """Mean CAR over [0, d] for every trading day d, with two-way clustered errors.

    Each day uses every event that has returns through that day, so later days
    rest on fewer events. ``percentiles=True`` adds the 1st to 99th percentiles
    of that day's CARs, which the site uses to draw the spread across purchases.
    """
    cars = abnormal_returns(returns, factors, events, date_column, horizons=range(last_day + 1))
    path = []
    for day in range(last_day + 1):
        values = cars[f"car_{day}"].dropna()
        if values.empty:
            continue
        members = events.loc[values.index, "legislator_name"]
        months = events.loc[values.index, date_column].dt.strftime("%Y-%m")
        mean, se = two_way_clustered_mean(values, members, months)
        point: dict[str, object] = {"day": day, "events": len(values), "mean": mean, "se": se}
        if percentiles:
            point["p"] = [round(float(v), 4) for v in np.percentile(values, PERCENTILES)]
        path.append(point)
    return path


def lag_histogram(
    lag_days: pd.Series, width: int = LAG_BIN_DAYS, cap: int = LAG_CAP_DAYS
) -> list[dict[str, int]]:
    """Trades per bin of disclosure lag; the last bin holds every lag of ``cap`` days or more."""
    bins = []
    for start in range(0, cap, width):
        count = int(lag_days.between(start, start + width - 1).sum())
        bins.append({"from": start, "to": start + width - 1, "trades": count})
    bins.append({"from": cap, "to": int(lag_days.max()), "trades": int((lag_days >= cap).sum())})
    return bins


def records(frame: pd.DataFrame) -> list[dict[str, object]]:
    """Rows as plain dicts, with missing values as None so the JSON stays valid."""
    return frame.astype(object).where(frame.notna(), None).to_dict("records")


def figures(data_dir: Path, snapshot: Path = SNAPSHOT) -> dict[str, object]:
    events, returns = load_inputs(data_dir)
    factors = pd.read_csv(data_dir / "french_daily.csv", index_col=0, parse_dates=True)
    sales = events[events["side"] == "sale"]
    purchases = events[events["side"] == "purchase"]
    disclosed = purchases[purchases["q1_eligible"]]
    lags, _ = disclosure_lags(load_snapshot(snapshot))
    return {
        "car_disclosure": car_path(
            returns, factors, disclosed, "disclosure_date", percentiles=True
        ),
        "car_transaction": car_path(returns, factors, purchases, "transaction_date"),
        "lag": {
            "deadline_days": DEADLINE_DAYS,
            "median_days": float(lags["lag_days"].median()),
            "trades": len(lags),
            "bins": lag_histogram(lags["lag_days"]),
        },
        "calendar": records(
            calendar_time_table(returns, factors, purchases)[
                ["holding_days", "alpha_annual", "t", "p"]
            ]
        ),
        "robustness": records(
            robustness_table(returns, factors, purchases, sales)[
                ["check", "events", "alpha_annual", "t", "p"]
            ]
        ),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Write the site's figure data.")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)

    data = figures(args.data_dir, args.snapshot)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(data, separators=(",", ":"), allow_nan=False, default=float) + "\n"
    )
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
