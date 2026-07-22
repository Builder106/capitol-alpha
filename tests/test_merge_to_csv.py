import pandas as pd

from pipeline.merge_to_csv import clean_dataframe


def test_clean_dataframe_basic():
    df = pd.DataFrame([
        {
            "chamber": "Senate",
            "legislator_name": " Ron L Wyden ",
            "transaction_date": "11/10/2020",
            "disclosure_date": "11/15/2020",
            "ticker": "aapl",
            "asset_description": "Apple Inc.",
            "asset_type": "Stock",
            "transaction_type": "Sale (Full)",
            "amount_range": "$50,001 - $100,000",
            "amount_min": "50001",
            "amount_max": "100000",
            "amount_avg": "75000.5",
            "owner": " spouse ",
            "ptr_link": "url",
            "office": "D-OR",
            "party": "D",
            "state": "OR",
            "transaction_year": 2020,
            "disclosure_year": 2020,
            "comment": "--",
        },
        {
            # duplicate row should be removed
            "chamber": "Senate",
            "legislator_name": "Ron L Wyden",
            "transaction_date": "11/10/2020",
            "disclosure_date": "11/15/2020",
            "ticker": "AAPL",
            "asset_description": "Apple Inc.",
            "asset_type": "Stock",
            "transaction_type": "Sale (Full)",
            "amount_range": "$50,001 - $100,000",
            "amount_min": "50001",
            "amount_max": "100000",
            "amount_avg": "75000.5",
            "owner": "Spouse",
            "ptr_link": "url",
            "office": "D-OR",
            "party": "D",
            "state": "OR",
            "transaction_year": 2020,
            "disclosure_year": 2020,
            "comment": "--",
        },
    ])

    cleaned = clean_dataframe(df)
    assert len(cleaned) == 1
    row = cleaned.iloc[0]
    assert row["legislator_name"] == "Ron L Wyden"
    assert row["ticker"] == "AAPL"
    assert row["transaction_type"] == "Sale"
    assert row["owner"] == "Spouse"
    assert row["amount_min"] == 50001.0
    assert row["amount_max"] == 100000.0
    assert row["amount_avg"] == 75000.5

def test_clean_dataframe_empty_and_nans():
    empty_df = pd.DataFrame()
    assert clean_dataframe(empty_df).empty

    df_nan = pd.DataFrame([
        {
            "legislator_name": pd.NA,
            "transaction_date": "2023-01-01",
            "ticker": None,
            "asset_description": "Description",
            "transaction_type": "Purchase",
            "owner": None
        }
    ])
    cleaned = clean_dataframe(df_nan)
    assert len(cleaned) == 1
    assert cleaned.iloc[0]["legislator_name"] is None
    assert cleaned.iloc[0]["ticker"] is None

def test_merge_to_csv(tmp_path, monkeypatch):
    import pipeline.merge_to_csv as mtc
    out_file = tmp_path / "output.csv"

    senate_df = pd.DataFrame([{
        "chamber": "Senate",
        "legislator_name": "Wyden Ron",
        "transaction_date": "2023-01-01",
        "ticker": "AAPL",
        "asset_description": "Apple",
        "transaction_type": "Purchase",
        "owner": "Self"
    }])
    house_df = pd.DataFrame([{
        "chamber": "House",
        "legislator_name": "Pelosi Nancy",
        "transaction_date": "2023-01-02",
        "ticker": "GOOGL",
        "asset_description": "Alphabet",
        "transaction_type": "Sale",
        "owner": "Spouse"
    }])

    res = mtc.merge_to_csv(senate_df=senate_df, house_df=house_df, output_path=str(out_file))
    assert len(res) == 2
    assert out_file.exists()

    # Test loading via fetchers (mocked)
    monkeypatch.setattr("pipeline.merge_to_csv.get_senate_df", lambda from_cache=True: senate_df)
    monkeypatch.setattr("pipeline.merge_to_csv.get_house_df", lambda from_cache=True: house_df)
    res_fetched = mtc.merge_to_csv(output_path=str(out_file))
    assert len(res_fetched) == 2

    # Test empty fetcher returns
    monkeypatch.setattr("pipeline.merge_to_csv.get_senate_df", lambda from_cache=True: pd.DataFrame())
    monkeypatch.setattr("pipeline.merge_to_csv.get_house_df", lambda from_cache=True: pd.DataFrame())
    res_empty = mtc.merge_to_csv(output_path=str(out_file))
    assert res_empty.empty
