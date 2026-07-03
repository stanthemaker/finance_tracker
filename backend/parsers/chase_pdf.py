"""
Chase PDF statement parser.
Handles both checking and credit card statement formats,
including the doubled-character PDF rendering artifact Chase uses on some statements
(e.g. "AACCCCOOUUNNTT AACCTTIIVVIITTYY" instead of "ACCOUNT ACTIVITY").
"""
import re
from datetime import datetime
from typing import Optional
import pdfplumber


# ── helpers ──────────────────────────────────────────────────────────────────

def _clean_amount(raw: str) -> Optional[float]:
    """Convert '$1,234.56' / '-$50.00' / '($50.00)' to float."""
    if raw is None:
        return None
    s = raw.strip().replace(",", "").replace("$", "").replace(" ", "")
    negative = s.startswith("(") or s.startswith("-")
    s = s.strip("()-")
    try:
        val = float(s)
        return -val if negative else val
    except ValueError:
        return None


def _parse_date(raw: str, year_hint: int, closing_month: int = 12) -> Optional[str]:
    """
    Parse 'MM/DD' or 'MM/DD/YY' → 'YYYY-MM-DD'.
    Handles cross-year billing cycles: if the statement closes in Jan or Feb
    and the transaction month is Nov or Dec, it belongs to the previous year.
    """
    raw = raw.strip()
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    try:
        dt = datetime.strptime(raw, "%m/%d")
        year = year_hint
        # Cross-year boundary: closing in Jan/Feb, transaction in Nov/Dec → previous year
        if closing_month <= 2 and dt.month >= 11:
            year = year_hint - 1
        return dt.replace(year=year).strftime("%Y-%m-%d")
    except ValueError:
        return None


_MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _year_and_closing_month_from_filename(filename: str) -> tuple[int, int]:
    """Extract (closing_year, closing_month) from '20260110...' or '2026-Mar-...' filenames."""
    # Original numeric format: 20260310-statements-7008-.pdf
    m = re.search(r"(20\d{2})(\d{2})\d{2}", filename)
    if m:
        return int(m.group(1)), int(m.group(2))
    # Friendly renamed format: 2026-Mar-Credit-Chase.pdf
    m = re.search(r"(20\d{2})-([A-Za-z]{3})-", filename)
    if m:
        month = _MONTH_ABBR.get(m.group(2).lower())
        if month:
            return int(m.group(1)), month
    now = datetime.now()
    return now.year, now.month


def _dedouble(line: str) -> str:
    """
    Normalize Chase's doubled-character PDF artifact.
    'AACCCCOOUUNNTT AACCTTIIVVIITTYY' → 'ACCOUNT ACTIVITY'
    Only removes a char if it's immediately repeated; leaves normal text untouched.
    """
    result, i = [], 0
    while i < len(line):
        result.append(line[i])
        if i + 1 < len(line) and line[i] == line[i + 1] and line[i] != " ":
            i += 2
        else:
            i += 1
    return "".join(result)


# ── credit card parser ────────────────────────────────────────────────────────

# Chase credit card format (Freedom Flex / Sapphire etc.):
# "02/10 UEP*J'S SNACKS AND TEA BERKELEY CA 12.55"
# "03/06 AUTOMATIC PAYMENT - THANK YOU -1,155.54"
_CC_ROW = re.compile(
    r"^(\d{2}/\d{2})\s+"          # transaction date
    r"(?:\d{2}/\d{2}\s+)?"        # optional post date
    r"(.+?)\s+"                    # description (non-greedy)
    r"(-?\$?[\d,]+\.\d{2})$"      # amount (with or without $, may be negative)
)


