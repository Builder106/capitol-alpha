"""Normalized Asset Entity Linking for Congressional Trade Disclosures.

Automated ticker symbol resolution and corporate entity mapping for raw PTR filings.
Handles messy disclosures, regex extraction, corporate name normalization,
and non-equity asset exclusion.
"""

from __future__ import annotations

import html
import re

import pandas as pd

# Ticker symbol validation: 1 to 5 uppercase ASCII letters, optionally followed by .X or -X for class shares
TICKER_RE = re.compile(r"^[A-Z]{1,5}([.-][A-Z]{1,2})?$")

# Disallowed words that look like tickers but are disclosure codes, asset types, or abbreviations
EXCLUDE_TICKER_TOKENS = frozenset(
    {
        "ST",
        "CS",
        "OP",
        "GS",
        "PS",
        "NA",
        "CMN",
        "LLC",
        "INC",
        "CORP",
        "CO",
        "LTD",
        "LP",
        "PLC",
        "REIT",
        "FD",
        "ETF",
        "FUND",
        "BOND",
        "NOTE",
        "MUNI",
        "GO",
        "USA",
        "NONE",
        "UNKNOWN",
        "TOTAL",
        "PDF",
        "PTR",
        "NEW",
        "SEE",
        "CLASS",
        "SHS",
        "USD",
    }
)

# Placeholder ticker representations in disclosure systems
PLACEHOLDER_TICKERS = frozenset({"--", "N/A", "NA", "NONE", "UNKNOWN", "NULL", "NAN"})

# Keywords identifying non-equity assets that should not resolve to equity tickers
NON_EQUITY_KEYWORDS = (
    "municipal bond",
    "muni bond",
    "muni",
    "revenue bond",
    "water fin auth",
    "dorm auth",
    "dormitory auth",
    "school dist",
    "general obligation",
    "public power",
    "tax revenue",
    "treasury bill",
    "treasury note",
    "treasury bond",
    "us treasury",
    "u.s. treasury",
    "t-bill",
    "rate/coupon:",
    "matures:",
    "coupon:",
    "maturity:",
    "corporate bond",
    "debenture",
    "senior notes",
    "secured debt",
    "promissory note",
    "fixed income",
    "cryptocurrency",
    "bitcoin",
    "ethereum",
    "crypto",
    "disclosed via scanned pdf",
    "see pdf",
    "view the pdf",
)

NON_EQUITY_ASSET_TYPES = frozenset(
    {
        "Municipal Security",
        "Corporate Bond",
        "Bond",
        "Non-Public Stock",
    }
)

# Regular expressions for extracting tickers embedded in asset descriptions
PAREN_TICKER_RE = re.compile(r"\(([A-Za-z]{1,5}(?:[.-][A-Za-z]{1,2})?)\)")
BRACKET_TICKER_RE = re.compile(r"\[([A-Za-z]{1,5}(?:[.-][A-Za-z]{1,2})?)\]")
PREFIX_TICKER_RE = re.compile(r"^([A-Za-z]{1,5})\s*[-:]\s+")
LABEL_TICKER_RE = re.compile(r"(?i)(?:ticker|symbol)[:\s]+([A-Za-z]{1,5}(?:[.-][A-Za-z]{1,2})?)")
HTML_TAG_RE = re.compile(r"<[^>]+>")

