"""Run the event study in docs/specs/event-study.md on fetched CRSP data.

Usage:
    python -m pipeline.run_event_study --data-dir DIR

Reads DIR/events.csv and DIR/returns.csv.gz written by pipeline.crsp,
downloads the daily factors into DIR, and prints the results as Markdown.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .crsp import wide_returns
from .event_study import (
    HORIZONS,
    abnormal_returns,
    calendar_time_alpha,
    download_factors,
    holm,
    normal_p,
    two_way_clustered_mean,
)

PRIMARY_HOLDING = 62
DAYS_PER_YEAR = 252


def load_inputs(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    events = pd.read_csv(
        data_dir / "events.csv",
        index_col="event_id",
        parse_dates=["transaction_date", "disclosure_date"],
    )
    returns = wide_returns(pd.read_csv(data_dir / "returns.csv.gz"))
    return events, returns


def calendar_time_table(
    returns: pd.DataFrame, factors: pd.DataFrame, events: pd.DataFrame
) -> pd.DataFrame:
    """Q1: four-factor alpha of the copy portfolio from the disclosure date."""
    disclosed = events[events["q1_eligible"]]
    rows = []
    for holding in HORIZONS:
        result = calendar_time_alpha(returns, factors, disclosed, "disclosure_date", holding)
        rows.append(
            {
                "holding_days": holding,
                "primary": holding == PRIMARY_HOLDING,
                "alpha_annual": result["alpha_daily"] * DAYS_PER_YEAR,
                **result,
            }
        )
    return pd.DataFrame(rows)


def car_table(returns: pd.DataFrame, factors: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Mean four-factor CARs with two-way clustered errors and Holm-adjusted p-values."""
    samples = (
        ("disclosure", "disclosure_date", events[events["q1_eligible"]]),
        ("transaction", "transaction_date", events),
    )
    rows = []
    for label, column, sample in samples:
        cars = abnormal_returns(returns, factors, sample, column)
        for horizon in HORIZONS:
            values = cars[f"car_{horizon}"].dropna()
            members = sample.loc[values.index, "legislator_name"]
            months = sample.loc[values.index, column].dt.strftime("%Y-%m")
            mean, se = two_way_clustered_mean(values, members, months)
            t = mean / se if se else float("nan")
            rows.append(
                {
                    "event_date": label,
                    "horizon": horizon,
                    "events": len(values),
                    "mean_car": mean,
                    "se": se,
                    "t": t,
                    "p": normal_p(t),
                }
            )
    table = pd.DataFrame(rows)
    keys = [f"{row.event_date}-{row.horizon}" for row in table.itertuples()]
    adjusted = holm(dict(zip(keys, table["p"], strict=True)))
    table["p_holm"] = [adjusted[key] for key in keys]
    return table


def format_calendar(table: pd.DataFrame) -> str:
    lines = [
        "| Holding days | Primary | Alpha (annual) | Daily alpha | NW s.e. | t | p | Days | Lags |",
        "| ---: | :---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in table.itertuples():
        lines.append(
            f"| {row.holding_days} | {'yes' if row.primary else ''} | {row.alpha_annual:.2%} "
            f"| {row.alpha_daily:.5f} | {row.se:.5f} | {row.t:.2f} | {row.p:.3f} "
            f"| {row.days:,} | {row.lag} |"
        )
    return "\n".join(lines)


def format_cars(table: pd.DataFrame) -> str:
    lines = [
        "| Event date | Horizon | Events | Mean CAR | Clustered s.e. | t | p | Holm p |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in table.itertuples():
        lines.append(
            f"| {row.event_date} | {row.horizon} | {row.events:,} | {row.mean_car:.2%} "
            f"| {row.se:.2%} | {row.t:.2f} | {row.p:.3f} | {row.p_holm:.3f} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the event study.")
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    events, returns = load_inputs(args.data_dir)
    factors = download_factors(args.data_dir / "french_daily.csv")
    print(f"{len(events):,} events, {returns.shape[1]:,} stocks, ", end="")
    print(f"returns {returns.index.min():%Y-%m-%d} to {returns.index.max():%Y-%m-%d}")
    print("\nQ1: copy portfolio from the disclosure date (four-factor alpha)\n")
    print(format_calendar(calendar_time_table(returns, factors, events)))
    print("\nEvent-level four-factor CARs (trading days)\n")
    print(format_cars(car_table(returns, factors, events)))


if __name__ == "__main__":
    main()
