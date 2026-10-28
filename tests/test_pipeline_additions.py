"""
Unit tests for new pipeline modules (fama_french.py and monitor.py) and edge branches.
"""

from pathlib import Path
import runpy
import sys
from unittest.mock import patch, MagicMock
import numpy as np
import pandas as pd
import pytest

from pipeline.fama_french import compute_factor_adjusted_alpha
from pipeline.monitor import analyze_trade_deltas
from pipeline.senate_fetcher import get_senate_df


def test_compute_factor_adjusted_alpha():
    df = pd.DataFrame({"roi_90d": [0.15, 0.18, 0.12, 0.20, 0.14]})
    bench = pd.Series([0.11, 0.11, 0.11, 0.11, 0.11])
    res = compute_factor_adjusted_alpha(df, bench)

    assert res["n_trades"] == 5
    assert res["capm_alpha"] > 0
    assert "fama_french_alpha" in res


def test_compute_factor_adjusted_alpha_empty_or_missing_column():
    # Empty dataframe
    empty_df = pd.DataFrame()
    res1 = compute_factor_adjusted_alpha(empty_df, pd.Series([0.1]))
    assert res1["n_trades"] == 0
    assert res1["p_value"] == 1.0

    # Missing roi_90d
    df_no_roi = pd.DataFrame({"other": [1, 2, 3]})
    res2 = compute_factor_adjusted_alpha(df_no_roi, pd.Series([0.1]))
    assert res2["n_trades"] == 0

    # All NaNs in roi_90d
    df_nans = pd.DataFrame({"roi_90d": [np.nan, np.nan]})
    res3 = compute_factor_adjusted_alpha(df_nans, pd.Series([0.1]))
    assert res3["n_trades"] == 0

    # Empty benchmark returns & single trade
    df_single = pd.DataFrame({"roi_90d": [0.15]})
    res4 = compute_factor_adjusted_alpha(df_single, pd.Series(dtype=float))
    assert res4["n_trades"] == 1
    assert res4["benchmark_mean_roi"] == 0.1116

    # Zero t-statistic branch (mean_trade_roi == benchmark_mean)
    df_zero = pd.DataFrame({"roi_90d": [0.10, 0.10]})
    res5 = compute_factor_adjusted_alpha(df_zero, pd.Series([0.10, 0.10]))
    assert res5["t_statistic"] == 0.0
    assert res5["p_value"] == 1.0


def test_fama_french_main(tmp_path, monkeypatch):
    # Test __main__ block when data file exists and when it does not
    ff_path = str(Path(__file__).parent.parent / "pipeline" / "fama_french.py")
    with patch("pipeline.fama_french.compute_factor_adjusted_alpha") as mock_calc:
        mock_calc.return_value = {"n_trades": 1}
        # Run with existing CSV
        with patch.object(Path, "exists", return_value=True):
            with patch("pandas.read_csv", return_value=pd.DataFrame({"roi_90d": [0.1]})):
                runpy.run_path(ff_path, run_name="__main__")

        # Run when file not found
        with patch.object(Path, "exists", return_value=False):
            runpy.run_path(ff_path, run_name="__main__")


def test_analyze_trade_deltas(tmp_path):
    # Non-existent file
    res_err = analyze_trade_deltas(tmp_path / "missing.csv")
    assert res_err["status"] == "error"

    # Existing file with columns
    csv_file = tmp_path / "test_trades.csv"
    df = pd.DataFrame(
        {
            "member_name": ["Alice", "Bob"],
            "transaction_date": ["2024-01-01", "2024-01-02"],
            "type": ["Purchase", "Sale"],
        }
    )
    df.to_csv(csv_file, index=False)

    summary = analyze_trade_deltas(csv_file)
    assert summary["status"] == "ok"
    assert summary["total_rows"] == 2
    assert summary["unique_legislators"] == 2
    assert "2024-01-01 to 2024-01-02" in summary["date_range"]

    # Existing file without standard columns
    csv_file_sparse = tmp_path / "sparse.csv"
    pd.DataFrame({"x": [1, 2]}).to_csv(csv_file_sparse, index=False)
    summary2 = analyze_trade_deltas(csv_file_sparse)
    assert summary2["unique_legislators"] == 0
    assert summary2["date_range"] == "N/A to N/A"