# Known high-frequency Congressional trading tickers mapped to canonical corporate entities
CANONICAL_TICKER_TO_ENTITY: dict[str, str] = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "AMZN": "Amazon.com, Inc.",
    "GOOGL": "Alphabet Inc.",
    "GOOG": "Alphabet Inc.",
    "NVDA": "NVIDIA Corporation",
    "META": "Meta Platforms, Inc.",
    "TSLA": "Tesla, Inc.",
    "BRK.A": "Berkshire Hathaway Inc.",
    "BRK.B": "Berkshire Hathaway Inc.",
    "BRK-B": "Berkshire Hathaway Inc.",
    "JNJ": "Johnson & Johnson",
    "JPM": "JPMorgan Chase & Co.",
    "V": "Visa Inc.",
    "PG": "The Procter & Gamble Company",
    "XOM": "Exxon Mobil Corporation",
    "CVX": "Chevron Corporation",
    "HD": "The Home Depot, Inc.",
    "MA": "Mastercard Incorporated",
    "BAC": "Bank of America Corporation",
    "LLY": "Eli Lilly and Company",
    "ABBV": "AbbVie Inc.",
    "KO": "The Coca-Cola Company",
    "PEP": "PepsiCo, Inc.",
    "COST": "Costco Wholesale Corporation",
    "WMT": "Walmart Inc.",
    "DIS": "The Walt Disney Company",
    "BA": "The Boeing Company",
    "CAT": "Caterpillar Inc.",
    "PFE": "Pfizer Inc.",
    "NFLX": "Netflix, Inc.",
    "TGT": "Target Corporation",
    "VZ": "Verizon Communications Inc.",
    "GE": "General Electric Company",
    "UNH": "UnitedHealth Group Incorporated",
    "CSCO": "Cisco Systems, Inc.",
    "ADBE": "Adobe Inc.",
    "CRM": "Salesforce, Inc.",
    "NKE": "NIKE, Inc.",
    "MCD": "McDonald's Corporation",
    "BMY": "Bristol-Myers Squibb Company",
    "ORCL": "Oracle Corporation",
    "UPS": "United Parcel Service, Inc.",
    "INTC": "Intel Corporation",
    "AMD": "Advanced Micro Devices, Inc.",
    "QCOM": "QUALCOMM Incorporated",
    "RTX": "RTX Corporation",
    "LMT": "Lockheed Martin Corporation",
    "GM": "General Motors Company",
    "F": "Ford Motor Company",
    "T": "AT&T Inc.",
    "PYPL": "PayPal Holdings, Inc.",
    "SBUX": "Starbucks Corporation",
    "LOW": "Lowe's Companies, Inc.",
    "FDX": "FedEx Corporation",
    "UNP": "Union Pacific Corporation",
    "COP": "ConocoPhillips",
    "SLB": "Schlumberger Limited",
    "PLTR": "Palantir Technologies Inc.",
    "UBER": "Uber Technologies, Inc.",
    "ABNB": "Airbnb, Inc.",
    "SNOW": "Snowflake Inc.",
    "CRWD": "CrowdStrike Holdings, Inc.",
    "MRNA": "Moderna, Inc.",
    "DKNG": "DraftKings Inc.",
    "HOOD": "Robinhood Markets, Inc.",
    "COIN": "Coinbase Global, Inc.",
    "SQ": "Block, Inc.",
    "BYND": "Beyond Meat, Inc.",
    "ZM": "Zoom Video Communications, Inc.",
    "GILD": "Gilead Sciences, Inc.",
    "ALL": "The Allstate Corporation",
    "HRL": "Hormel Foods Corporation",
    "DGX": "Quest Diagnostics Incorporated",
    "CCJ": "Cameco Corporation",
    "NWL": "Newell Brands Inc.",
    "MO": "Altria Group, Inc.",
    "MPC": "Marathon Petroleum Corporation",
    "MNDT": "Mandiant, Inc.",
    "IRM": "Iron Mountain Incorporated",
    "UAA": "Under Armour, Inc.",
    "SPY": "SPDR S&P 500 ETF Trust",
    "QQQ": "Invesco QQQ Trust",
    "IWM": "iShares Russell 2000 ETF",
    "VTI": "Vanguard Total Stock Market ETF",
    "VOO": "Vanguard S&P 500 ETF",
    "DIA": "SPDR Dow Jones Industrial Average ETF Trust",
    "XLF": "Financial Select Sector SPDR Fund",
    "XLK": "Technology Select Sector SPDR Fund",
    "XLE": "Energy Select Sector SPDR Fund",
}

