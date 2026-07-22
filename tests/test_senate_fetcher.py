from pipeline.senate_fetcher import (
    _flatten_senate_raw,
    _normalize_senate_row,
    _parse_date,
)


def test_parse_date():
    assert _parse_date("01/15/2023") == 2023
    assert _parse_date("12/31/2020") == 2020
    assert _parse_date("2024-06-01") == 2024
    assert _parse_date("") is None
    assert _parse_date(None) is None
    assert _parse_date("invalid") is None


def test_flatten_senate_raw_nested():
    raw = [
        {
            "first_name": "Jane",
            "last_name": "Doe",
            "ptr_link": "https://example.com/ptr/1",
            "date_recieved": "01/10/2023",
            "transactions": [
                {"transaction_date": "01/05/2023", "ticker": "AAPL", "type": "Purchase", "amount": "$1,001 - $15,000"},
                {"transaction_date": "01/06/2023", "ticker": "MSFT", "type": "Sale", "amount": "$15,001 - $50,000"},
            ],
        }
    ]
    flat = _flatten_senate_raw(raw)
    assert len(flat) == 2
    assert flat[0]["first_name"] == "Jane" and flat[0]["ticker"] == "AAPL"
    assert flat[1]["ticker"] == "MSFT"


def test_flatten_senate_raw_flat():
    raw = [
        {"senator": "Ron Wyden", "transaction_date": "11/10/2020", "ticker": "BYND", "type": "Sale (Full)", "amount": "$50,001 - $100,000"}
    ]
    flat = _flatten_senate_raw(raw)
    assert len(flat) == 1
    assert flat[0]["senator"] == "Ron Wyden" and flat[0]["ticker"] == "BYND"


def test_normalize_senate_row_flat():
    r = {
        "senator": "Ron L Wyden",
        "transaction_date": "11/10/2020",
        "ticker": "BYND",
        "asset_description": "Beyond Meat, Inc.",
        "asset_type": "Stock",
        "type": "Sale (Full)",
        "amount": "$50,001 - $100,000",
        "owner": "Spouse",
        "ptr_link": "https://efdsearch.senate.gov/search/view/ptr/xxx/",
    }
    out = _normalize_senate_row(r)
    assert out["chamber"] == "Senate"
    assert out["legislator_name"] == "Ron L Wyden"
    assert out["transaction_date"] == "11/10/2020"
    assert out["ticker"] == "BYND"
    assert out["transaction_type"] == "Sale (Full)"
    assert out["amount_range"] == "$50,001 - $100,000"


def test_normalize_senate_row_first_last_name():
    r = {"first_name": "Jane", "last_name": "Doe", "transaction_date": "01/01/2023", "type": "Purchase"}
    out = _normalize_senate_row(r)
    assert out["legislator_name"] == "Jane Doe"


def test_parse_amount_range():
    from pipeline.senate_fetcher import _parse_amount_range

    assert _parse_amount_range("$1,001 - $15,000") == (1001.0, 15000.0)
    assert _parse_amount_range("$50,000+") == (50000.0, None)
    assert _parse_amount_range("$10,000") == (10000.0, 10000.0)
    assert _parse_amount_range("--") == (None, None)


def test_amount_range_parsing_values():
    from pipeline.senate_fetcher import _parse_amount_range

    assert _parse_amount_range("$1,001 - $15,000") == (1001.0, 15000.0)
    assert _parse_amount_range("$50,000+") == (50000.0, None)
    assert _parse_amount_range("$10,000") == (10000.0, 10000.0)
    assert _parse_amount_range("--") == (None, None)


def test_normalize_senate_row_amount_min_max_avg():
    r = {
        "senator": "Ron L Wyden",
        "transaction_date": "11/10/2020",
        "ticker": "BYND",
        "asset_description": "Beyond Meat, Inc.",
        "asset_type": "Stock",
        "type": "Sale (Full)",
        "amount": "$50,001 - $100,000",
        "owner": "Spouse",
        "ptr_link": "https://efdsearch.senate.gov/search/view/ptr/xxx/",
        "office": "D-OR",
    }
    out = _normalize_senate_row(r)
    assert out["amount_min"] == 50001.0
    assert out["amount_max"] == 100000.0
    assert out["amount_avg"] == 75000.5
    assert out["office"] == "D-OR"
    assert out["party"] == "D"
    assert out["state"] == "OR"

def test_parse_amount_range_exception_branches():
    from pipeline.senate_fetcher import _parse_amount_range
    assert _parse_amount_range("bad - range") == (None, None)
    assert _parse_amount_range("bad+") == (None, None)
    assert _parse_amount_range("not_a_number") == (None, None)

def test_parse_party_state_fallback():
    from pipeline.senate_fetcher import _parse_party_state
    party, state = _parse_party_state("UnknownOffice")
    assert party is None and state is None

def test_fetch_senate_and_get_senate_df(tmp_path, monkeypatch):
    import json, pytest, pipeline.senate_fetcher as sf
    fake_path = tmp_path / "senate_all_transactions.json"
    monkeypatch.setattr(sf, "SENATE_JSON_PATH", fake_path)

    # Missing file
    with pytest.raises(FileNotFoundError):
        sf.fetch_senate()
    with pytest.raises(FileNotFoundError):
        sf.get_senate_df()

    # Empty raw file
    fake_path.write_text("[]")
    assert sf.fetch_senate().empty

    # Sample transactions
    sample = [
        {
            "senator": "Ron Wyden",
            "transaction_date": "11/10/2020",
            "ticker": "BYND",
            "amount": "$1,001 - $15,000"
        },
        {
            "senator": "Old Senator",
            "transaction_date": "11/10/1980",  # Out of range
            "amount": "$1,001 - $15,000"
        }
    ]
    fake_path.write_text(json.dumps(sample))
    df = sf.fetch_senate()
    assert len(df) == 1
    assert df.iloc[0]["legislator_name"] == "Ron Wyden"

    df_cache = sf.get_senate_df()
    assert len(df_cache) == 1

    # Dict format (senate JSON is list of report dicts with transactions)
    fake_path.write_text(json.dumps([{"senator": "Ron Wyden", "transaction_date": "11/10/2020", "amount": "$1,001 - $15,000"}]))
    assert len(sf.fetch_senate()) == 1

    # Flat list format for get_senate_df
    fake_path.write_text(json.dumps([{"senator": "Ron Wyden", "transaction_date": "11/10/2020", "amount": "$1,001 - $15,000"}]))
    assert len(sf.get_senate_df(from_cache=True)) == 1
    assert len(sf.get_senate_df(from_cache=False)) == 1
