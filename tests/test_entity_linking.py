"""Unit tests for Normalized Asset Entity Linking (pipeline.entity_linking)."""

import pandas as pd
import pytest

from pipeline.entity_linking import (
    _clean_description,
    _clean_entity_name,
    _is_non_equity,
    link_asset_entity,
    link_dataframe_entities,
    resolve_corporate_entity,
    resolve_ticker,
)
from pipeline.merge_to_csv import COLUMN_ORDER, clean_dataframe, merge_to_csv


def test_clean_description():
    assert _clean_description(None) == ""
    assert _clean_description(123) == ""  # type: ignore[arg-type]
    assert _clean_description("   ") == ""
    assert (
        _clean_description("OWENS &amp; MINOR <div><em>Rate:</em> 3.5%</div>")
        == "OWENS & MINOR Rate: 3.5%"
    )


def test_is_non_equity():
    assert _is_non_equity("Municipal bond") is True
    assert _is_non_equity("Revenue bond for water authority") is True
    assert _is_non_equity("U.S. Treasury Bill 0% 12/2023") is True
    assert _is_non_equity("Rate/Coupon: 4.5% Matures: 2024") is True
    assert _is_non_equity("Bitcoin digital currency") is True
    assert _is_non_equity("Disclosed via scanned PDF. See link.") is True
    assert _is_non_equity("Arbitrary text", asset_type="Bond") is True
    assert _is_non_equity("Arbitrary text", asset_type="Municipal Security") is True
    assert _is_non_equity("Arbitrary text", asset_type="Corporate Bond") is True
    assert _is_non_equity("Arbitrary text", asset_type="Non-Public Stock") is True
    assert _is_non_equity("Apple Inc. Common Stock", asset_type="Stock") is False


def test_clean_entity_name():
    assert _clean_entity_name("") is None
    assert _clean_entity_name("Common Stock - Apple Inc. (AAPL) [ST]") == "Apple Inc"
    assert _clean_entity_name("Shares of Microsoft Corp Class A") == "Microsoft Corp"
    assert _clean_entity_name("Tesoro Logistics LP CMN (Exchanged)") == "Tesoro Logistics LP"
    assert _clean_entity_name("Acme Widgets LLC Capital Stock") == "Acme Widgets LLC"
    assert _clean_entity_name("Description") is None
    assert _clean_entity_name("Stock") is None
    assert _clean_entity_name("x") is None


def test_resolve_ticker_explicit():
    assert resolve_ticker("Any Description", ticker="AAPL") == "AAPL"
    assert resolve_ticker("Any Description", ticker="  aapl  ") == "AAPL"
    assert resolve_ticker("Any Description", ticker="$MSFT") == "MSFT"
    assert resolve_ticker("Any Description", ticker="BRK.B") == "BRK.B"
    assert resolve_ticker("Any Description", ticker="BRK-B") == "BRK-B"

    # Placeholders and invalid formats fall back to description resolution
    assert resolve_ticker("Apple Inc.", ticker="--") == "AAPL"
    assert resolve_ticker("Apple Inc.", ticker="N/A") == "AAPL"
    assert resolve_ticker("Apple Inc.", ticker="NA") == "AAPL"
    assert resolve_ticker("Apple Inc.", ticker="NONE") == "AAPL"
    assert resolve_ticker("Apple Inc.", ticker="UNKNOWN") == "AAPL"
    assert resolve_ticker("Apple Inc.", ticker="") == "AAPL"
    assert resolve_ticker("Apple Inc.", ticker="ST") == "AAPL"  # excluded token
    assert resolve_ticker("Apple Inc.", ticker="TOOLONGTICKER") == "AAPL"