# Regex patterns matching corporate names to (ticker, canonical_entity)
COMPANY_NAME_PATTERNS: list[tuple[re.Pattern[str], tuple[str, str]]] = [
    (re.compile(r"(?i)\bapple\b"), ("AAPL", "Apple Inc.")),
    (re.compile(r"(?i)\bmicrosoft\b"), ("MSFT", "Microsoft Corporation")),
    (re.compile(r"(?i)\bamazon\b"), ("AMZN", "Amazon.com, Inc.")),
    (re.compile(r"(?i)\b(alphabet|google)\b"), ("GOOGL", "Alphabet Inc.")),
    (re.compile(r"(?i)\bnvidia\b"), ("NVDA", "NVIDIA Corporation")),
    (re.compile(r"(?i)\b(meta platforms|facebook)\b"), ("META", "Meta Platforms, Inc.")),
    (re.compile(r"(?i)\btesla\b"), ("TSLA", "Tesla, Inc.")),
    (re.compile(r"(?i)\bberkshire hathaway\b"), ("BRK.B", "Berkshire Hathaway Inc.")),
    (re.compile(r"(?i)\bjohnson & johnson\b"), ("JNJ", "Johnson & Johnson")),
    (re.compile(r"(?i)\bjpmorgan\b"), ("JPM", "JPMorgan Chase & Co.")),
    (re.compile(r"(?i)\bvisa\b"), ("V", "Visa Inc.")),
    (re.compile(r"(?i)\bprocter & gamble\b"), ("PG", "The Procter & Gamble Company")),
    (re.compile(r"(?i)\bexxon\b"), ("XOM", "Exxon Mobil Corporation")),
    (re.compile(r"(?i)\bchevron\b"), ("CVX", "Chevron Corporation")),
    (re.compile(r"(?i)\bhome depot\b"), ("HD", "The Home Depot, Inc.")),
    (re.compile(r"(?i)\bmastercard\b"), ("MA", "Mastercard Incorporated")),
    (re.compile(r"(?i)\bbank of america\b"), ("BAC", "Bank of America Corporation")),
    (re.compile(r"(?i)\beli lilly\b"), ("LLY", "Eli Lilly and Company")),
    (re.compile(r"(?i)\babbvie\b"), ("ABBV", "AbbVie Inc.")),
    (re.compile(r"(?i)\bcoca-cola\b"), ("KO", "The Coca-Cola Company")),
    (re.compile(r"(?i)\bpepsico\b"), ("PEP", "PepsiCo, Inc.")),
    (re.compile(r"(?i)\bcostco\b"), ("COST", "Costco Wholesale Corporation")),
    (re.compile(r"(?i)\bwalmart\b"), ("WMT", "Walmart Inc.")),
    (re.compile(r"(?i)\b(walt disney|disney)\b"), ("DIS", "The Walt Disney Company")),
    (re.compile(r"(?i)\bboeing\b"), ("BA", "The Boeing Company")),
    (re.compile(r"(?i)\bcaterpillar\b"), ("CAT", "Caterpillar Inc.")),
    (re.compile(r"(?i)\bpfizer\b"), ("PFE", "Pfizer Inc.")),
    (re.compile(r"(?i)\bnetflix\b"), ("NFLX", "Netflix, Inc.")),
    (re.compile(r"(?i)\btarget\b"), ("TGT", "Target Corporation")),
    (re.compile(r"(?i)\bverizon\b"), ("VZ", "Verizon Communications Inc.")),
    (re.compile(r"(?i)\bgeneral electric\b"), ("GE", "General Electric Company")),
    (re.compile(r"(?i)\bunitedhealth\b"), ("UNH", "UnitedHealth Group Incorporated")),
    (re.compile(r"(?i)\bcisco\b"), ("CSCO", "Cisco Systems, Inc.")),
    (re.compile(r"(?i)\badobe\b"), ("ADBE", "Adobe Inc.")),
    (re.compile(r"(?i)\bsalesforce\b"), ("CRM", "Salesforce, Inc.")),
    (re.compile(r"(?i)\bnike\b"), ("NKE", "NIKE, Inc.")),
    (re.compile(r"(?i)\bmcdonald\b"), ("MCD", "McDonald's Corporation")),
    (re.compile(r"(?i)\bbristol-myers\b"), ("BMY", "Bristol-Myers Squibb Company")),
    (re.compile(r"(?i)\boracle\b"), ("ORCL", "Oracle Corporation")),
    (re.compile(r"(?i)\bunited parcel\b"), ("UPS", "United Parcel Service, Inc.")),
    (re.compile(r"(?i)\bintel\b"), ("INTC", "Intel Corporation")),
    (re.compile(r"(?i)\badvanced micro devices\b"), ("AMD", "Advanced Micro Devices, Inc.")),
    (re.compile(r"(?i)\bqualcomm\b"), ("QCOM", "QUALCOMM Incorporated")),
    (re.compile(r"(?i)\b(raytheon|rtx)\b"), ("RTX", "RTX Corporation")),
    (re.compile(r"(?i)\blockheed martin\b"), ("LMT", "Lockheed Martin Corporation")),
    (re.compile(r"(?i)\bgeneral motors\b"), ("GM", "General Motors Company")),
    (re.compile(r"(?i)\bford motor\b"), ("F", "Ford Motor Company")),
    (re.compile(r"(?i)\bat&t\b"), ("T", "AT&T Inc.")),
    (re.compile(r"(?i)\bpaypal\b"), ("PYPL", "PayPal Holdings, Inc.")),
    (re.compile(r"(?i)\bstarbucks\b"), ("SBUX", "Starbucks Corporation")),
    (re.compile(r"(?i)\blowe's\b"), ("LOW", "Lowe's Companies, Inc.")),
    (re.compile(r"(?i)\bfedex\b"), ("FDX", "FedEx Corporation")),
    (re.compile(r"(?i)\bunion pacific\b"), ("UNP", "Union Pacific Corporation")),
    (re.compile(r"(?i)\bconocophillips\b"), ("COP", "ConocoPhillips")),
    (re.compile(r"(?i)\bschlumberger\b"), ("SLB", "Schlumberger Limited")),
    (re.compile(r"(?i)\bpalantir\b"), ("PLTR", "Palantir Technologies Inc.")),
    (re.compile(r"(?i)\buber\b"), ("UBER", "Uber Technologies, Inc.")),
    (re.compile(r"(?i)\bairbnb\b"), ("ABNB", "Airbnb, Inc.")),
    (re.compile(r"(?i)\bsnowflake\b"), ("SNOW", "Snowflake Inc.")),
    (re.compile(r"(?i)\bcrowdstrike\b"), ("CRWD", "CrowdStrike Holdings, Inc.")),
    (re.compile(r"(?i)\bmoderna\b"), ("MRNA", "Moderna, Inc.")),
    (re.compile(r"(?i)\bdraftkings\b"), ("DKNG", "DraftKings Inc.")),
    (re.compile(r"(?i)\brobinhood\b"), ("HOOD", "Robinhood Markets, Inc.")),
    (re.compile(r"(?i)\bcoinbase\b"), ("COIN", "Coinbase Global, Inc.")),
    (re.compile(r"(?i)\bblock, inc\b"), ("SQ", "Block, Inc.")),
    (re.compile(r"(?i)\bbeyond meat\b"), ("BYND", "Beyond Meat, Inc.")),
    (re.compile(r"(?i)\bzoom video\b"), ("ZM", "Zoom Video Communications, Inc.")),
    (re.compile(r"(?i)\bgilead\b"), ("GILD", "Gilead Sciences, Inc.")),
    (re.compile(r"(?i)\ballstate\b"), ("ALL", "The Allstate Corporation")),
    (re.compile(r"(?i)\bhormel\b"), ("HRL", "Hormel Foods Corporation")),
    (re.compile(r"(?i)\bquest diagnostics\b"), ("DGX", "Quest Diagnostics Incorporated")),
    (re.compile(r"(?i)\bcameco\b"), ("CCJ", "Cameco Corporation")),
    (re.compile(r"(?i)\bnewell brands\b"), ("NWL", "Newell Brands Inc.")),
    (re.compile(r"(?i)\baltria\b"), ("MO", "Altria Group, Inc.")),
    (re.compile(r"(?i)\bmarathon petroleum\b"), ("MPC", "Marathon Petroleum Corporation")),
    (re.compile(r"(?i)\biron mountain\b"), ("IRM", "Iron Mountain Incorporated")),
    (re.compile(r"(?i)\bunder armour\b"), ("UAA", "Under Armour, Inc.")),
    (re.compile(r"(?i)\bspdr s&p 500\b"), ("SPY", "SPDR S&P 500 ETF Trust")),
    (re.compile(r"(?i)\binvesco qqq\b"), ("QQQ", "Invesco QQQ Trust")),
]


