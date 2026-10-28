from pathlib import Path

SENATE_RAW_URL = "https://raw.githubusercontent.com/timothycarambat/senate-stock-watcher-data/master/aggregate/all_transactions.json"
SENATE_S3_URL = (
    "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json"
)
HOUSE_S3_URL = (
    "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"
)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_CSV = DATA_DIR / "legislative_trades.csv"
MIN_YEAR = 2020
MAX_YEAR = 2026

DATA_DIR.mkdir(parents=True, exist_ok=True)
