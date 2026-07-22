import pytest
import pandas as pd
from pipeline.house_fetcher import _parse_date, _parse_amount_range, _normalize_house_row

def test_parse_date():
    assert _parse_date("01/15/2021") == 2021
    assert _parse_date("2021-01-15") == 2021
    assert _parse_date("1/15/21") == 2021
    assert _parse_date("invalid") is None
    assert _parse_date("") is None
    assert _parse_date(None) is None

def test_parse_amount_range():
    assert _parse_amount_range("$1,001 - $15,000") == (1001.0, 15000.0)
    assert _parse_amount_range("1001 - 15000") == (1001.0, 15000.0)
    assert _parse_amount_range("$50,000,000+") == (50000000.0, None)
    assert _parse_amount_range("500") == (500.0, 500.0)
    assert _parse_amount_range("Unknown") == (None, None)
    assert _parse_amount_range("N/A") == (None, None)
    assert _parse_amount_range(None) == (None, None)

def test_normalize_house_row():
    raw_row = {
        "representative": "Nancy Pelosi",
        "disclosure_date": "05/15/2023",
        "transaction_date": "05/01/2023",
        "ticker": " GOOGL ",
        "asset_description": "Alphabet Inc.",
        "type": "Purchase",
        "amount": "$1,001 - $15,000",
        "owner": "Spouse",
        "ptr_link": "https://example.com/doc.pdf",
        "office": "D-CA"
    }
    
    normalized = _normalize_house_row(raw_row)
    
    assert normalized["chamber"] == "House"
    assert normalized["legislator_name"] == "Nancy Pelosi"
    assert normalized["disclosure_date"] == "05/15/2023"
    assert normalized["transaction_date"] == "05/01/2023"
    assert normalized["ticker"] == "GOOGL"
    assert normalized["asset_description"] == "Alphabet Inc."
    assert normalized["transaction_type"] == "Purchase"
    assert normalized["amount_range"] == "$1,001 - $15,000"
    assert normalized["amount_min"] == 1001.0
    assert normalized["amount_max"] == 15000.0
    assert normalized["amount_avg"] == 8000.5
    assert normalized["owner"] == "Spouse"
    assert normalized["ptr_link"] == "https://example.com/doc.pdf"
    assert normalized["office"] == "D-CA"
    assert normalized["party"] == "D"
    assert normalized["state"] == "CA"

def test_normalize_house_row_fallback_fields():
    # Tests alternate field names like first_name/last_name, asset_name, transaction_type
    raw_row = {
        "first_name": "Ro",
        "last_name": "Khanna",
        "date_received": "01/10/2022",
        "asset_name": "Apple Inc.",
        "transaction_type": "Sale (Partial)",
        "amount_range": "$15,001 - $50,000",
        "disclosure_link": "https://example.com/link"
    }
    
    normalized = _normalize_house_row(raw_row)
    
    assert normalized["legislator_name"] == "Ro Khanna"
    assert normalized["disclosure_date"] == "01/10/2022"
    assert normalized["transaction_date"] == "01/10/2022"  # fallback to disclosure date
    assert normalized["asset_description"] == "Apple Inc."
    assert normalized["transaction_type"] == "Sale (Partial)"
    assert normalized["amount_range"] == "$15,001 - $50,000"
    assert normalized["amount_min"] == 15001.0
    assert normalized["amount_max"] == 50000.0
    assert normalized["ptr_link"] == "https://example.com/link"

def test_parse_amount_range_invalid_branches():
    assert _parse_amount_range("abc - def") == (None, None)
    assert _parse_amount_range("abc+") == (None, None)
    assert _parse_amount_range("invalid_number") == (None, None)

def test_fetch_house_and_get_house_df(tmp_path, monkeypatch):
    import json, pipeline.house_fetcher as hf
    fake_path = tmp_path / "house_all_transactions.json"
    monkeypatch.setattr(hf, "HOUSE_JSON_PATH", fake_path)

    # Missing file error
    with pytest.raises(FileNotFoundError):
        hf.fetch_house()
    with pytest.raises(FileNotFoundError):
        hf.get_house_df()

    # Empty raw file
    fake_path.write_text("[]")
    assert hf.fetch_house().empty

    # List of transactions
    sample = [
        {
            "representative": "Pelosi Nancy",
            "transaction_date": "05/01/2022",
            "disclosure_date": "05/15/2022",
            "amount": "$1,001 - $15,000",
            "ticker": "AAPL"
        },
        {
            "representative": "Old Rep",
            "transaction_date": "05/01/1990",  # Out of range year
            "disclosure_date": "05/15/1990",
            "amount": "$1,001 - $15,000"
        }
    ]
    fake_path.write_text(json.dumps(sample))
    df = hf.fetch_house()
    assert len(df) == 1
    assert df.iloc[0]["legislator_name"] == "Pelosi Nancy"

    df_cache = hf.get_house_df()
    assert len(df_cache) == 1

    # Dict with transactions key
    fake_path.write_text(json.dumps({"transactions": sample}))
    df_dict = hf.fetch_house()
    assert len(df_dict) == 1
    assert len(hf.get_house_df()) == 1

    # Dict with data key
    fake_path.write_text(json.dumps({"data": sample}))
    assert len(hf.get_house_df()) == 1

    # Empty dict transactions
    fake_path.write_text(json.dumps({"transactions": []}))
    assert hf.fetch_house().empty
