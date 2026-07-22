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

def test_playwright_missing_error():
    with patch("pipeline.scrapers.house_official.HAS_PLAYWRIGHT", False):
        with pytest.raises(RuntimeError):
            HouseOfficialScraper()
            
    with patch("pipeline.scrapers.senate_official.has_playwright", False):
        with pytest.raises(RuntimeError):
            SenateOfficialScraper()

def test_house_pdf_parser_edge_cases():
    assert parse_house_pdf("http://example.com/file.txt") == []

    with patch("pipeline.scrapers.house_pdf_parser.requests.get", side_effect=Exception("HTTP Error")):
        assert parse_house_pdf("http://example.com/file.pdf") == []

    with patch("pipeline.scrapers.house_pdf_parser.requests.get") as mock_get:
        mock_get.return_value.content = b"pdf_data"
        with patch("pipeline.scrapers.house_pdf_parser.pdfplumber.open", side_effect=Exception("PDF Parse Error")):
            assert parse_house_pdf("http://example.com/file.pdf") == []

    # Table with missing headers / empty rows / no table
    with patch("pipeline.scrapers.house_pdf_parser.requests.get") as mock_get:
        mock_get.return_value.content = b"pdf_data"
        mock_pdf = MagicMock()
        mock_page1 = MagicMock()
        mock_page1.extract_table.return_value = None  # Table is None
        
        mock_page2 = MagicMock()
        mock_page2.extract_table.return_value = [
            ["Unrelated", "Header"],  # Missing asset/amount in headers
            ["val1", "val2"]
        ]

        mock_page3 = MagicMock()
        mock_page3.extract_table.return_value = [
            ["Asset", "Date"],  # Missing amount in col_map
            ["val1", "val2"]
        ]

        mock_page4 = MagicMock()
        mock_page4.extract_table.return_value = [
            ["Asset", "Amount", "Date"],
            [None, None, None]  # empty row
        ]

        mock_pdf.pages = [mock_page1, mock_page2, mock_page3, mock_page4]
        with patch("pipeline.scrapers.house_pdf_parser.pdfplumber.open") as mock_open:
            mock_open.return_value.__enter__.return_value = mock_pdf
            assert parse_house_pdf("http://example.com/file.pdf") == []

@patch('pipeline.scrapers.house_official.sync_playwright')
def test_house_official_scraper_dom_branches(mock_pw):
    mock_playwright = MagicMock()
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()
    
    mock_pw.return_value.start.return_value = mock_playwright
    mock_playwright.chromium.launch.return_value = mock_browser
    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page

    # Test search_tab not visible
    search_tab = MagicMock()
    search_tab.is_visible.return_value = False
    mock_page.query_selector.side_effect = lambda sel: search_tab if sel == 'a[href="#Search"]' else MagicMock()
    
    scraper = HouseOfficialScraper()
    scraper._page = mock_page
    scraper._ensure_search_page()
    search_tab.click.assert_called_once()

    # Test empty search results
    empty_cell = MagicMock()
    empty_cell.inner_text.return_value = "No activities found"
    mock_page.query_selector.side_effect = lambda sel: empty_cell if sel == "td.dataTables_empty" else None
    assert scraper._search_year("2023") == []

    # Test missing table
    mock_page.query_selector.side_effect = lambda sel: None
    assert scraper._search_year("2023") == []

    # Test href missing / pdf fallback
    mock_page.evaluate.return_value = [
        {"name": "No Href", "href": ""},
        {"name": "With Href", "filing_type": "periodic transaction report", "href": "doc.pdf"}
    ]
    mock_page.query_selector.side_effect = lambda sel: MagicMock()
    with patch("pipeline.scrapers.house_official.parse_house_pdf", return_value=[]):
        res = scraper._search_year("2023")
        assert len(res) == 1
        assert res[0]["legislator_name"] == "With Href"

    # Test scrape empty dataframe
    with patch.object(scraper, "_search_year", return_value=[]):
        df = scraper.scrape(start_year=2023, end_year=2023)
        assert df.empty

