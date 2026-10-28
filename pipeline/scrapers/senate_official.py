from datetime import datetime
from types import TracebackType
from typing import TypedDict

import pandas as pd

try:
    from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

    has_playwright = True
except ImportError:
    sync_playwright = None  # type: ignore[assignment]
    has_playwright = False
    Playwright = object  # type: ignore[assignment, misc]
    Browser = object  # type: ignore[assignment, misc]
    BrowserContext = object  # type: ignore[assignment, misc]
    Page = object  # type: ignore[assignment, misc]

from ..config import MIN_YEAR, MAX_YEAR

SENATE_BASE = "https://efdsearch.senate.gov"
SENATE_SEARCH = f"{SENATE_BASE}/search/"
PTR_REPORT_TYPE_VALUE = "11"


class SenateTransaction(TypedDict):
    chamber: str
    legislator_name: str
    disclosure_date: str
    transaction_date: str
    ticker: str | None
    asset_description: str | None
    asset_type: str | None
    transaction_type: str | None
    amount_range: str | None
    owner: str | None
    ptr_link: str
    comment: str | None


class SenateSearchResult(TypedDict):
    first_name: str
    last_name: str
    office: str
    report_type: str
    date: str
    report_url: str


def _parse_date(s: str) -> int | None:
    if not s:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%B %d, %Y"):
        try:
            return datetime.strptime(s.strip(), fmt).year
        except ValueError:
            continue
    return None


def _normalize_senate_row(
    raw: dict[str, str],
    legislator_name: str,
    disclosure_date: str,
    ptr_link: str,
) -> SenateTransaction:
    return {
        "chamber": "Senate",
        "legislator_name": legislator_name,
        "disclosure_date": disclosure_date,
        "transaction_date": raw.get("transaction_date") or raw.get("transaction_date_date") or "",
        "ticker": (raw.get("ticker") or raw.get("asset") or "").strip() or None,
        "asset_description": raw.get("asset_name")
        or raw.get("asset_description")
        or raw.get("asset"),
        "asset_type": raw.get("asset_type"),
        "transaction_type": raw.get("type") or raw.get("transaction_type"),
        "amount_range": raw.get("amount") or raw.get("amount_range"),
        "owner": raw.get("owner"),
        "ptr_link": ptr_link,
        "comment": raw.get("comment"),
    }