def test_monitor_main():
    mon_path = str(Path(__file__).parent.parent / "pipeline" / "monitor.py")
    with patch(
        "pandas.read_csv",
        return_value=pd.DataFrame(
            {"member_name": ["Alice"], "transaction_date": ["2024-01-01"], "type": ["Purchase"]}
        ),
    ):
        with patch.object(Path, "exists", return_value=True):
            runpy.run_path(mon_path, run_name="__main__")


def test_run_pipeline_main_execution(tmp_path):
    from pipeline.run_pipeline import main as run_pipeline_main
    import subprocess

    # Test __main__ guard with module execution
    subprocess.run([sys.executable, "-m", "pipeline.run_pipeline", "--help"], check=True)

    with patch("sys.argv", ["run_pipeline.py", "--senate-only"]):
        with patch("pipeline.senate_fetcher.SENATE_JSON_PATH") as mock_sen_path:
            with patch("pipeline.house_fetcher.HOUSE_JSON_PATH") as mock_house_path:
                with patch("pipeline.run_pipeline.SENATE_JSON_PATH") as mock_path:
                    with patch("pipeline.run_pipeline.HOUSE_JSON_PATH") as mock_h_path:
                        with patch("pipeline.run_pipeline.DATA_DIR", tmp_path):
                            mock_sen_path.exists.return_value = True
                            mock_house_path.exists.return_value = True
                            mock_path.exists.return_value = True
                            mock_h_path.exists.return_value = True
                            with patch(
                                "pipeline.senate_fetcher.get_senate_df",
                                return_value=pd.DataFrame([{"chamber": "Senate"}]),
                            ):
                                with patch(
                                    "pipeline.run_pipeline.get_senate_df",
                                    return_value=pd.DataFrame([{"chamber": "Senate"}]),
                                ):
                                    with patch("pandas.DataFrame.to_csv"):
                                        run_pipeline_main()


def test_scrapers_import_playwright_fallback():
    import builtins

    orig_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("playwright"):
            raise ImportError("No playwright")
        return orig_import(name, globals, locals, fromlist, level)

    senate_code = Path("pipeline/scrapers/senate_official.py").read_text()
    scope_senate = {
        "__name__": "pipeline.scrapers.senate_official",
        "__file__": str(Path("pipeline/scrapers/senate_official.py").resolve()),
        "__package__": "pipeline.scrapers",
    }
    with patch("builtins.__import__", side_effect=fake_import):
        exec(
            compile(
                senate_code, str(Path("pipeline/scrapers/senate_official.py").resolve()), "exec"
            ),
            scope_senate,
        )
        assert scope_senate["has_playwright"] is False
        assert scope_senate["sync_playwright"] is None

    house_code = Path("pipeline/scrapers/house_official.py").read_text()
    scope_house = {
        "__name__": "pipeline.scrapers.house_official",
        "__file__": str(Path("pipeline/scrapers/house_official.py").resolve()),
        "__package__": "pipeline.scrapers",
    }
    with patch("builtins.__import__", side_effect=fake_import):
        exec(
            compile(house_code, str(Path("pipeline/scrapers/house_official.py").resolve()), "exec"),
            scope_house,
        )
        assert scope_house["HAS_PLAYWRIGHT"] is False


def test_senate_fetcher_already_flat_raw(tmp_path):
    json_path = tmp_path / "senate.json"
    import json

    data = [
        {
            "first_name": "Jane",
            "last_name": "Doe",
            "office": "Senator",
            "report_type": "PTR",
            "date_received": "01/01/2023",
            "transactions": [
                {
                    "transaction_date": "01/01/2023",
                    "disclosure_date": "01/05/2023",
                    "ticker": "AAPL",
                    "asset_description": "Apple",
                    "type": "Purchase",
                    "amount": "$1,001 - $15,000",
                }
            ],
        }
    ]
    json_path.write_text(json.dumps(data))

    # Test when _flatten_senate_raw produces empty list but raw is a list
    with patch("pipeline.senate_fetcher.SENATE_JSON_PATH", json_path):
        with patch("pipeline.senate_fetcher._flatten_senate_raw", return_value=[]):
            # raw is a list of dicts that can be normalized
            flat_items = [
                {
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "office": "Senator",
                    "transaction_date": "01/01/2023",
                    "disclosure_date": "01/05/2023",
                    "ticker": "AAPL",
                    "asset_description": "Apple",
                    "type": "Purchase",
                    "amount": "$1,001 - $15,000",
                    "ptr_link": "http://ptr",
                }
            ]
            json_path.write_text(json.dumps(flat_items))
            df = get_senate_df()
            assert not df.empty
            assert df.iloc[0]["legislator_name"] == "Jane Doe"