def _clean_description(desc: str | None) -> str:
    """Clean HTML tags, entities, and extra whitespace from an asset description."""
    if not desc or not isinstance(desc, str):
        return ""
    text = html.unescape(desc)
    text = HTML_TAG_RE.sub(" ", text)
    return " ".join(text.split()).strip()


def _is_non_equity(text: str, asset_type: str | None = None) -> bool:
    """Check if the text or asset type indicates a non-equity asset."""
    if asset_type in NON_EQUITY_ASSET_TYPES:
        return True
    lowered = text.lower()
    return any(keyword in lowered for keyword in NON_EQUITY_KEYWORDS)


def _clean_entity_name(text: str) -> str | None:
    """Extract a cleaned corporate entity name from a descriptive asset string."""
    if not text:
        return None
    # Strip parenthesized tokens (e.g. tickers)
    name = re.sub(r"\([A-Za-z0-9.-]+\)", "", text)
    # Strip bracketed tokens (e.g. [ST])
    name = re.sub(r"\[[A-Za-z0-9]+\]", "", name)
    # Strip leading descriptive prefixes (e.g. 'Shares of ', 'Common Stock - ')
    name = re.sub(
        r"(?i)^(?:common\s+stock(?:\s*[-:]\s*|\s+of\s+)?|shares\s+of\s+|option\s+(?:on\s+)?|bond\s*[-:]\s*)",
        "",
        name,
    )
    # Strip leading ticker prefixes (e.g. 'AAPL - ')
    name = re.sub(r"^[A-Za-z]{1,5}\s*[-:]\s*", "", name)
    # Strip share class or common stock suffixes
    name = re.sub(
        r"(?i)\b(?:common\s+stock|capital\s+stock|ordinary\s+shares|class\s+[a-z]|cl\s+[a-z]|cmn|shares|stock)\b",
        "",
        name,
    )
    # Strip transaction annotations
    name = re.sub(r"(?i)\b(?:exchanged|received|muni)\b", "", name)
    cleaned = " ".join(name.split()).strip(" ,-.:")
    if len(cleaned) < 2 or cleaned.lower() in ("description", "stock", "none", "n/a"):
        return None
    return cleaned


