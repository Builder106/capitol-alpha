from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from xml.etree import ElementTree

import pandas as pd
import pytest
import requests

from pipeline.ingestion import IngestionError, publish_csvs, retry
from pipeline.merge_to_csv import COLUMN_ORDER, merge_to_csv
from pipeline.run_pipeline import run
from pipeline.scrapers.house_official import HouseOfficialScraper
from pipeline.scrapers.house_pdf_parser import parse_house_pdf
from pipeline.scrapers.senate_official import SenateOfficialScraper

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def no_retry_sleep():
    with patch("pipeline.ingestion.sleep") as sleeping:
        yield sleeping


def test_retry_recovers_and_reports_exhaustion(no_retry_sleep):
    source = Mock(side_effect=[TimeoutError("temporary"), 42])
    assert retry(source, "PTR") == 42
    no_retry_sleep.assert_called_once_with(1)
    source = Mock(side_effect=TimeoutError("unavailable"))
    with pytest.raises(IngestionError, match="PTR failed after 3 attempts") as failure:
        retry(source, "PTR")
    assert isinstance(failure.value.__cause__, TimeoutError)
    assert source.call_count == 3
    nested = Mock(side_effect=IngestionError("already exhausted"))
    with pytest.raises(IngestionError, match="already exhausted"):
        retry(nested, "outer")
    assert nested.call_count == 1


def test_house_pdf_download_retries_and_parses_every_table():
    response = Mock(content=(FIXTURES / "house_ptr.pdf").read_bytes())
    with patch(
        "pipeline.scrapers.house_pdf_parser.requests.get",
        side_effect=[requests.Timeout("transient"), response],
    ) as download:
        rows = parse_house_pdf("https://disclosures-clerk.house.gov/ptr/2023/fixture.pdf")
    assert download.call_count == 2
    assert len(rows) == 3
    assert rows[0]["ticker"] == "AAPL"
    assert rows[0]["transaction_date"] == "12/30/2022"
    assert rows[0]["amount_range"] == "$1,001 - $15,000"
    assert rows[1]["transaction_type"] == "S (partial)"
    assert rows[2]["asset_description"] == "Municipal bond"
    assert rows[2]["ticker"] is None


def senate_fixture_rows():
    """Feed cached HTML cells through the actual Senate table parser."""
    root = ElementTree.fromstring((FIXTURES / "senate_ptr.html").read_text())
    table = MagicMock()

    def cell(node):
        result = Mock()
        result.inner_text.return_value = node.text or ""
        return result

    header_cells = [cell(node) for node in root.findall("table/thead/tr/th")]
    body_rows = []
    for node in root.findall("table/tbody/tr"):
        row = Mock()
        row.query_selector_all.return_value = [cell(td) for td in node.findall("td")]
        body_rows.append(row)
    table.query_selector_all.side_effect = lambda selector: (
        header_cells if selector == "thead th" else body_rows
    )
    section = Mock()
    section.query_selector.return_value = table
    scraper = SenateOfficialScraper()
    scraper._page = Mock()
    scraper._page.query_selector.return_value = section
    return scraper._scrape_ptr_transactions(
        "https://efdsearch.senate.gov/search/view/ptr/fixture/", "Test Senator", "01/10/2023"
    )


def test_fixture_ingestion_has_stable_schema_ranges_and_idempotence(tmp_path):
    with patch(
        "pipeline.scrapers.house_pdf_parser.requests.get",
        return_value=Mock(content=(FIXTURES / "house_ptr.pdf").read_bytes()),
    ):
        house = pd.DataFrame(parse_house_pdf("https://example.com/ptr.pdf"))
    house["chamber"] = "House"
    house["legislator_name"] = "Test Representative"
    house["transaction_year"] = [2022, 2023, 2023]
    senate = pd.DataFrame(senate_fixture_rows())
    destination = tmp_path / "trades.csv"
    first = merge_to_csv(senate, house, destination)
    first_bytes = destination.read_bytes()
    second = merge_to_csv(pd.concat([senate, senate]), pd.concat([house, house]), destination)
    pd.testing.assert_frame_equal(first, second)
    assert first_bytes == destination.read_bytes()
    assert list(first.columns) == COLUMN_ORDER
    assert len(first) == 5
    assert first.iloc[0]["amount_min"] == 1001
    assert first.iloc[0]["amount_max"] == 15000
    assert first.iloc[0]["amount_avg"] == 8000.5
    assert first.iloc[1]["ticker"] is None
    assert first.iloc[1]["transaction_type"] == "Sale"
    assert first.iloc[2]["transaction_year"] == 2022
    assert first.iloc[3]["transaction_type"] == "Sale"


