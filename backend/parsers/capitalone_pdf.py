"""
Capital One 360 Performance Savings statement parser.
Only extracts the ending balance (for net worth tracking as emergency fund).
No transaction import — these accounts have minimal activity (just interest).
"""
import re
from typing import Optional
import pdfplumber

_MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def is_capitalone_savings(pdf) -> bool:
    text = (pdf.pages[0].extract_text() or "").lower()
    return "capital one" in text and (
        "360" in text or "performance savings" in text or "thanks for saving" in text
    )


def _extract_date(text: str) -> Optional[str]:
    # Primary: "Here's your March 2026 bank statement."
    m = re.search(
        r"here.s your\s+(\w+)\s+(\d{4})\s+bank statement",
        text, re.IGNORECASE
    )
    if m:
        month_word = m.group(1).lower()
        year = int(m.group(2))
        mn = _MONTH_NAMES.get(month_word)
        if not mn:
            # try prefix match e.g. "Feb" → "february"
            mn = next((v for k, v in _MONTH_NAMES.items() if k.startswith(month_word[:3])), None)
        if mn:
            return f"{year}-{mn:02d}"

    # Fallback: "STATEMENT PERIOD Mar 1 - Mar 31, 2026"
    m = re.search(
        r"statement period\s+(\w+)\s+\d+\s*[-–]\s*\w+\s+\d+,\s*(\d{4})",
        text, re.IGNORECASE
    )
    if m:
        month_word = m.group(1).lower()
        year = int(m.group(2))
        mn = next((v for k, v in _MONTH_NAMES.items() if k.startswith(month_word[:3])), None)
        if mn:
            return f"{year}-{mn:02d}"

    return None


def _extract_balance(text: str) -> Optional[float]:
    def _parse(s):
        try:
            return float(s.replace(",", ""))
        except ValueError:
            return None

    # Primary: "Closing Balance $6,023.42" in transaction table
    m = re.search(r"closing balance\s+\$?([\d,]+\.\d{2})", text, re.IGNORECASE)
    if m:
        return _parse(m.group(1))

    # Secondary: "$6,023.42\n...TOTAL ENDING BALANCE"
    m = re.search(
        r"\$([\d,]+\.\d{2})[\s\S]{0,60}?total ending balance",
        text, re.IGNORECASE
    )
    if m:
        return _parse(m.group(1))

    # Fallback: last value on the account summary row
    # "360 Performance Savings...8513 $6,007.15 $6,023.42"
    m = re.search(
        r"360 performance savings[^\n]*\$[\d,]+\.\d{2}\s+\$?([\d,]+\.\d{2})",
        text, re.IGNORECASE
    )
    if m:
        return _parse(m.group(1))

    return None


def parse_capitalone_savings(filepath: str, filename: str) -> Optional[dict]:
    """
    Parse a Capital One 360 savings statement.
    Returns {statement_date, filename, balance} or None if not a Capital One savings statement.
    """
    with pdfplumber.open(filepath) as pdf:
        if not is_capitalone_savings(pdf):
            return None

        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages[:3])

        statement_date = _extract_date(full_text)
        balance = _extract_balance(full_text)

    if balance is None:
        return None

    return {
        "statement_date": statement_date,
        "filename": filename,
        "balance": balance,
    }
