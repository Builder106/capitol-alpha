from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_CSV = DATA_DIR / "legislative_trades.csv"
MIN_YEAR = 2020
MAX_YEAR = 2026

DATA_DIR.mkdir(parents=True, exist_ok=True)