def test_missing_and_open_ended_amounts_do_not_become_point_estimates(tmp_path):
    rows = pd.DataFrame(senate_fixture_rows()[:1] * 3)
    rows["amount_range"] = [pd.NA, "$1,000,000+", "$1,001 - $15,000"]
    rows["amount_min"] = [None, None, 1001.0]
    merged = merge_to_csv(rows, pd.DataFrame(), tmp_path / "trades.csv")
    assert pd.isna(merged.iloc[0]["amount_min"])
    assert pd.isna(merged.iloc[0]["amount_avg"])
    assert merged.iloc[1]["amount_min"] == 1000000
    assert pd.isna(merged.iloc[1]["amount_max"])
    assert pd.isna(merged.iloc[1]["amount_avg"])
    assert merged.iloc[2]["amount_avg"] == 8000.5


@pytest.mark.parametrize("chamber", ["house", "senate"])
def test_invalid_year_range(chamber):
    scraper = HouseOfficialScraper() if chamber == "house" else SenateOfficialScraper()
    with pytest.raises(ValueError, match="start_year"):
        scraper.scrape(2024, 2023)


def test_house_requires_ptr_links_and_deduplicates_reports():
    scraper = HouseOfficialScraper()
    scraper._page = MagicMock()
    scraper._page.query_selector.return_value.inner_text.return_value = "Results"
    row = {"name": "Test", "filing_type": "PTR", "href": "https://example.com/test.pdf"}
    scraper._page.evaluate.return_value = [row, row]
    trade = {"transaction_date": "12/30/2022", "disclosure_date": "01/05/2023"}
    with patch("pipeline.scrapers.house_official.parse_house_pdf", return_value=[trade]) as parser:
        rows = scraper._search_year("2023")
    parser.assert_called_once_with(row["href"])
    assert len(rows) == 1
    assert rows[0]["transaction_year"] == 2022
    assert rows[0]["disclosure_year"] == 2023
    row["href"] = ""
    with pytest.raises(IngestionError, match="Missing House PTR URL"):
        scraper._search_year("2023")


def test_senate_deduplicates_reports_and_keeps_late_disclosures():
    scraper = SenateOfficialScraper()
    scraper._agreement_accepted = True
    item = {"report_url": "https://example.com/ptr/test", "date": "01/10/2023"}
    rows = senate_fixture_rows()
    with (
        patch.object(scraper, "_search_ptr_by_date_range", return_value=[item, item]),
        patch.object(scraper, "_scrape_ptr_transactions", return_value=rows) as report,
    ):
        frame = scraper.scrape(2023, 2023)
    assert len(frame) == 2
    assert frame.iloc[0]["transaction_year"] == 2022
    report.assert_called_once()


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [{"transaction_date": "bad date"}],
        [{"transaction_date": "01/01/2023"}],
        [{"transaction_date": "01/01/2023", "ticker": "AAPL"}],
    ],
)
def test_senate_malformed_or_empty_report_is_a_failure(rows):
    scraper = SenateOfficialScraper()
    scraper._agreement_accepted = True
    with (
        patch.object(scraper, "_search_ptr_by_date_range", return_value=[{"report_url": "ptr"}]),
        patch.object(scraper, "_scrape_ptr_transactions", return_value=rows) as report,
    ):
        with pytest.raises(IngestionError, match="Read Senate PTR"):
            scraper.scrape(2023, 2023)
    assert report.call_count == 3


def test_senate_stalled_pagination_fails():
    scraper = SenateOfficialScraper()
    scraper._page = MagicMock()
    scraper._page.query_selector_all.return_value = []
    with pytest.raises(IngestionError, match="pagination did not advance"):
        scraper._extract_search_page_results()


def test_pdf_incomplete_row_does_not_publish_partial_results():
    with (
        patch("pipeline.scrapers.house_pdf_parser.requests.get", return_value=Mock(content=b"pdf")),
        patch("pipeline.scrapers.house_pdf_parser.pdfplumber.open") as pdf,
    ):
        page = Mock()
        page.extract_tables.return_value = [
            [["Asset", "Amount", "Date"], ["Apple", "$1 - $5", "01/02/2023"], ["Broken"]]
        ]
        pdf.return_value.__enter__.return_value.pages = [page]
        with pytest.raises(IngestionError, match="Failed to parse House PTR"):
            parse_house_pdf("https://example.com/ptr.pdf")


