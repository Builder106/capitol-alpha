"""Event study estimators from docs/specs/event-study.md.

Returns come in as a wide frame of daily simple returns: a DatetimeIndex of
trading days and one column per security. The price source (CRSP or another)
only has to produce that frame and a security id on each event.

Usage:
    python -m pipeline.event_study factors
"""

from __future__ import annotations

import argparse
import io
import math
import re
import zipfile
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from .config import DATA_DIR

FRENCH_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{name}_CSV.zip"
FRENCH_FILES = ("F-F_Research_Data_Factors_daily", "F-F_Momentum_Factor_daily")
FIVE_FACTOR_FILES = ("F-F_Research_Data_5_Factors_2x3_daily",)
FACTORS_CSV = DATA_DIR / "factors" / "french_daily.csv"
MARKET = ("Mkt-RF",)
FOUR_FACTOR = ("Mkt-RF", "SMB", "HML", "Mom")
FIVE_FACTOR = ("Mkt-RF", "SMB", "HML", "RMW", "CMA")
DATA_ROW = re.compile(r"^\d{8},")
ESTIMATION = (-250, -30)
MIN_ESTIMATION_DAYS = 100
HORIZONS = (20, 62, 125)


def parse_french_csv(text: str) -> pd.DataFrame:
    """Parse one daily file from Kenneth French's data library into decimals."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if DATA_ROW.match(line))
    columns = [name.strip() for name in lines[start - 1].split(",")[1:]]
    rows = []
    for line in lines[start:]:
        if not DATA_ROW.match(line):
            break
        date, *values = line.split(",")
        rows.append([pd.Timestamp(date), *(float(value) for value in values)])
    frame = pd.DataFrame(rows, columns=["date", *columns]).set_index("date")
    return frame.where(frame > -99, np.nan) / 100


def download_factors(
    path: Path = FACTORS_CSV, files: tuple[str, ...] = FRENCH_FILES
) -> pd.DataFrame:
    """Download daily factor files (three factors and momentum by default), join them, save a CSV."""
    frames = []
    for name in files:
        response = requests.get(FRENCH_URL.format(name=name), timeout=60)
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            text = archive.read(archive.namelist()[0]).decode("latin-1")
        frames.append(parse_french_csv(text))
    factors = frames[0]
    for frame in frames[1:]:
        factors = factors.join(frame, how="inner")
    path.parent.mkdir(parents=True, exist_ok=True)
    factors.to_csv(path)
    return factors


def event_day(days: pd.DatetimeIndex, date: pd.Timestamp) -> int | None:
    """Position of the first trading day on or after ``date``."""
    position = int(days.searchsorted(date))
    return position if position < len(days) else None


def entry_day(days: pd.DatetimeIndex, date: pd.Timestamp) -> int | None:
    """Position of the first trading day strictly after ``date``: when a copier can first buy.

    A disclosure on a Saturday gives the Monday, not the Tuesday.
    """
    position = int(days.searchsorted(date, side="right"))
    return position if position < len(days) else None


def ols(y: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """OLS with an intercept. Returns coefficients (intercept first) and residuals."""
    design = np.column_stack([np.ones(len(y)), x])
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    return coef, y - design @ coef


def abnormal_returns(
    returns: pd.DataFrame,
    factors: pd.DataFrame,
    events: pd.DataFrame,
    date_column: str,
    model: tuple[str, ...] = FOUR_FACTOR,
    horizons: Iterable[int] = HORIZONS,
    project_alpha: bool = False,
    after_event: bool = False,
) -> pd.DataFrame:
    """Cumulative abnormal returns over [0, h] trading days for each event.

    ``after_event=True`` instead sums the h trading days a copier could hold:
    from the first trading day strictly after the event date (``entry_day``),
    the same window as the calendar-time portfolio.

    Betas come from trading days -250 to -30 and need at least 100 returns.
    The abnormal return removes factor exposure only. ``project_alpha=True``
    also subtracts the pre-event intercept, which pushes CARs down for stocks
    bought after a run-up (the first run did this; see JOURNAL.md).
    A CAR is missing when any return inside its window is missing.
    """
    days = returns.index.intersection(factors.index)
    excess = returns.loc[days].sub(factors.loc[days, "RF"], axis=0)
    loadings = factors.loc[days, list(model)].to_numpy()
    horizons = tuple(horizons)
    out = []
    for security, date in zip(events["security"], events[date_column], strict=True):
        out.append(dict.fromkeys((f"car_{h}" for h in horizons), np.nan))
        zero = event_day(days, date)
        if security not in excess.columns or zero is None or zero + ESTIMATION[0] < 0:
            continue
        y = excess[security].to_numpy()
        window = slice(zero + ESTIMATION[0], zero + ESTIMATION[1] + 1)
        usable = ~np.isnan(y[window])
        if usable.sum() < MIN_ESTIMATION_DAYS:
            continue
        coef, _ = ols(y[window][usable], loadings[window][usable])
        expected = loadings @ coef[1:] + (coef[0] if project_alpha else 0.0)
        start = entry_day(days, date) if after_event else zero
        if start is None:
            continue
        for h in horizons:
            stop = start + h if after_event else start + h + 1
            if stop <= len(days):
                span = slice(start, stop)
                out[-1][f"car_{h}"] = float(np.sum(y[span] - expected[span]))
    return pd.DataFrame(out, index=events.index)


def gap_abnormal_returns(
    returns: pd.DataFrame,
    factors: pd.DataFrame,
    events: pd.DataFrame,
    model: tuple[str, ...] = FOUR_FACTOR,
) -> pd.DataFrame:
    """Abnormal return a copier misses: from the trade until the first day they can buy.

    Sums abnormal returns from the first trading day on or after
    ``transaction_date`` up to, but not including, the entry day after
    ``disclosure_date``. Betas come from days -250 to -30 before the trade.
    Returns columns ``gap_car`` and ``gap_days`` (0 days when the trade and
    the entry fall on the same day).
    """
    days = returns.index.intersection(factors.index)
    excess = returns.loc[days].sub(factors.loc[days, "RF"], axis=0)
    loadings = factors.loc[days, list(model)].to_numpy()
    out = []
    for security, traded, disclosed in zip(
        events["security"], events["transaction_date"], events["disclosure_date"], strict=True
    ):
        out.append({"gap_car": np.nan, "gap_days": np.nan})
        zero = event_day(days, traded)
        entry = entry_day(days, disclosed)
        if security not in excess.columns or zero is None or entry is None:
            continue
        if zero + ESTIMATION[0] < 0 or entry < zero:
            continue
        y = excess[security].to_numpy()
        window = slice(zero + ESTIMATION[0], zero + ESTIMATION[1] + 1)
        usable = ~np.isnan(y[window])
        if usable.sum() < MIN_ESTIMATION_DAYS:
            continue
        coef, _ = ols(y[window][usable], loadings[window][usable])
        span = slice(zero, entry)
        out[-1] = {
            "gap_car": float(np.sum(y[span] - loadings[span] @ coef[1:])),
            "gap_days": entry - zero,
        }
    return pd.DataFrame(out, index=events.index)


def newey_west_lag(n: int) -> int:
    """Newey and West (1994) rule of thumb for the number of lags."""
    return math.floor(4 * (n / 100) ** (2 / 9))


def newey_west(x: np.ndarray, resid: np.ndarray, lag: int) -> np.ndarray:
    """HAC covariance of OLS coefficients with Bartlett weights. ``x`` includes the constant."""
    scores = x * resid[:, None]
    meat = scores.T @ scores
    for k in range(1, lag + 1):
        gamma = scores[k:].T @ scores[:-k]
        meat += (1 - k / (lag + 1)) * (gamma + gamma.T)
    bread = np.linalg.inv(x.T @ x)
    return bread @ meat @ bread


def normal_p(t: float) -> float:
    """Two-sided p-value from the normal distribution."""
    return math.erfc(abs(t) / math.sqrt(2))


def copy_portfolio(
    returns: pd.DataFrame,
    factors: pd.DataFrame,
    events: pd.DataFrame,
    date_column: str,
    holding_days: int,
    weight_column: str | None = None,
    start_offset: int = 0,
) -> pd.Series:
    """Daily return of a portfolio of stocks bought in the last ``holding_days``.

    A stock enters on the first trading day strictly after its event date
    (``entry_day``) and stays for ``holding_days`` trading days. Daily returns
    are close to close, so the first day's return includes the overnight move
    before the open; ``start_offset=1`` instead buys at that day's close and
    counts returns from the next day. With no
    ``weight_column``, each held stock gets equal weight however many events
    name it (equal weight by stock, not by purchase). Otherwise a stock's
    weight is the sum of its active events' weights, and events with a
    missing weight are skipped. Days with no holding are dropped.
    """
    days = returns.index.intersection(factors.index)
    weights = (
        events[weight_column] if weight_column else pd.Series(1.0, index=events.index)
    ).to_numpy(dtype=float)
    held = np.zeros((len(days), len(returns.columns)))
    for security, date, weight in zip(
        events["security"], events[date_column], weights, strict=True
    ):
        start = entry_day(days, date)
        if security in returns.columns and start is not None and not np.isnan(weight):
            start += start_offset
            held[start : start + holding_days, returns.columns.get_loc(security)] += weight
    if not weight_column:
        held = (held > 0).astype(float)
    values = returns.loc[days].to_numpy()
    active = np.where(np.isnan(values), 0.0, held)
    total = active.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        daily = np.nansum(values * active, axis=1) / total
    return pd.Series(daily, index=days)[total > 0]


def factor_alpha(
    excess: pd.Series,
    factors: pd.DataFrame,
    model: tuple[str, ...] = FOUR_FACTOR,
    lag: int | None = None,
) -> dict[str, float]:
    """Intercept of a daily excess-return series on the factors, with Newey-West errors.

    ``lag=None`` uses the Newey and West (1994) rule of thumb.
    """
    loadings = factors.loc[excess.index, list(model)].to_numpy()
    coef, resid = ols(excess.to_numpy(), loadings)
    design = np.column_stack([np.ones(len(excess)), loadings])
    lag = newey_west_lag(len(excess)) if lag is None else lag
    se = math.sqrt(newey_west(design, resid, lag)[0, 0])
    t = coef[0] / se
    return {
        "alpha_daily": float(coef[0]),
        "se": se,
        "t": t,
        "p": normal_p(t),
        "days": len(excess),
        "lag": lag,
    }


def calendar_time_alpha(
    returns: pd.DataFrame,
    factors: pd.DataFrame,
    events: pd.DataFrame,
    date_column: str,
    holding_days: int,
    model: tuple[str, ...] = FOUR_FACTOR,
    weight_column: str | None = None,
    lag: int | None = None,
    start_offset: int = 0,
) -> dict[str, float]:
    """Alpha of the copy portfolio (``copy_portfolio``) on the factors."""
    portfolio = copy_portfolio(
        returns, factors, events, date_column, holding_days, weight_column, start_offset
    )
    excess = portfolio - factors.loc[portfolio.index, "RF"]
    return factor_alpha(excess, factors, model, lag)


def two_way_clustered_mean(
    values: pd.Series, first: pd.Series, second: pd.Series
) -> tuple[float, float]:
    """Mean and its standard error clustered on two dimensions (Cameron, Gelbach, Miller 2011)."""
    resid = values - values.mean()
    n = len(values)

    def part(groups: pd.Series) -> float:
        return float((resid.groupby(groups.to_numpy()).sum() ** 2).sum())

    both = first.astype(str) + "|" + second.astype(str)
    variance = (part(first) + part(second) - part(both)) / n**2
    return float(values.mean()), math.sqrt(max(variance, 0.0))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Event study tools.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("factors", help=f"download daily factors to {FACTORS_CSV}")
    parser.parse_args(argv)

    factors = download_factors()
    first, last = factors.index.min(), factors.index.max()
    print(f"{len(factors):,} days, {first:%Y-%m-%d} to {last:%Y-%m-%d} -> {FACTORS_CSV}")
    print(f"missing values: {int(factors.isna().sum().sum())}")


def holm(pvalues: dict[str, float]) -> dict[str, float]:
    """Holm-adjusted p-values, capped at 1 and kept monotone."""
    ordered = sorted(pvalues.items(), key=lambda item: item[1])
    adjusted, running = {}, 0.0
    for rank, (name, p) in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - rank) * p))
        adjusted[name] = running
    return adjusted


if __name__ == "__main__":
    main()