@patch('pipeline.scrapers.senate_official.sync_playwright')
def test_senate_official_scraper_dom_branches(mock_pw):
    mock_playwright = MagicMock()
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()
    
    mock_pw.return_value.start.return_value = mock_playwright
    mock_playwright.chromium.launch.return_value = mock_browser
    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page

    scraper = SenateOfficialScraper()
    scraper._page = mock_page

    # Test accept agreement form
    mock_form = MagicMock()
    mock_page.query_selector.side_effect = lambda sel: mock_form if sel == "#agreement_form" else None
    scraper._accept_agreement()
    mock_page.click.assert_called_with("#agree_statement")

    # Test search_ptr_by_date_range no results alert
    alert_info = MagicMock()
    alert_info.inner_text.return_value = "No results"
    mock_page.query_selector.side_effect = lambda sel: alert_info if sel == ".alert-info" else MagicMock()
    assert scraper._search_ptr_by_date_range("01/01/2023", "12/31/2023") == []

    # Test search_ptr_by_date_range returning results
    mock_page.query_selector.side_effect = lambda sel: None
    with patch.object(scraper, "_extract_search_page_results", return_value=[{"report_url": "http://ptr"}]):
        res = scraper._search_ptr_by_date_range("01/01/2023", "12/31/2023")
        assert len(res) == 1

    # Test extract_search_page_results pagination & cell filtering (cell without link & non-ptr link & pagination)
    row1 = MagicMock()
    cell1 = MagicMock(); cell1.inner_text.return_value = "FirstName"
    cell2 = MagicMock(); cell2.inner_text.return_value = "LastName"
    cell3 = MagicMock(); cell3.inner_text.return_value = "Office"
    cell4 = MagicMock(); cell4.inner_text.return_value = "PTR"
    link = MagicMock(); link.get_attribute.return_value = "/ptr/123"
    cell4.query_selector.return_value = link
    cell5 = MagicMock(); cell5.inner_text.return_value = "01/01/2023"
    row1.query_selector_all.return_value = [cell1, cell2, cell3, cell4, cell5]

    row_short = MagicMock()
    row_short.query_selector_all.return_value = [cell1]  # < 5 cells

    row_no_link = MagicMock()
    c1 = MagicMock(); c1.inner_text.return_value = "A"
    c2 = MagicMock(); c2.inner_text.return_value = "B"
    c3 = MagicMock(); c3.inner_text.return_value = "C"
    c4 = MagicMock(); c4.inner_text.return_value = "D"; c4.query_selector.return_value = None
    c5 = MagicMock(); c5.inner_text.return_value = "E"
    row_no_link.query_selector_all.return_value = [c1, c2, c3, c4, c5]

    row_non_ptr = MagicMock()
    c4_non_ptr = MagicMock(); c4_non_ptr.inner_text.return_value = "Annual"
    link_non_ptr = MagicMock(); link_non_ptr.get_attribute.return_value = "/annual/123"
    c4_non_ptr.query_selector.return_value = link_non_ptr
    row_non_ptr.query_selector_all.return_value = [c1, c2, c3, c4_non_ptr, c5]

    next_btn = MagicMock()
    page_call_count = [0]
    def mock_qs_all(sel):
        if page_call_count[0] == 0:
            page_call_count[0] += 1
            return [row1, row_short, row_no_link, row_non_ptr]
        return []

    mock_page.query_selector_all.side_effect = mock_qs_all
    def mock_qs(sel):
        if sel == ".paginate_button.next:not(.disabled)" and page_call_count[0] == 1:
            page_call_count[0] += 1
            return next_btn
        return None
    mock_page.query_selector.side_effect = mock_qs

    results = scraper._extract_search_page_results()
    assert len(results) == 1
    next_btn.click.assert_called_once()

    # Test scrape_ptr_transactions missing card / table
    mock_page.query_selector.side_effect = lambda sel: None
    assert scraper._scrape_ptr_transactions("http://link", "Name", "Date") == []

    card = MagicMock()
    card.query_selector.return_value = None  # No table
    mock_page.query_selector.side_effect = lambda sel: card if sel == "section.card" else None
    assert scraper._scrape_ptr_transactions("http://link", "Name", "Date") == []

    # Test scrape_ptr_transactions table parsing
    card = MagicMock()
    table = MagicMock()
    th1 = MagicMock(); th1.inner_text.return_value = "Asset"
    th2 = MagicMock(); th2.inner_text.return_value = "Type"
    th3 = MagicMock(); th3.inner_text.return_value = "Transaction Date"
    table.query_selector_all.side_effect = lambda sel: [th1, th2, th3] if sel == "thead th" else [tr1]

    tr1 = MagicMock()
    td1 = MagicMock(); td1.inner_text.return_value = "AAPL"
    td2 = MagicMock(); td2.inner_text.return_value = "Purchase"
    td3 = MagicMock(); td3.inner_text.return_value = "01/01/2023"
    tr1.query_selector_all.return_value = [td1, td2, td3]

    card.query_selector.return_value = table
    mock_page.query_selector.side_effect = lambda sel: card if sel == "section.card" else None
    
    rows = scraper._scrape_ptr_transactions("http://link", "Senator Wyden", "01/05/2023")
    assert len(rows) == 1
    assert rows[0]["ticker"] == "AAPL"

    # Test scrape empty results
    with patch.object(scraper, "_search_ptr_by_date_range", return_value=[{"report_url": ""}]):
        assert scraper.scrape(2023, 2023).empty

    with patch.object(scraper, "_search_ptr_by_date_range", return_value=[{"report_url": "http://link"}]):
        with patch.object(scraper, "_scrape_ptr_transactions", side_effect=Exception("scrape fail")):
            assert scraper.scrape(2023, 2023).empty

@patch('pipeline.scrapers.house_official.sync_playwright')
def test_house_official_pdf_exception_and_columns(mock_pw):
    mock_playwright = MagicMock()
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()
    
    mock_pw.return_value.start.return_value = mock_playwright
    mock_playwright.chromium.launch.return_value = mock_browser
    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page

    scraper = HouseOfficialScraper()
    scraper._page = mock_page

    # PDF exception branch
    mock_page.evaluate.return_value = [
        {"name": "Smith", "office": "NY", "year": "2023", "filing_type": "periodic transaction report", "href": "doc.pdf"}
    ]
    mock_page.query_selector.side_effect = lambda sel: MagicMock()
    with patch("pipeline.scrapers.house_official.parse_house_pdf", side_effect=Exception("PDF error")):
        res = scraper._search_year("2023")
        assert len(res) == 1
        assert res[0]["legislator_name"] == "Smith"

    # Column missing branch in scrape()
    with patch.object(scraper, "_search_year", return_value=[{"name": "Smith"}]):
        df = scraper.scrape(2023, 2023)
        assert "transaction_year" in df.columns