def test_failed_csv_staging_keeps_all_previous_outputs(tmp_path):
    first, second = tmp_path / "senate.csv", tmp_path / "house.csv"
    first.write_text("previous senate")
    second.write_text("previous house")
    failing = Mock()
    failing.to_csv.side_effect = OSError("disk full")
    with pytest.raises(OSError, match="disk full"):
        publish_csvs({first: pd.DataFrame({"new": [1]}), second: failing})
    assert first.read_text() == "previous senate"
    assert second.read_text() == "previous house"
    assert set(tmp_path.iterdir()) == {first, second}


@pytest.mark.parametrize("failure", ["exception", "empty", "invalid"])
def test_failed_house_ingestion_keeps_senate_and_merged_outputs(tmp_path, failure):
    paths = [tmp_path / name for name in ("senate_trades.csv", "house_trades.csv", "trades.csv")]
    for path in paths:
        path.write_text("previous")
    senate_rows = pd.DataFrame(senate_fixture_rows())
    with (
        patch("pipeline.run_pipeline.DATA_DIR", tmp_path),
        patch("pipeline.run_pipeline.OUTPUT_CSV", paths[2]),
        patch("pipeline.scrapers.SenateOfficialScraper") as senate,
        patch("pipeline.scrapers.HouseOfficialScraper") as house,
    ):
        senate.return_value.__enter__.return_value.scrape.return_value = senate_rows
        house_scraper = house.return_value.__enter__.return_value
        if failure == "exception":
            house_scraper.scrape.side_effect = IngestionError("source failed")
        elif failure == "empty":
            house_scraper.scrape.return_value = pd.DataFrame()
        else:
            invalid = senate_rows.copy()
            invalid["transaction_date"] = None
            house_scraper.scrape.return_value = invalid
        with pytest.raises(IngestionError):
            run(use_official=True)
    assert all(path.read_text() == "previous" for path in paths)
    assert set(tmp_path.iterdir()) == set(paths)


def test_empty_senate_and_conflicting_modes_fail(tmp_path):
    with pytest.raises(ValueError, match="mutually exclusive"):
        run(senate_only=True, house_only=True)
    with (
        patch("pipeline.run_pipeline.DATA_DIR", tmp_path),
        patch("pipeline.scrapers.SenateOfficialScraper") as senate,
    ):
        senate.return_value.__enter__.return_value.scrape.return_value = pd.DataFrame()
        with pytest.raises(IngestionError, match="Senate returned no transactions"):
            run(use_official=True)
    assert not list(tmp_path.iterdir())


def test_senate_empty_search_is_distinct_from_a_failed_report():
    scraper = SenateOfficialScraper()
    scraper._agreement_accepted = True
    with patch.object(scraper, "_search_ptr_by_date_range", return_value=[]):
        assert scraper.scrape(2023, 2023).empty


def test_complete_official_run_publishes_both_chambers_idempotently(tmp_path):
    senate = pd.DataFrame(senate_fixture_rows())
    with patch(
        "pipeline.scrapers.house_pdf_parser.requests.get",
        return_value=Mock(content=(FIXTURES / "house_ptr.pdf").read_bytes()),
    ):
        house = pd.DataFrame(parse_house_pdf("https://example.com/ptr.pdf"))
    house["chamber"] = "House"
    house["legislator_name"] = "Test Representative"
    with (
        patch("pipeline.run_pipeline.DATA_DIR", tmp_path),
        patch("pipeline.run_pipeline.OUTPUT_CSV", tmp_path / "trades.csv"),
        patch("pipeline.scrapers.SenateOfficialScraper") as senate_scraper,
        patch("pipeline.scrapers.HouseOfficialScraper") as house_scraper,
    ):
        senate_scraper.return_value.__enter__.return_value.scrape.return_value = senate
        house_scraper.return_value.__enter__.return_value.scrape.return_value = house
        run(use_official=True)
        first = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
        run(use_official=True)
    assert first == {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    assert len(pd.read_csv(tmp_path / "senate_trades.csv")) == 2
    assert len(pd.read_csv(tmp_path / "house_trades.csv")) == 3
    combined = pd.read_csv(tmp_path / "trades.csv")
    assert len(combined) == 5
    assert list(combined.columns) == COLUMN_ORDER
    assert combined["amount_avg"].notna().all()
