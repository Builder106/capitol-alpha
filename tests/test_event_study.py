"""Tests for the event study estimators (pipeline.event_study).

Every return and factor series here is a constructed test fixture with a known
answer. None of it is market data.
"""

import io
import math
import zipfile

import numpy as np
import pandas as pd
import pytest

from pipeline import event_study as es

FRENCH_SAMPLE = (
    "This file was created by using the 202609 CRSP database.\r\n"
    "\r\n"
    ",Mkt-RF,SMB,HML,RF\r\n"
    "20260929,   -0.21,   -0.01,   -0.50,    0.01\r\n"
    "20260930,   -0.26,  -99.99,   -0.88,    0.01\r\n"
    "\r\n"
    "Copyright 2026 Eugene F. Fama and Kenneth R. French\r\n"
)
MOMENTUM_SAMPLE = "Momentum notes\r\n,Mom\r\n20260929,  -0.31\r\n20260930,   0.32\r\n\r\n"


def constructed_market(n_days: int = 400, seed: int = 7) -> pd.DataFrame:
    """Constructed daily factors with a fixed seed (test fixture, not market data)."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2021-01-04", periods=n_days)
    values = rng.normal(0, 0.01, size=(n_days, 4))
    factors = pd.DataFrame(values, index=days, columns=list(es.FOUR_FACTOR))
    factors["RF"] = 0.0001
    return factors


def test_parse_french_csv():
    frame = es.parse_french_csv(FRENCH_SAMPLE)
    assert list(frame.columns) == ["Mkt-RF", "SMB", "HML", "RF"]
    assert frame.loc["2026-09-29", "Mkt-RF"] == pytest.approx(-0.0021)
    assert math.isnan(frame.loc["2026-09-30", "SMB"])
    assert len(frame) == 2


def test_download_factors_joins_and_saves(tmp_path, monkeypatch):
    def zipped(text: str) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("file.csv", text)
        return buffer.getvalue()

    class Response:
        def __init__(self, url: str) -> None:
            self.content = zipped(MOMENTUM_SAMPLE if "Momentum" in url else FRENCH_SAMPLE)

        def raise_for_status(self) -> None:
            pass

    monkeypatch.setattr(es.requests, "get", lambda url, timeout: Response(url))
    path = tmp_path / "factors" / "french.csv"
    factors = es.download_factors(path)
    assert list(factors.columns) == ["Mkt-RF", "SMB", "HML", "RF", "Mom"]
    assert factors.loc["2026-09-30", "Mom"] == pytest.approx(0.0032)
    assert path.exists()


def test_main_downloads_factors(monkeypatch, capsys):
    monkeypatch.setattr(es, "download_factors", lambda: es.parse_french_csv(FRENCH_SAMPLE))
    es.main(["factors"])
    out = capsys.readouterr().out
    assert out.startswith("2 days, 2026-09-29 to 2026-09-30 ->")
    assert "missing values: 1" in out


def test_event_day():
    days = pd.DatetimeIndex(["2021-01-04", "2021-01-05", "2021-01-07"])
    assert es.event_day(days, pd.Timestamp("2021-01-01")) == 0
    assert es.event_day(days, pd.Timestamp("2021-01-05")) == 1
    assert es.event_day(days, pd.Timestamp("2021-01-06")) == 2
    assert es.event_day(days, pd.Timestamp("2021-01-08")) is None


def test_entry_day_is_first_trading_day_strictly_after():
    days = pd.DatetimeIndex(["2021-01-08", "2021-01-11", "2021-01-12"])
    assert es.entry_day(days, pd.Timestamp("2021-01-08")) == 1
    assert es.entry_day(days, pd.Timestamp("2021-01-09")) == 1
    assert es.entry_day(days, pd.Timestamp("2021-01-10")) == 1
    assert es.entry_day(days, pd.Timestamp("2021-01-12")) is None


def test_weekend_disclosure_enters_on_monday():
    factors = constructed_market()
    days = factors.index
    returns = pd.DataFrame({"AAA": factors["RF"] + factors["Mkt-RF"]})
    friday = next(day for day in days[10:] if day.day_of_week == 4)
    saturday = friday + pd.Timedelta(days=1)
    events = pd.DataFrame({"security": ["AAA"], "date": [saturday]})
    portfolio = es.copy_portfolio(returns, factors, events, "date", holding_days=3)
    assert list(portfolio.index) == list(days[days > saturday][:3])
    assert portfolio.index[0].day_of_week == 0
    at_close = es.copy_portfolio(returns, factors, events, "date", holding_days=3, start_offset=1)
    assert list(at_close.index) == list(days[days > saturday][1:4])


def test_ols_recovers_exact_coefficients():
    x = np.array([[1.0, 2.0], [2.0, 1.0], [3.0, 5.0], [4.0, 3.0]])
    y = 0.5 + x @ np.array([2.0, -1.0])
    coef, resid = es.ols(y, x)
    assert coef == pytest.approx([0.5, 2.0, -1.0])
    assert np.abs(resid).max() < 1e-12


def test_abnormal_returns_recovers_known_car():
    factors = constructed_market()
    days = factors.index
    normal = factors["RF"] + 0.0005 + 1.2 * factors["Mkt-RF"] + 0.5 * factors["SMB"]
    returns = pd.DataFrame({"AAA": normal, "GAP": normal})
    returns.iloc[300:321, 0] += 0.01
    returns.iloc[100:300, 1] = np.nan
    events = pd.DataFrame(
        {
            "security": ["AAA", "AAA", "ZZZ", "GAP", "AAA"],
            "date": [days[300], days[100], days[300], days[300], days[390]],
        }
    )
    cars = es.abnormal_returns(returns, factors, events, "date", horizons=(20, 62))

    assert cars.loc[0, "car_20"] == pytest.approx(21 * (0.0005 + 0.01))
    assert cars.loc[0, "car_62"] == pytest.approx(0.21 + 63 * 0.0005)
    projected = es.abnormal_returns(
        returns, factors, events, "date", horizons=(20,), project_alpha=True
    )
    assert projected.loc[0, "car_20"] == pytest.approx(0.21)
    assert cars.iloc[1:4].isna().all().all()
    assert math.isnan(cars.loc[4, "car_20"])


def test_abnormal_returns_after_event_matches_holding_window():
    factors = constructed_market()
    days = factors.index
    normal = factors["RF"] + 1.2 * factors["Mkt-RF"]
    returns = pd.DataFrame({"AAA": normal})
    returns.iloc[300, 0] += 0.05
    returns.iloc[301:321, 0] += 0.01
    events = pd.DataFrame({"security": ["AAA", "AAA"], "date": [days[300], days[-1]]})
    after = es.abnormal_returns(returns, factors, events, "date", horizons=(20,), after_event=True)
    from_zero = es.abnormal_returns(returns, factors, events, "date", horizons=(20,))
    assert after.loc[0, "car_20"] == pytest.approx(20 * 0.01)
    assert from_zero.loc[0, "car_20"] == pytest.approx(0.05 + 20 * 0.01)
    assert math.isnan(after.loc[1, "car_20"])


def test_gap_abnormal_returns_covers_trade_to_entry():
    factors = constructed_market()
    days = factors.index
    returns = pd.DataFrame({"AAA": factors["RF"] + factors["Mkt-RF"]})
    returns["GAP"] = returns["AAA"]
    returns.iloc[40:300, 1] = np.nan
    returns.iloc[300:306, 0] += 0.002
    returns.iloc[306, 0] += 0.5
    events = pd.DataFrame(
        {
            "security": ["AAA", "AAA", "ZZZ", "GAP"],
            "transaction_date": [days[300]] * 4,
            "disclosure_date": [days[305], days[298], days[305], days[305]],
        }
    )
    gaps = es.gap_abnormal_returns(returns, factors, events)
    assert gaps.loc[0, "gap_days"] == 6
    assert gaps.loc[0, "gap_car"] == pytest.approx(6 * 0.002)
    assert gaps.loc[1:3].isna().all().all()


def test_newey_west_lag_zero_is_white():
    rng = np.random.default_rng(1)
    x = np.column_stack([np.ones(50), rng.normal(size=50)])
    resid = rng.normal(size=50)
    bread = np.linalg.inv(x.T @ x)
    white = bread @ (x.T * resid**2) @ x @ bread
    assert es.newey_west(x, resid, 0) == pytest.approx(white)
    hac = es.newey_west(x, resid, 3)
    assert hac == pytest.approx(hac.T)
    assert es.newey_west_lag(1000) == 6


def test_normal_p():
    assert es.normal_p(1.959963984540054) == pytest.approx(0.05)


def test_calendar_time_alpha_recovers_alpha_and_holding_days():
    factors = constructed_market()
    days = factors.index
    rng = np.random.default_rng(3)
    base = factors["RF"] + 0.002 + factors["Mkt-RF"]
    returns = pd.DataFrame(
        {name: base + rng.normal(0, 0.0001, len(days)) for name in ("AAA", "BBB")}
    )
    events = pd.DataFrame(
        {
            "security": ["AAA", "BBB", "AAA", "ZZZ", "BBB"],
            "date": [days[100], days[105], days[102], days[200], pd.Timestamp("2030-01-01")],
        }
    )
    result = es.calendar_time_alpha(returns, factors, events, "date", holding_days=10)

    assert result["days"] == 15
    assert result["alpha_daily"] == pytest.approx(0.002, abs=1e-4)
    assert result["lag"] == es.newey_west_lag(15)
    assert result["p"] < 0.001
    fixed = es.calendar_time_alpha(returns, factors, events, "date", holding_days=10, lag=4)
    assert fixed["lag"] == 4
    assert fixed["alpha_daily"] == result["alpha_daily"]


def test_two_way_clustered_mean():
    values = pd.Series([1.0, 2.0, 3.0, 4.0])
    first = pd.Series(["a", "a", "b", "b"])
    second = pd.Series(["x", "y", "x", "y"])
    mean, se = es.two_way_clustered_mean(values, first, second)
    assert mean == 2.5
    assert se == pytest.approx(math.sqrt(5 / 16))


def test_two_way_clustered_mean_floors_negative_variance():
    values = pd.Series([1.0, -1.0, -1.0, 1.0])
    first = pd.Series(["a", "a", "b", "b"])
    second = pd.Series(["x", "y", "x", "y"])
    assert es.two_way_clustered_mean(values, first, second) == (0.0, 0.0)


def test_holm():
    adjusted = es.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adjusted == pytest.approx({"a": 0.03, "c": 0.06, "b": 0.06})
    assert es.holm({"x": 0.6, "y": 0.7}) == {"x": 1.0, "y": 1.0}


def test_calendar_time_alpha_weights_events():
    factors = constructed_market()
    days = factors.index
    rng = np.random.default_rng(5)
    noise = rng.normal(0, 0.00005, (len(days), 2))
    returns = pd.DataFrame(
        {
            "AAA": factors["RF"] + 0.002 + factors["Mkt-RF"] + noise[:, 0],
            "BBB": factors["RF"] + factors["Mkt-RF"] + noise[:, 1],
        }
    )
    returns.iloc[50, 1] = np.nan
    events = pd.DataFrame(
        {
            "security": ["AAA", "BBB", "BBB"],
            "date": [days[40], days[40], days[40]],
            "weight": [3.0, 1.0, np.nan],
        }
    )
    weighted = es.calendar_time_alpha(returns, factors, events, "date", 30, weight_column="weight")
    equal = es.calendar_time_alpha(returns, factors, events, "date", 30)
    assert weighted["alpha_daily"] == pytest.approx(0.0015, abs=1e-4)
    assert equal["alpha_daily"] == pytest.approx(0.001, abs=1e-4)
    assert weighted["days"] == equal["days"] == 30
