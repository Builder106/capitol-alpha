"""Run the event study in docs/specs/event-study.md on fetched CRSP data.

Usage:
    python -m pipeline.run_event_study --data-dir DIR

Reads DIR/events.csv and DIR/returns.csv.gz written by pipeline.crsp,
downloads the daily factors into DIR, and prints the results as Markdown.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from .crsp import wide_returns
from .event_study import (
    FOUR_FACTOR,
    HORIZONS,
    MARKET,
    abnormal_returns,
    calendar_time_alpha,
    download_factors,
    holm,
    normal_p,
    two_way_clustered_mean,
)

PRIMARY_HOLDING = 62
DAYS_PER_YEAR = 252
OWN_OWNERS = {"", "Self"}


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


def car_table(
    returns: pd.DataFrame,
    factors: pd.DataFrame,
    events: pd.DataFrame,
    project_alpha: bool = False,
    model: tuple[str, ...] = FOUR_FACTOR,
) -> pd.DataFrame:
    """Mean CARs with two-way clustered errors and Holm-adjusted p-values."""
    samples = (
        ("disclosure", "disclosure_date", events[events["q1_eligible"]]),
        ("transaction", "transaction_date", events),
    )
    rows = []
    for label, column, sample in samples:
        cars = abnormal_returns(
            returns, factors, sample, column, model=model, project_alpha=project_alpha
        )
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


def amount_midpoint(ranges: pd.Series) -> pd.Series:
    """Midpoint of a disclosed band such as "$1,001 - $15,000"; the floor if open-ended."""

    def parse(text: object) -> float:
        numbers = [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", str(text))][:2]
        return sum(numbers) / len(numbers) if numbers else float("nan")

    return ranges.map(parse)


def robustness_table(
    returns: pd.DataFrame, factors: pd.DataFrame, purchases: pd.DataFrame, sales: pd.DataFrame
) -> pd.DataFrame:
    """The plan's robustness checks on the primary test (62-day copy portfolio)."""
    q1 = purchases[purchases["q1_eligible"]]
    busiest = q1["legislator_name"].value_counts().index[:5]
    checks = [
        ("Primary: purchases from disclosure", q1, "disclosure_date", None),
        (
            "Leave out trades made in 2020",
            q1[q1["transaction_date"].dt.year != 2020],
            "disclosure_date",
            None,
        ),
        (
            "Drop the five most active members",
            q1[~q1["legislator_name"].isin(busiest)],
            "disclosure_date",
            None,
        ),
        (
            "Weight by disclosed amount",
            q1.assign(weight=amount_midpoint(q1["amount_range"])),
            "disclosure_date",
            "weight",
        ),
        (
            "Members' own trades only",
            q1[q1["owner"].fillna("").isin(OWN_OWNERS)],
            "disclosure_date",
            None,
        ),
        (
            "House purchases from the trade date",
            purchases[purchases["chamber"] == "House"],
            "transaction_date",
            None,
        ),
        (
            "Senate purchases from the trade date",
            purchases[purchases["chamber"] == "Senate"],
            "transaction_date",
            None,
        ),
        ("Sales from disclosure", sales[sales["q1_eligible"]], "disclosure_date", None),
    ]
    rows = []
    for label, sample, column, weight in checks:
        row: dict[str, object] = {"check": label, "events": len(sample)}
        if len(sample):
            result = calendar_time_alpha(
                returns, factors, sample, column, PRIMARY_HOLDING, weight_column=weight
            )
            row |= {"alpha_annual": result["alpha_daily"] * DAYS_PER_YEAR, **result}
        rows.append(row)
    return pd.DataFrame(rows)


def format_robustness(table: pd.DataFrame) -> str:
    lines = [
        "| Check | Events | Alpha (annual) | t | p | Days |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in table.itertuples():
        if pd.isna(row.alpha_annual):
            lines.append(f"| {row.check} | {row.events:,} | n/a | | | |")
            continue
        lines.append(
            f"| {row.check} | {row.events:,} | {row.alpha_annual:.2%} | {row.t:.2f} "
            f"| {row.p:.3f} | {int(row.days):,} |"
        )
    return "\n".join(lines)


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
    sales = events[events["side"] == "sale"]
    events = events[events["side"] == "purchase"]
    print(f"{len(events):,} purchases, {len(sales):,} sales, {returns.shape[1]:,} stocks, ", end="")
    print(f"returns {returns.index.min():%Y-%m-%d} to {returns.index.max():%Y-%m-%d}")
    print("\nQ1: copy portfolio from the disclosure date (four-factor alpha)\n")
    print(format_calendar(calendar_time_table(returns, factors, events)))
    print("\nEvent-level four-factor CARs (trading days)\n")
    print(format_cars(car_table(returns, factors, events)))
    print("\nSame CARs with the pre-event intercept projected (first run, kept for disclosure)\n")
    print(format_cars(car_table(returns, factors, events, project_alpha=True)))
    print("\nEvent-level market-model CARs (trading days)\n")
    print(format_cars(car_table(returns, factors, events, model=MARKET)))
    print("\nRobustness: 62-day copy portfolio, four-factor alpha\n")
    print(format_robustness(robustness_table(returns, factors, events, sales)))


if __name__ == "__main__":
    main()