def test_resolve_ticker_embedded_patterns():
    # Parenthesized ticker
    assert resolve_ticker("Apple Inc. (AAPL)") == "AAPL"
    assert resolve_ticker("Alphabet Inc. (GOOGL)") == "GOOGL"
    assert resolve_ticker("Berkshire Hathaway (BRK.B)") == "BRK.B"
    assert resolve_ticker("Exchanged shares (ST)") is None  # excluded token

    # Bracketed ticker
    assert resolve_ticker("Tesla Motors [TSLA]") == "TSLA"
    assert resolve_ticker("Invalid tag [ST]") is None  # excluded token

    # Leading prefix
    assert resolve_ticker("GOOG - Alphabet Inc. C") == "GOOG"
    assert resolve_ticker("GMSYX - Goldman Sachs Small Cap Fund") == "GMSYX"
    assert resolve_ticker("ST - Stock Description") is None  # excluded token

    # Explicit label
    assert resolve_ticker("Holding Company, Ticker: MSFT") == "MSFT"
    assert resolve_ticker("Holding Company, Symbol: AMD") == "AMD"
    assert resolve_ticker("Holding Company, Ticker: CS") is None  # excluded token

    # Standalone ticker
    assert resolve_ticker("msft") == "MSFT"
    assert resolve_ticker("ba") == "BA"
    assert resolve_ticker("zm") == "ZM"
    assert resolve_ticker("WMT") == "WMT"
    assert resolve_ticker("st") is None  # excluded token
    assert resolve_ticker("not a ticker") is None


def test_resolve_ticker_company_lookup():
    assert resolve_ticker("The Boeing Company") == "BA"
    assert resolve_ticker("Amazon.com, Inc. - Online Retail") == "AMZN"
    assert resolve_ticker("Target Corporation") == "TGT"
    assert resolve_ticker("Costco Wholesale Corporation") == "COST"
    assert resolve_ticker("Walmart Inc.") == "WMT"
    assert resolve_ticker("Pfizer Inc CMN") == "PFE"
    assert resolve_ticker("SPDR S&P 500 ETF Trust") == "SPY"
    assert resolve_ticker("Invesco QQQ Trust Series 1") == "QQQ"
    assert resolve_ticker("Completely Unknown Asset Description") is None
    assert resolve_ticker(None) is None


def test_resolve_ticker_non_equity_exclusion():
    assert resolve_ticker("Municipal bond", ticker="--") is None
    assert resolve_ticker("New York City Municipal Water Fin Auth Revenue Bond") is None
    assert resolve_ticker("U.S. Treasury Bill 0% 12/15/2022") is None
    assert resolve_ticker("OWENS & MINOR Rate/Coupon: 3.875% Matures: 09/15/2021") is None
    assert resolve_ticker("Bitcoin Investment Trust") is None
    assert (
        resolve_ticker(
            "This filing was disclosed via scanned PDF. Use link in ptr_link column to view the PDF."
        )
        is None
    )
    assert resolve_ticker("Arbitrary description", asset_type="Bond") is None


def test_resolve_corporate_entity():
    # Known ticker lookup
    assert resolve_corporate_entity(None, ticker="AAPL") == "Apple Inc."
    assert resolve_corporate_entity(None, ticker="MSFT") == "Microsoft Corporation"
    assert resolve_corporate_entity(None, ticker="$AMZN") == "Amazon.com, Inc."
    assert resolve_corporate_entity(None, ticker="BRK.B") == "Berkshire Hathaway Inc."

    # Known company name in description without ticker
    assert resolve_corporate_entity("Apple Inc. Common Stock", ticker=None) == "Apple Inc."
    assert resolve_corporate_entity("The Boeing Company", ticker=None) == "The Boeing Company"

    # Non-equity exclusion
    assert resolve_corporate_entity("Municipal bond") is None
    assert resolve_corporate_entity("US Treasury Note", asset_type="Bond") is None

    # Fallback to cleaned description
    assert resolve_corporate_entity("Cabela's Inc CMN", ticker=None) == "Cabela's Inc"
    assert resolve_corporate_entity("Description", ticker=None) is None
    assert resolve_corporate_entity(None, ticker=None) is None
    assert resolve_corporate_entity(None, ticker="UNKNOWN_CUSTOM_TICKER") is None