def resolve_ticker(
    asset_description: str | None,
    ticker: str | None = None,
    asset_type: str | None = None,
) -> str | None:
    """Resolve and normalize the ticker symbol for a transaction.

    Validates candidate tickers against standard exchange rules, extracts embedded
    tickers from disclosure descriptions via regex heuristics, maps corporate entity
    names to known symbols, and excludes non-equity assets.
    """
    if ticker is not None:
        raw = str(ticker).strip().upper().lstrip("$")
        if raw in PLACEHOLDER_TICKERS or not raw:
            raw = None
        elif TICKER_RE.match(raw) and raw not in EXCLUDE_TICKER_TOKENS:
            return raw

    clean_desc = _clean_description(asset_description)
    if not clean_desc:
        return None

    if _is_non_equity(clean_desc, asset_type):
        return None

    # 1. Regex match for parenthesized ticker: (AAPL)
    match = PAREN_TICKER_RE.search(clean_desc)
    if match:
        cand = match.group(1).upper()
        if cand not in EXCLUDE_TICKER_TOKENS and TICKER_RE.match(cand):
            return cand

    # 2. Regex match for bracketed ticker: [AAPL]
    match = BRACKET_TICKER_RE.search(clean_desc)
    if match:
        cand = match.group(1).upper()
        if cand not in EXCLUDE_TICKER_TOKENS and TICKER_RE.match(cand):
            return cand

    # 3. Leading ticker prefix: 'AAPL - Apple Inc.' or 'GOOG - Alphabet'
    match = PREFIX_TICKER_RE.match(clean_desc)
    if match:
        cand = match.group(1).upper()
        if cand not in EXCLUDE_TICKER_TOKENS and TICKER_RE.match(cand):
            return cand

    # 4. Explicit label: 'Ticker: MSFT'
    match = LABEL_TICKER_RE.search(clean_desc)
    if match:
        cand = match.group(1).upper()
        if cand not in EXCLUDE_TICKER_TOKENS and TICKER_RE.match(cand):
            return cand

    # 5. Standalone ticker word: 'msft', 'aapl', 'ba'
    alpha_only = re.sub(r"[^A-Za-z]", "", clean_desc).upper()
    if (
        1 <= len(alpha_only) <= 5
        and " " not in clean_desc.strip()
        and alpha_only not in EXCLUDE_TICKER_TOKENS
        and TICKER_RE.match(alpha_only)
    ):
        return alpha_only

    # 6. Corporate entity name lookup
    for pattern, (symbol, _) in COMPANY_NAME_PATTERNS:
        if pattern.search(clean_desc):
            return symbol

    return None


