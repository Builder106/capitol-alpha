import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from pipeline.scrapers.house_official import HouseOfficialScraper, _parse_date, _normalize_house_disclosure_row
from pipeline.scrapers.senate_official import SenateOfficialScraper, _parse_date as senate_parse_date, _normalize_senate_row
from pipeline.scrapers.house_pdf_parser import parse_house_pdf

def test_house_parse_date():
    assert _parse_date(None) is None
    assert _parse_date("2024") == 2024
    assert _parse_date("01/15/2023") == 2023
    assert _parse_date("2022-05-12") == 2022
    assert _parse_date("invalid") is None

def test_senate_parse_date():
    assert senate_parse_date(None) is None
    assert senate_parse_date("01/15/2023") == 2023
    assert senate_parse_date("invalid") is None

def test_normalize_house_row():
    row = _normalize_house_disclosure_row("Smith", "NY01", "2023", "PTR", "http://pdf")
    assert row["chamber"] == "House"
    assert row["legislator_name"] == "Smith"
    assert row["transaction_year"] == 2023

def test_normalize_senate_row():
    raw = {
        "ticker": "AAPL",
        "asset_name": "Apple Inc",
        "asset_type": "Stock",
        "transaction_type": "Purchase",
        "transaction_date": "01/01/2023",
        "amount": "$1 - $15,000",
        "comment": ""
    }
    row = _normalize_senate_row(
        raw=raw,
        legislator_name="Smith",
        disclosure_date="01/05/2023",
        ptr_link="http://link",
    )
    assert row["chamber"] == "Senate"
    assert row["legislator_name"] == "Smith"

@patch('pipeline.scrapers.house_pdf_parser.pdfplumber')
@patch('pipeline.scrapers.house_pdf_parser.requests')
def test_parse_house_pdf(mock_req, mock_plumber):
    # Mock requests.get
    mock_resp = MagicMock()
    mock_resp.content = b"pdfcontent"
    mock_req.get.return_value = mock_resp

    # Mock pdfplumber.open
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    
    # Return table that mimics a parsed house pdf
    mock_page.extract_table.return_value = [
        ["Asset", "Owner", "Date", "Notification Date", "Amount", "Type"], # Should be skipped
        ["Apple Inc (AAPL)", "Self", "01/01/2023", "01/05/2023", "$1,001 - $15,000", "P"],
        ["Some Invalid Row"],
        ["Microsoft", "Spouse", "invalid date", "invalid date", "$1 - $5", "S (partial)"],
    ]
    mock_pdf.pages = [mock_page]
    mock_plumber.open.return_value.__enter__.return_value = mock_pdf

    res = parse_house_pdf("http://fake.pdf")
    assert len(res) == 3
    assert res[0]["ticker"] == "AAPL"
    assert res[0]["transaction_date"] == "01/01/2023"
    assert res[0]["amount_range"] == "$1,001 - $15,000"
    
    assert res[2]["ticker"] is None
    assert res[2]["transaction_date"] == "invalid date"

@patch('pipeline.scrapers.house_official.sync_playwright')
@patch('pipeline.scrapers.house_official.parse_house_pdf')
def test_house_scraper(mock_parse_pdf, mock_pw):
    mock_parse_pdf.return_value = [{"ticker": "AAPL", "transaction_type": "Purchase"}]

    mock_playwright = MagicMock()
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()
    
    mock_pw.return_value.start.return_value = mock_playwright
    mock_playwright.chromium.launch.return_value = mock_browser
    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page

    mock_page.evaluate.return_value = [
        {"name": "Smith", "office": "NY", "year": "2023", "filing_type": "PTR", "href": "/fake.pdf"},
        {"name": "Doe", "office": "TX", "year": "2023", "filing_type": "Annual", "href": "fake2.pdf"}
    ]

    with HouseOfficialScraper() as scraper:
        df = scraper.scrape(start_year=2023, end_year=2023)
        assert len(df) > 0
        assert df.iloc[0]["legislator_name"] == "Smith"

    # Error handling test
    mock_page.evaluate.side_effect = Exception("evaluate failed")
    with HouseOfficialScraper() as scraper:
        df2 = scraper.scrape(start_year=2023, end_year=2023)
        assert df2.empty

@patch('pipeline.scrapers.senate_official.SenateOfficialScraper._search_ptr_by_date_range')
@patch('pipeline.scrapers.senate_official.SenateOfficialScraper._extract_search_page_results')
@patch('pipeline.scrapers.senate_official.SenateOfficialScraper._scrape_ptr_transactions')
@patch('pipeline.scrapers.senate_official.SenateOfficialScraper._accept_agreement')
@patch('pipeline.scrapers.senate_official.sync_playwright')
def test_senate_scraper(mock_pw, mock_accept, mock_scrape_ptr, mock_extract_search, mock_search_ptr):
    mock_playwright = MagicMock()
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()
    
    mock_pw.return_value.start.return_value = mock_playwright
    mock_playwright.chromium.launch.return_value = mock_browser
    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page

    mock_search_ptr.side_effect = [
        [
            {"first_name": "Smith", "last_name": "Senator", "office": "Senator", "date": "01/05/2023", "report_type": "PTR", "report_url": "fake.html"},
            {"first_name": "Doe", "last_name": "Senator", "office": "Senator", "date": "01/05/2023", "report_type": "Annual", "report_url": "fake2.html"}
        ]
    ] + [[]] * 11 # 11 empty months
    
    mock_scrape_ptr.return_value = [
        {"asset": "Apple Inc", "ticker": "AAPL", "asset_type": "Stock", "transaction_type": "Purchase", "transaction_date": "01/01/2023", "disclosure_date": "01/05/2023", "amount": "$1,001 - $15,000", "owner": "Self", "comment": ""}
    ]

    with SenateOfficialScraper() as scraper:
        # Override these since we mocked the sync methods but scrape loops over dates
        df = scraper.scrape(start_year=2023, end_year=2023)
        assert not df.empty
        assert "AAPL" in df["ticker"].values