class SenateOfficialScraper:
    def __init__(self, headless: bool = True) -> None:
        if not has_playwright:
            raise RuntimeError(
                "Playwright is required. Install with: pip install playwright && playwright install"
            )
        self._headless = headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._agreement_accepted = False

    def __enter__(self) -> "SenateOfficialScraper":
        self._playwright = sync_playwright().start()  # type: ignore[misc]
        self._browser = self._playwright.chromium.launch(
            headless=self._headless, args=["--disable-dev-shm-usage"]
        )
        self._context = self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        )
        self._page = self._context.new_page()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._page:
            self._page.close()
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def _accept_agreement(self) -> None:
        self._page.goto(SENATE_SEARCH)
        self._page.wait_for_load_state("networkidle")
        form = self._page.query_selector("#agreement_form")
        if form:
            self._page.click("#agree_statement")
            self._page.wait_for_url(SENATE_SEARCH, timeout=10000)
        self._agreement_accepted = True

    def _search_ptr_by_date_range(self, start_date: str, end_date: str) -> list[SenateSearchResult]:
        self._page.wait_for_selector("#searchForm", state="visible", timeout=10000)
        self._page.fill("#fromDate", start_date)
        self._page.fill("#toDate", end_date)
        self._page.check(".senator_filer")
        self._page.evaluate(
            "() => { document.querySelectorAll('input[name=\"report_type\"]').forEach(el => el.checked = false); }"
        )
        ptr_cb = self._page.query_selector(
            f'input[name="report_type"][value="{PTR_REPORT_TYPE_VALUE}"]'
        )
        if ptr_cb:
            ptr_cb.check()
        self._page.click("button[type='submit']")
        self._page.wait_for_selector("#filedReports_processing", state="visible", timeout=5000)
        self._page.wait_for_selector("#filedReports_processing", state="hidden", timeout=30000)
        self._page.wait_for_selector(
            "#filedReports tbody tr, .alert-info", state="visible", timeout=10000
        )
        if self._page.query_selector(".alert-info") and "No results" in (
            self._page.query_selector(".alert-info").inner_text() or ""
        ):
            return []
        return self._extract_search_page_results()

    def _extract_search_page_results(self) -> list[SenateSearchResult]:
        results: list[SenateSearchResult] = []
        while True:
            rows = self._page.query_selector_all("#filedReports tbody tr")
            for row in rows:
                cells = row.query_selector_all("td")
                if len(cells) < 5:
                    continue
                link = cells[3].query_selector("a")
                if not link:
                    continue
                href = link.get_attribute("href")
                if not href or "ptr" not in href.lower():
                    continue
                if href.startswith("/"):
                    href = f"{SENATE_BASE}{href}"
                results.append(
                    {
                        "first_name": cells[0].inner_text().strip(),
                        "last_name": cells[1].inner_text().strip(),
                        "office": cells[2].inner_text().strip(),
                        "report_type": cells[3].inner_text().strip(),
                        "date": cells[4].inner_text().strip(),
                        "report_url": href,
                    }
                )
            next_btn = self._page.query_selector(".paginate_button.next:not(.disabled)")
            if not next_btn:
                break
            next_btn.click()
            self._page.wait_for_selector("#filedReports_processing", state="hidden", timeout=15000)
        return results

    def _scrape_ptr_transactions(
        self, report_url: str, legislator_name: str, disclosure_date: str
    ) -> list[SenateTransaction]:
        self._page.goto(report_url)
        self._page.wait_for_load_state("networkidle")
        section = self._page.query_selector("section.card")
        if not section:
            return []
        table = section.query_selector("table")
        if not table:
            return []
        headers = [
            th.inner_text().strip().lower().replace(" ", "_")
            for th in table.query_selector_all("thead th")
        ]
        rows_data: list[dict[str, str]] = []
        for tr in table.query_selector_all("tbody tr"):
            cells = tr.query_selector_all("td")
            row: dict[str, str] = {}
            for i, h in enumerate(headers):
                if i < len(cells):
                    row[h] = cells[i].inner_text().strip()
            if row:
                rows_data.append(row)
        return [
            _normalize_senate_row(r, legislator_name, disclosure_date, report_url)
            for r in rows_data
        ]

    def scrape(self, start_year: int | None = None, end_year: int | None = None) -> pd.DataFrame:
        start_year = start_year or MIN_YEAR
        end_year = end_year or MAX_YEAR
        if not self._agreement_accepted:
            self._accept_agreement()
        start_date = f"01/01/{start_year}"
        end_date = f"12/31/{end_year}"
        ptr_list = self._search_ptr_by_date_range(start_date, end_date)
        all_rows: list[SenateTransaction] = []
        for item in ptr_list:
            name = f"{item.get('first_name', '')} {item.get('last_name', '')}".strip()
            date = item.get("date") or ""
            url = item.get("report_url", "")
            if not url:
                continue
            try:
                trades = self._scrape_ptr_transactions(url, name, date)
                for t in trades:
                    y = _parse_date(t.get("transaction_date") or "")
                    if y is not None and start_year <= y <= end_year:
                        all_rows.append(t)
            except Exception:
                continue
        if not all_rows:
            return pd.DataFrame()
        df = pd.DataFrame(all_rows)
        df["transaction_year"] = df["transaction_date"].apply(_parse_date)  # type: ignore[arg-type]
        df["disclosure_year"] = df["disclosure_date"].apply(_parse_date)  # type: ignore[arg-type]
        return df