def resolve_corporate_entity(
    asset_description: str | None,
    ticker: str | None = None,
    asset_type: str | None = None,
) -> str | None:
    """Map a transaction to its canonical corporate entity name.

    Uses resolved tickers to look up canonical company names, and falls back
    to descriptive entity name normalization when ticker is unlisted. Excludes
    non-equity assets like municipal bonds and sovereign debt.
    """
    clean_desc = _clean_description(asset_description)
    if clean_desc and _is_non_equity(clean_desc, asset_type):
        return None

    # If valid ticker provided, check canonical dictionary
    if ticker:
        normalized_ticker = str(ticker).strip().upper().lstrip("$")
        if normalized_ticker in CANONICAL_TICKER_TO_ENTITY:
            return CANONICAL_TICKER_TO_ENTITY[normalized_ticker]

    # Check known company name patterns in description
    if clean_desc:
        for pattern, (_, entity_name) in COMPANY_NAME_PATTERNS:
            if pattern.search(clean_desc):
                return entity_name

        cleaned_entity = _clean_entity_name(clean_desc)
        if cleaned_entity:
            return cleaned_entity

    return None


def link_asset_entity(
    asset_description: str | None,
    ticker: str | None = None,
    asset_type: str | None = None,
) -> tuple[str | None, str | None]:
    """Link an asset description and optional ticker to normalized (ticker, corporate_entity)."""
    resolved_sym = resolve_ticker(asset_description, ticker=ticker, asset_type=asset_type)
    resolved_entity = resolve_corporate_entity(
        asset_description, ticker=resolved_sym, asset_type=asset_type
    )
    return resolved_sym, resolved_entity


def link_dataframe_entities(df: pd.DataFrame) -> pd.DataFrame:
    """Apply automated ticker resolution and corporate entity mapping to a DataFrame."""
    if df.empty:
        if "ticker" not in df.columns:
            df["ticker"] = None
        if "corporate_entity" not in df.columns:
            df["corporate_entity"] = None
        return df

    df = df.copy()

    has_ticker = "ticker" in df.columns
    has_desc = "asset_description" in df.columns
    has_type = "asset_type" in df.columns

    resolved_tickers: list[str | None] = []
    resolved_entities: list[str | None] = []

    for _, row in df.iterrows():
        t = row["ticker"] if has_ticker else None
        d = row["asset_description"] if has_desc else None
        atype = row["asset_type"] if has_type else None

        sym, entity = link_asset_entity(d, ticker=t, asset_type=atype)
        resolved_tickers.append(sym)
        resolved_entities.append(entity)

    df["ticker"] = pd.Series(resolved_tickers, index=df.index, dtype=object).replace(
        {float("nan"): None}
    )
    df["corporate_entity"] = pd.Series(resolved_entities, index=df.index, dtype=object).replace(
        {float("nan"): None}
    )

    return df