def _parse_credit_card(pdf, filename: str) -> list[dict]:
    year, closing_month = _year_and_closing_month_from_filename(filename)
    transactions = []
    in_activity = False

    for page in pdf.pages:
        text = page.extract_text() or ""
        for line in text.splitlines():
            line = line.strip()
            norm = _dedouble(line).lower()

            if re.search(r"account activity|transaction detail|merchant name or transaction", norm):
                in_activity = True
                continue
            if re.search(r"interest charges|total fees|2\d{3} totals|annual percentage rate", norm):
                in_activity = False
                continue
            if not in_activity:
                continue

            m = _CC_ROW.match(line)
            if not m:
                continue

            date_str   = m.group(1)
            desc       = m.group(2).strip()
            amount_str = m.group(3)

            if desc.lower() in ("transaction", "merchant name or transaction description"):
                continue

            amount = _clean_amount(amount_str)
            date   = _parse_date(date_str, year, closing_month)
            if amount is None or date is None:
                continue

            transactions.append({
                "date":         date,
                "description":  desc,
                "amount":       -amount,
                "account_type": "credit",
            })

    return transactions


# ── checking parser ───────────────────────────────────────────────────────────

_CHK_ROW = re.compile(
    r"^(\d{2}/\d{2}(?:/\d{2,4})?)\s+"
    r"(.+?)\s+"
    r"(-?[\d,]+\.\d{2})\s+"        # amount
    r"-?[\d,]+\.\d{2}$"            # balance (ignored)
)

_CHK_ROW_NO_BAL = re.compile(
    r"^(\d{2}/\d{2}(?:/\d{2,4})?)\s+"
    r"(.+?)\s+"
    r"(-?[\d,]+\.\d{2})$"
)


def _parse_checking(pdf, filename: str) -> tuple[list[dict], Optional[float]]:
    year, closing_month = _year_and_closing_month_from_filename(filename)
    transactions = []
    in_detail = False
    ending_balance = None

    for page in pdf.pages:
        text = page.extract_text() or ""
        for line in text.splitlines():
            line = line.strip()
            norm = _dedouble(line).lower()

            if re.search(r"transaction detail|\*start\*transaction|account activity|deposits.*additions", norm):
                in_detail = True
                continue
            if re.search(r"ending balance|\*end\*transaction|service fee summary|daily balance", norm):
                # Capture ending balance amount from this line before exiting
                if ending_balance is None:
                    amt_m = re.search(r"([\d,]+\.\d{2})", line)
                    if amt_m:
                        ending_balance = _clean_amount(amt_m.group(1))
                in_detail = False
                continue
            if not in_detail:
                continue

            m = _CHK_ROW.match(line) or _CHK_ROW_NO_BAL.match(line)
            if not m:
                continue

            date_str, desc, amount_str = m.group(1), m.group(2).strip(), m.group(3)
            if "beginning balance" in desc.lower():
                continue

            amount = _clean_amount(amount_str)
            date   = _parse_date(date_str, year, closing_month)
            if amount is None or date is None:
                continue

            transactions.append({
                "date":         date,
                "description":  desc,
                "amount":       amount,
                "account_type": "checking",
            })

    return transactions, ending_balance


def _extract_credit_new_balance(pdf) -> Optional[float]:
    """Extract the 'New Balance' amount from a credit card statement."""
    for page in pdf.pages[:3]:
        text = page.extract_text() or ""
        for line in text.splitlines():
            norm = _dedouble(line).lower().strip()
            m = re.search(r"new\s+balance\s+\$?([\d,]+\.\d{2})", norm)
            if m:
                return _clean_amount(m.group(1))
            # Also catch "Statement Balance $X" format
            m = re.search(r"statement\s+balance\s+\$?([\d,]+\.\d{2})", norm)
            if m:
                return _clean_amount(m.group(1))
    return None


# ── table-based fallback ──────────────────────────────────────────────────────

