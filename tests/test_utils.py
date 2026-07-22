import pandas as pd
import pytest
from utils.check_covid import run_check_covid
from utils.mappings import clean_house_names as mappings_clean, update_flourish_export, party_map
from utils.patch_code import clean_house_names as patch_clean

def test_clean_house_names():
    assert mappings_clean("Hon.. John Doe") == "John Doe"
    assert mappings_clean("Doe, Hon. John") == "John Doe"
    assert mappings_clean("Doe, Hon.. John") == "John Doe"
    assert mappings_clean("Mrs. Jane Smith") == "Jane Smith"
    assert mappings_clean("Fields Cleo") == "Cleo Fields"
    assert mappings_clean(123) == 123
    assert patch_clean("Spartz Victoria") == "Victoria Spartz"
    assert patch_clean("Meijer Peter") == "Peter Meijer"
    assert patch_clean(None) is None

def test_update_flourish_export(tmp_path):
    csv_file = tmp_path / "flourish.csv"
    df_init = pd.DataFrame({
        "legislator_name ": ["Nancy Pelosi", "Unknown Person"],
        " Party ": ["Democrat", "Unknown"],
        "2020": [100, 50]
    })
    df_init.to_csv(csv_file, index=False)

    df_res, missing_names = update_flourish_export(str(csv_file))
    assert "Nancy Pelosi" in df_res["legislator_name"].values
    assert "Unknown Person" in missing_names

def test_run_check_covid(tmp_path):
    csv_file = tmp_path / "trades.csv"
    df_init = pd.DataFrame({
        "legislator_name": ["Alice", "Bob"],
        "transaction_date": ["2020-02-01", "2020-03-01"],
        "transaction_type": ["Sale", "Buy"],
        "amount_avg": [10000.0, 5000.0]
    })
    df_init.to_csv(csv_file, index=False)

    total_sales, top_amt, rem_amt = run_check_covid(str(csv_file))
    assert total_sales == 10000.0

def test_flourish_two_columns(tmp_path):
    csv_file = tmp_path / "flourish_2col.csv"
    df_init = pd.DataFrame({
        "legislator_name": ["Unknown Person"],
        "Party": ["Unknown"]
    })
    df_init.to_csv(csv_file, index=False)
    df_res, missing_names = update_flourish_export(str(csv_file))
    assert "Unknown Person" in missing_names

def test_main_guards_utils(tmp_path, monkeypatch):
    import runpy
    # patch_code main
    runpy.run_module("utils.patch_code", run_name="__main__")

    # check_covid main
    trades_csv = tmp_path / "legislative_trades.csv"
    pd.DataFrame({
        "legislator_name": ["Alice"],
        "transaction_date": ["2020-02-01"],
        "transaction_type": ["Sale"],
        "amount_avg": [100.0]
    }).to_csv(trades_csv, index=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    pd.DataFrame({
        "legislator_name": ["Alice"],
        "transaction_date": ["2020-02-01"],
        "transaction_type": ["Sale"],
        "amount_avg": [100.0]
    }).to_csv(tmp_path / "data" / "legislative_trades.csv", index=False)
    runpy.run_module("utils.check_covid", run_name="__main__")

    # mappings main
    pd.DataFrame({
        "legislator_name": ["Nancy Pelosi"],
        "Party": ["Democrat"],
        "2020": [100]
    }).to_csv(tmp_path / "data" / "flourish_racing_bar_export.csv", index=False)
    runpy.run_module("utils.mappings", run_name="__main__")