def test_link_asset_entity():
    sym, entity = link_asset_entity("Apple Inc. (AAPL)")
    assert sym == "AAPL"
    assert entity == "Apple Inc."

    sym, entity = link_asset_entity("Municipal bond", ticker="--")
    assert sym is None
    assert entity is None

    sym, entity = link_asset_entity("Walmart Inc.", ticker=None)
    assert sym == "WMT"
    assert entity == "Walmart Inc."


def test_link_dataframe_entities():
    # Empty DataFrame without columns
    empty = link_dataframe_entities(pd.DataFrame())
    assert "ticker" in empty.columns
    assert "corporate_entity" in empty.columns

    # Empty DataFrame with columns
    empty_with_cols = link_dataframe_entities(pd.DataFrame(columns=["ticker", "corporate_entity"]))
    assert empty_with_cols.empty

    # DataFrame with missing columns
    df_desc_only = pd.DataFrame([{"asset_description": "Apple Inc."}])
    res_desc_only = link_dataframe_entities(df_desc_only)
    assert res_desc_only.iloc[0]["ticker"] == "AAPL"
    assert res_desc_only.iloc[0]["corporate_entity"] == "Apple Inc."

    df_ticker_only = pd.DataFrame([{"ticker": "MSFT"}])
    res_ticker_only = link_dataframe_entities(df_ticker_only)
    assert res_ticker_only.iloc[0]["ticker"] == "MSFT"
    assert res_ticker_only.iloc[0]["corporate_entity"] == "Microsoft Corporation"

    # Full mixed DataFrame
    df = pd.DataFrame(
        [
            {"ticker": "aapl", "asset_description": "Apple Inc.", "asset_type": "Stock"},
            {"ticker": None, "asset_description": "Walmart Inc.", "asset_type": "Stock"},
            {"ticker": "--", "asset_description": "Municipal bond", "asset_type": "Bond"},
            {
                "ticker": None,
                "asset_description": "Common Stock - Amazon.com",
                "asset_type": "Stock",
            },
        ]
    )
    res = link_dataframe_entities(df)
    assert res.iloc[0]["ticker"] == "AAPL"
    assert res.iloc[0]["corporate_entity"] == "Apple Inc."
    assert res.iloc[1]["ticker"] == "WMT"
    assert res.iloc[1]["corporate_entity"] == "Walmart Inc."
    assert res.iloc[2]["ticker"] is None
    assert res.iloc[2]["corporate_entity"] is None
    assert res.iloc[3]["ticker"] == "AMZN"
    assert res.iloc[3]["corporate_entity"] == "Amazon.com, Inc."

    # Idempotence: running link_dataframe_entities again returns identical results
    res_twice = link_dataframe_entities(res)
    pd.testing.assert_frame_equal(res, res_twice)


def test_merge_to_csv_with_entity_linking(tmp_path):
    out_file = tmp_path / "merged_output.csv"
    senate = pd.DataFrame(
        [
            {
                "chamber": "Senate",
                "legislator_name": "Wyden Ron",
                "transaction_date": "2023-01-01",
                "ticker": None,
                "asset_description": "The Boeing Company",
                "transaction_type": "Purchase",
                "owner": "Self",
            }
        ]
    )
    house = pd.DataFrame(
        [
            {
                "chamber": "House",
                "legislator_name": "Pelosi Nancy",
                "transaction_date": "2023-01-02",
                "ticker": "AAPL",
                "asset_description": "Apple Inc.",
                "transaction_type": "Sale",
                "owner": "Spouse",
            }
        ]
    )

    merged = merge_to_csv(senate_df=senate, house_df=house, output_path=str(out_file))
    assert len(merged) == 2
    assert list(merged.columns) == COLUMN_ORDER
    assert merged.iloc[0]["ticker"] == "BA"
    assert merged.iloc[0]["corporate_entity"] == "The Boeing Company"
    assert merged.iloc[1]["ticker"] == "AAPL"
    assert merged.iloc[1]["corporate_entity"] == "Apple Inc."
    assert out_file.exists()