def _parse_tables(pdf, filename: str, account_type: str) -> list[dict]:
    """Fallback: extract transactions from PDF tables when text parsing finds nothing."""
    year, closing_month = _year_and_closing_month_from_filename(filename)
    transactions = []
    date_re = re.compile(r"^\d{2}/\d{2}")

    for page in pdf.pages:
        for table in page.extract_tables():
            for row in table:
                if row is None:
                    continue
                cells = [str(c).strip() if c else "" for c in row]
                date_cell = next((c for c in cells if date_re.match(c)), None)
                if not date_cell:
                    continue
                amount_cell = next(
                    (c for c in reversed(cells)
                     if re.match(r"-?[\d,]+\.\d{2}$", c.replace("$", "").replace(",", ""))),
                    None,
                )
                if not amount_cell:
                    continue
                desc_idx = cells.index(date_cell) + 1
                desc = " ".join(cells[desc_idx:cells.index(amount_cell)]).strip() if desc_idx < len(cells) else ""
                if not desc:
                    continue
                amount = _clean_amount(amount_cell)
                date   = _parse_date(date_cell, year, closing_month)
                if amount is None or date is None:
                    continue
                if account_type == "credit":
                    amount = -amount
                transactions.append({
                    "date":         date,
                    "description":  desc,
                    "amount":       amount,
                    "account_type": account_type,
                })

    return transactions


# ── closing month extractor (credit only) ────────────────────────────────────

_PERIOD_DATE_RE = re.compile(
    r"opening/closing date\s+(\d{1,2}/\d{1,2}/\d{2,4})\s*-\s*\d{1,2}/\d{1,2}/\d{2,4}"
)


def _extract_credit_statement_month(pdf) -> Optional[str]:
    """
    Extract the billing period's opening month from 'Opening/Closing Date MM/DD/YY - MM/DD/YY'.
    Returns 'YYYY-MM' based on the opening date (e.g. 03/11/26 - 04/10/26 → '2026-03').
    Searches raw text first to avoid _dedouble corrupting dates like 11/10/25 → 1/10/25.
    """
    for page in pdf.pages[:2]:
        text = page.extract_text() or ""
        for candidate in (text.lower(), _dedouble(text).lower()):
            m = _PERIOD_DATE_RE.search(candidate)
            if m:
                opening_raw = m.group(1)
                for fmt in ("%m/%d/%Y", "%m/%d/%y"):
                    try:
                        dt = datetime.strptime(opening_raw.strip(), fmt)
                        return dt.strftime("%Y-%m")
                    except ValueError:
                        pass
    return None


# ── public API ────────────────────────────────────────────────────────────────

def detect_account_type(pdf) -> str:
    """Guess 'credit' or 'checking' from the first page text."""
    first_page = pdf.pages[0].extract_text() or ""
    text = _dedouble(first_page).lower()
    if any(kw in text for kw in ["credit card", "credit account", "rewards card",
                                   "chase freedom", "chase sapphire", "cash back"]):
        return "credit"
    if any(kw in text for kw in ["checking", "total checking", "account balance"]):
        return "checking"
    if any(kw in text for kw in ["sapphire", "freedom", "unlimited", "preferred", "flex"]):
        return "credit"
    return "checking"


def parse_statement(filepath: str, filename: str) -> tuple[str, list[dict], Optional[str], Optional[float]]:
    """
    Parse a Chase PDF statement.
    Returns (account_type, transactions, closing_month, ending_balance) where:
      - closing_month: 'YYYY-MM' from the PDF (credit) or None (checking)
      - ending_balance: statement ending/new balance, or None if not found
    """
    with pdfplumber.open(filepath) as pdf:
        account_type = detect_account_type(pdf)
        closing_month = None
        ending_balance = None

        if account_type == "credit":
            txns = _parse_credit_card(pdf, filename)
            closing_month = _extract_credit_statement_month(pdf)
            ending_balance = _extract_credit_new_balance(pdf)
        else:
            txns, ending_balance = _parse_checking(pdf, filename)

        if not txns:
            txns = _parse_tables(pdf, filename, account_type)

    return account_type, txns, closing_month, ending_balance
