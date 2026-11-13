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
    FIVE_FACTOR,
    FIVE_FACTOR_FILES,
    FOUR_FACTOR,
    HORIZONS,
    MARKET,
    abnormal_returns,
    calendar_time_alpha,
    copy_portfolio,
    download_factors,
    entry_day,
    factor_alpha,
    gap_abnormal_returns,
    holm,
    normal_p,
    two_way_clustered_mean,
)

PRIMARY_HOLDING = 62
DAYS_PER_YEAR = 252
OWN_OWNERS = {"", "Self"}
# CRSP daily data in this study end here; returns after it are ignored.
ANALYSIS_END = pd.Timestamp("2025-12-31")
NW_LAGS = (None, 21, 62)
SALES_CHECK = "Stocks sold, held long from disclosure"


def load_inputs(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    events = pd.read_csv(
        data_dir / "events.csv",
        index_col="event_id",
        parse_dates=["transaction_date", "disclosure_date"],
    )
    returns = wide_returns(pd.read_csv(data_dir / "returns.csv.gz"))
    return events, returns.loc[:ANALYSIS_END]


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
        (SALES_CHECK, sales[sales["q1_eligible"]], "disclosure_date", None),
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


def lag_sensitivity_table(
    returns: pd.DataFrame, factors: pd.DataFrame, events: pd.DataFrame
) -> pd.DataFrame:
    """Q1 t-statistics under the rule-of-thumb lag and longer Newey-West lags."""
    disclosed = events[events["q1_eligible"]]
    rows = []
    for holding in HORIZONS:
        for lag in NW_LAGS:
            result = calendar_time_alpha(
                returns, factors, disclosed, "disclosure_date", holding, lag=lag
            )
            rows.append({"holding_days": holding, **result})
    return pd.DataFrame(rows)


def close_entry_table(
    returns: pd.DataFrame, factors: pd.DataFrame, events: pd.DataFrame
) -> pd.DataFrame:
    """Q1 alpha when the copier buys at the close of the first trading day after disclosure.

    Close-to-close returns on the entry day include the overnight move before
    the open, which a copier who reads the filing that evening cannot earn.
    """
    disclosed = events[events["q1_eligible"]]
    rows = []
    for holding in HORIZONS:
        result = calendar_time_alpha(
            returns, factors, disclosed, "disclosure_date", holding, start_offset=1
        )
        rows.append(
            {
                "holding_days": holding,
                "primary": False,
                "alpha_annual": result["alpha_daily"] * DAYS_PER_YEAR,
                **result,
            }
        )
    return pd.DataFrame(rows)


def us_incorporated_check(
    returns: pd.DataFrame, factors: pd.DataFrame, events: pd.DataFrame
) -> dict[str, float] | None:
    """Q1 62-day alpha using only issuers CRSP flags as US-incorporated."""
    if "usincflg" not in events.columns:
        return None
    q1 = events[events["q1_eligible"] & (events["usincflg"] == "Y")]
    result = calendar_time_alpha(returns, factors, q1, "disclosure_date", PRIMARY_HOLDING)
    return {"events": len(q1), "alpha_annual": result["alpha_daily"] * DAYS_PER_YEAR, **result}


def five_factor_table(
    returns: pd.DataFrame, five: pd.DataFrame, events: pd.DataFrame
) -> pd.DataFrame:
    """Q1 alpha against the Fama-French five factors (the plan's robustness check)."""
    disclosed = events[events["q1_eligible"]]
    rows = []
    for holding in HORIZONS:
        result = calendar_time_alpha(
            returns, five, disclosed, "disclosure_date", holding, model=FIVE_FACTOR
        )
        rows.append(
            {
                "holding_days": holding,
                "alpha_annual": result["alpha_daily"] * DAYS_PER_YEAR,
                **result,
            }
        )
    return pd.DataFrame(rows)


def weighting_difference(
    returns: pd.DataFrame, factors: pd.DataFrame, events: pd.DataFrame
) -> dict[str, float]:
    """Four-factor alpha of the amount-weighted minus the equal-weighted 62-day portfolio."""
    q1 = events[events["q1_eligible"]].assign(
        weight=lambda frame: amount_midpoint(frame["amount_range"])
    )
    equal = copy_portfolio(returns, factors, q1, "disclosure_date", PRIMARY_HOLDING)
    weighted = copy_portfolio(
        returns, factors, q1, "disclosure_date", PRIMARY_HOLDING, weight_column="weight"
    )
    common = equal.index.intersection(weighted.index)
    result = factor_alpha(weighted[common] - equal[common], factors)
    return {"alpha_annual": result["alpha_daily"] * DAYS_PER_YEAR, **result}


def investable_car_table(
    returns: pd.DataFrame, factors: pd.DataFrame, events: pd.DataFrame
) -> pd.DataFrame:
    """CARs over the h trading days a copier holds, starting the day after disclosure."""
    disclosed = events[events["q1_eligible"]]
    cars = abnormal_returns(returns, factors, disclosed, "disclosure_date", after_event=True)
    rows = []
    for horizon in HORIZONS:
        values = cars[f"car_{horizon}"].dropna()
        members = disclosed.loc[values.index, "legislator_name"]
        months = disclosed.loc[values.index, "disclosure_date"].dt.strftime("%Y-%m")
        mean, se = two_way_clustered_mean(values, members, months)
        t = mean / se if se else float("nan")
        rows.append(
            {
                "event_date": "after disclosure",
                "horizon": horizon,
                "events": len(values),
                "mean_car": mean,
                "se": se,
                "t": t,
                "p": normal_p(t),
            }
        )
    table = pd.DataFrame(rows)
    adjusted = holm(dict(zip(table["horizon"].astype(str), table["p"], strict=True)))
    table["p_holm"] = [adjusted[str(h)] for h in table["horizon"]]
    return table


def gap_summary(
    returns: pd.DataFrame, factors: pd.DataFrame, events: pd.DataFrame
) -> dict[str, float]:
    """Mean abnormal return between the trade and the copier's first possible entry (House Q1)."""
    disclosed = events[events["q1_eligible"]]
    gaps = gap_abnormal_returns(returns, factors, disclosed).dropna()
    members = disclosed.loc[gaps.index, "legislator_name"]
    months = disclosed.loc[gaps.index, "transaction_date"].dt.strftime("%Y-%m")
    mean, se = two_way_clustered_mean(gaps["gap_car"], members, months)
    t = mean / se if se else float("nan")
    return {
        "events": len(gaps),
        "median_days": float(gaps["gap_days"].median()),
        "mean_car": mean,
        "se": se,
        "t": t,
        "p": normal_p(t),
    }


def censoring_summary(returns: pd.DataFrame, events: pd.DataFrame) -> dict[str, int]:
    """How many Q1 purchases enter the 62-day portfolio, and how many are cut short by the data end."""
    disclosed = events[events["q1_eligible"]]
    days = returns.index
    entries = [entry_day(days, date) for date in disclosed["disclosure_date"]]
    entered = [e for e in entries if e is not None]
    return {
        "eligible": len(disclosed),
        "entered": len(entered),
        "never_entered": len(entries) - len(entered),
        "partial": sum(e + PRIMARY_HOLDING > len(days) for e in entered),
    }


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


def format_summary(values: dict[str, float]) -> str:
    return ", ".join(
        f"{key} {value:.5f}" if isinstance(value, float) else f"{key} {value:,}"
        for key, value in values.items()
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the event study.")
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    events, returns = load_inputs(args.data_dir)
    factors = download_factors(args.data_dir / "french_daily.csv")
    five = download_factors(args.data_dir / "french_5_daily.csv", FIVE_FACTOR_FILES)
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
    print(
        "\nAdded after review: CARs over the copier's holding window (from the day after disclosure)\n"
    )
    print(format_cars(investable_car_table(returns, factors, events)))
    print("\nAdded after review: abnormal return from the trade to the copier's entry (House Q1)\n")
    print(format_summary(gap_summary(returns, factors, events)))
    print("\nAdded after review: Newey-West lag sensitivity (rule of thumb, 21, 62)\n")
    print(
        format_calendar(
            lag_sensitivity_table(returns, factors, events).assign(
                primary=False, alpha_annual=lambda f: f["alpha_daily"] * DAYS_PER_YEAR
            )
        )
    )
    print("\nPlanned five-factor check (Fama-French 2015), copy portfolio\n")
    print(format_calendar(five_factor_table(returns, five, events).assign(primary=False)))
    print("\nAdded after review: amount-weighted minus equal-weighted, 62 days\n")
    print(format_summary(weighting_difference(returns, factors, events)))
    print("\nAdded after review: buy at the close of the first trading day after disclosure\n")
    print(format_calendar(close_entry_table(returns, factors, events)))
    incorporated = us_incorporated_check(returns, factors, events)
    if incorporated is not None:
        print("\nAdded after review: US-incorporated issuers only, 62 days\n")
        print(format_summary(incorporated))
    print("\nCensoring of the 62-day portfolio\n")
    print(format_summary(censoring_summary(returns, events)))


if __name__ == "__main__":
    main()
