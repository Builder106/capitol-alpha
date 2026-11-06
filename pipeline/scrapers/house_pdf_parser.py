import re
from datetime import datetime
from io import BytesIO
from typing import TypedDict

import pdfplumber
import requests

from ..ingestion import IngestionError, retry


class HousePdfTransaction(TypedDict):
    asset_description: str
    ticker: str | None
    transaction_type: str
    transaction_date: str
    disclosure_date: str
    amount_range: str
    owner: str
    ptr_link: str


def parse_house_pdf(pdf_url: str) -> list[HousePdfTransaction]:
    """
    Downloads and parses a House Financial Disclosure or PTR PDF.
    Extracts transaction tables and maps them to row dictionaries.
    """
    if not pdf_url.lower().endswith(".pdf"):
        return []

    def download() -> bytes:
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()
        return response.content

    content = retry(download, f"Download House PTR {pdf_url}")

    transactions: list[HousePdfTransaction] = []

    try:
        with pdfplumber.open(BytesIO(content)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    if not table:
                        continue

                    # Usually House electronic PTR tables have headers like:
                    # 'ID', 'Owner', 'Asset', 'Transaction Type', 'Date', 'Notification Date', 'Amount', 'Cap. Gains > $200?'

                    # Try to identify if this is a transaction table
                    headers = [
                        str(cell or "").lower().replace("\n", " ").strip() for cell in table[0]
                    ]

                    # Minimal check for PTR columns
                    if not any(
                        header in "\t".join(headers)
                        for header in ["asset", "transaction type", "amount", "date"]
                    ):
                        continue

                    # Find column indices
                    col_map: dict[str, int] = {}
                    for i, h in enumerate(headers):
                        if "owner" in h:
                            col_map["owner"] = i
                        elif "asset" in h:
                            col_map["asset"] = i
                        elif "transaction type" in h or "type" in h:
                            col_map["type"] = i
                        elif "notification" in h:
                            col_map["notification_date"] = i
                        elif "date" in h:
                            col_map["date"] = i
                        elif "amount" in h:
                            col_map["amount"] = i

                    # If we can't find core columns, skip this table
                    if "asset" not in col_map or "amount" not in col_map:
                        continue

                    for row in table[1:]:
                        if not any(row):  # Skip empty rows
                            continue

                        # Extract basic info, with safety bounds
                        def get_col(name: str) -> str:
                            if name in col_map and col_map[name] < len(row) and row[col_map[name]]:
                                return str(row[col_map[name]]).replace("\n", " ").strip()
                            return ""

                        asset_description = get_col("asset")
                        if not asset_description or not get_col("amount"):
                            raise ValueError("Incomplete transaction row")
                        # Sometimes ticker is in parenthesis in the asset name: 'Apple Inc. (AAPL)'
                        ticker = None
                        ticker_match = re.search(r"\(([A-Z]+)\)", asset_description)
                        if ticker_match:
                            ticker = ticker_match.group(1)

                        transaction_date = get_col("date")
                        notification_date = get_col("notification_date")
                        datetime.strptime(transaction_date, "%m/%d/%Y")

                        transactions.append(
                            {
                                "asset_description": asset_description,
                                "ticker": ticker,
                                "transaction_type": get_col("type"),
                                "transaction_date": transaction_date,
                                "disclosure_date": notification_date
                                if notification_date
                                else transaction_date,
                                "amount_range": get_col("amount"),
                                "owner": get_col("owner"),
                                "ptr_link": pdf_url,
                            }
                        )
    except Exception as exc:
        raise IngestionError(f"Failed to parse House PTR {pdf_url}") from exc

    if not transactions:
        raise IngestionError(f"No transaction tables in House PTR {pdf_url}; OCR may be required")

    return transactions
