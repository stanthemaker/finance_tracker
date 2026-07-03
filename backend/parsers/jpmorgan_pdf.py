"""
J.P. Morgan Consolidated Investment Statement PDF parser.

Format confirmed from April 2026 statement:
- Page 1: Portfolio Value table ("PORTFOLIO VALUE $7,693.50 $8,165.90")
- Page 3: Asset Allocation ("Cash & Money Market Funds 1,973.65 2,123.67 150.02")
- Page 5: Summary of Accounts ("TOTAL PORTFOLIO VALUE $7,693.50 $150.00 ...")
- Holdings section: one line per security, followed by "Symbol: TICKER"
  Equity: "BERKSHIRE HATHAWAY INC 02 Mar 2026 N 7 473.6 3,315.20 485 3,395.00 (79.80) ST --"
  Cash:   "CHASE IRA DEPOSIT SWEEP 2,055.03 1 2,055.03 --"
"""
import re
from typing import Optional
import pdfplumber

_MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def _amt(s) -> Optional[float]:
    if s is None:
        return None
    s = str(s).strip().replace(",", "").replace("$", "").replace(" ", "")
    negative = s.startswith("(") or s.startswith("-")
    s = re.sub(r"[()\-]", "", s).strip()
    try:
        return -float(s) if negative else float(s)
    except ValueError:
        return None


def is_jpmorgan(pdf) -> bool:
    text = (pdf.pages[0].extract_text() or "").lower()
    return "j.p. morgan" in text and (
        "consolidated investment" in text or "investment statement" in text
    )


def _extract_date(text: str) -> Optional[str]:
    """Handle 'Statement PeriodEnding April 30, 2026' and 'Statement Period Ending: April 30, 2026'."""
    m = re.search(
        r"statement\s+period\s*ending[:\s]+(\w+)\s+\d+,?\s*(\d{4})",
        text, re.IGNORECASE
    )
    if m:
        mn = _MONTH_NAMES.get(m.group(1).lower())
        if mn:
            return f"{int(m.group(2))}-{mn:02d}"
    return None


def _extract_portfolio_values(text: str) -> tuple[Optional[float], Optional[float]]:
    """Returns (prev_value, current_value) from 'PORTFOLIO VALUE $7,693.50 $8,165.90'."""
    m = re.search(
        r"portfolio value\s+\$?([\d,]+\.?\d*)\s+\$?([\d,]+\.?\d*)",
        text, re.IGNORECASE
    )
    if m:
        return _amt(m.group(1)), _amt(m.group(2))
    return None, None


def _extract_asset_allocation(text: str) -> dict:
    """Extract cash and equity total values (This Month column)."""
    result = {}
    # "Cash & Money Market Funds 1,973.65 2,123.67 150.02"
    m = re.search(
        r"cash\s*&\s*money\s*market\s*funds?\s+[\d,]+\.?\d*\s+([\d,]+\.?\d*)",
        text, re.IGNORECASE
    )
    if m:
        result["cash"] = _amt(m.group(1))
    # "Equity 5,719.85 6,042.23 322.38"
    m = re.search(
        r"(?:^|\n)equity\s+[\d,]+\.?\d*\s+([\d,]+\.?\d*)",
        text, re.IGNORECASE | re.MULTILINE
    )
    if m:
        result["equity"] = _amt(m.group(1))
    return result


def _extract_net_deposits(text: str) -> float:
    """
    Page 5 has 6-column format: 'TOTAL PORTFOLIO VALUE $7,693.50 $150.00 $0.02 $0.00 $322.38 $8,165.90'
    Page 3 has 2-column format: 'TOTAL PORTFOLIO VALUE $7,693.50 $8,165.90'
    We need page 5's 2nd value ($150.00). Require a 3rd dollar value to avoid matching page 3.
    """
    m = re.search(
        r"total portfolio value\s+\$[\d,]+\.?\d*\s+\$?([\d,]+\.?\d*)\s+\$[\d,]",
        text, re.IGNORECASE
    )
    if m:
        return _amt(m.group(1)) or 0.0
    # Fallback: "Net Cash Activity $150.02" from consolidated cash flow summary
    m = re.search(r"net cash activity\s+\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
    if m:
        return _amt(m.group(1)) or 0.0
    return 0.0


# Equity holding line:
# "BERKSHIRE HATHAWAY INC 02 Mar 2026 N 7 473.6 3,315.20 485 3,395.00 (79.80) ST --"
_EQ_LINE = re.compile(
    r"^([A-Z][A-Z\s,&.()\-]+?)\s+"   # security name (greedy stop before date)
    r"(\d{2}\s+\w{3}\s+\d{4})\s+"    # acquisition date "02 Mar 2026"
    r"\w\s+"                          # coverage flag (N = noncovered, etc.)
    r"([\d.]+)\s+"                    # quantity
    r"([\d,.]+)\s+"                   # price
    r"([\d,.]+)\s+"                   # market value
    r"([\d,.]+)\s+"                   # unit cost
    r"([\d,.]+)\s+"                   # cost basis
    r"(\(?[\d,.]+\)?)"               # unrealized G/L "(79.80)" or "188.50"
)

# Cash holding line:
# "CHASE IRA DEPOSIT SWEEP 2,055.03 1 2,055.03 --"
_CASH_LINE = re.compile(
    r"^([A-Z][A-Z\s]+[A-Z])\s+"   # name (all caps)
    r"([\d,.]+)\s+"                # market value
    r"(\d+)\s+"                    # quantity (usually 1)
    r"([\d,.]+)"                   # market value again
)


def _extract_holdings(pdf) -> list[dict]:
    """
    Parse holdings by matching data lines then correlating with 'Symbol:' lines.
    Holdings span per-account sections within the PDF.
    """
    holdings = []

    for page in pdf.pages:
        text = page.extract_text() or ""
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        current_account = None
        current_asset_class = None
        pending: Optional[dict] = None

        for line in lines:
            norm = line.lower()

            # Track which account we're reading
            if re.search(r"ira roth\s*\(acct", norm):
                current_account = "IRA Roth"
            elif re.search(r"brokerage\s*\(acct|individual\s*\(acct", norm):
                current_account = "Brokerage"

            # Track asset class sections
            if re.match(r"^cash\s*&\s*money\s*market", norm):
                current_asset_class = "cash"
            elif re.match(r"^equity(\s|\(|$)", norm):
                current_asset_class = "equity"
            elif re.match(r"^fixed\s*income", norm):
                current_asset_class = "fixed_income"

            # "Symbol: BRKB" → close out the pending holding
            sym_m = re.match(r"^symbol:\s*(\w+)", norm)
            if sym_m:
                if pending:
                    pending["symbol"] = sym_m.group(1).upper()
                    holdings.append(pending)
                    pending = None
                continue

            # Skip total/header/blank lines
            if any(x in norm for x in [
                "total cash", "total equity", "total account", "total portfolio",
                "total assets", "acquisition", "unrealized", "est. accrued",
                "i will show",   # redacted placeholder text in this PDF
            ]):
                continue

            # Try equity holding line
            if current_asset_class == "equity":
                eq_m = _EQ_LINE.match(line)
                if eq_m:
                    # If there's already a pending holding (missed symbol), save it
                    if pending:
                        holdings.append(pending)
                    pending = {
                        "account":      current_account or "Unknown",
                        "asset_class":  "equity",
                        "symbol":       None,
                        "name":         eq_m.group(1).strip(),
                        "quantity":     _amt(eq_m.group(3)),
                        "price":        _amt(eq_m.group(4)),
                        "market_value": _amt(eq_m.group(5)),
                        "cost_basis":   _amt(eq_m.group(7)),
                        "unrealized_gl": _amt(eq_m.group(8)),
                    }
                    continue

            # Try cash holding line
            if current_asset_class == "cash":
                cash_m = _CASH_LINE.match(line)
                if cash_m:
                    name = cash_m.group(1).strip()
                    # Exclude obvious section headers
                    if not any(x in name.lower() for x in ["total", "description"]):
                        if pending:
                            holdings.append(pending)
                        pending = {
                            "account":       current_account or "Unknown",
                            "asset_class":   "cash",
                            "symbol":        None,
                            "name":          name,
                            "quantity":      _amt(cash_m.group(3)),
                            "price":         1.0,
                            "market_value":  _amt(cash_m.group(2)),
                            "cost_basis":    _amt(cash_m.group(2)),
                            "unrealized_gl": 0.0,
                        }
                        continue

        # Page ended with a pending holding (Symbol on next page is rare but handle it)
        if pending and pending.get("market_value"):
            holdings.append(pending)

    return holdings


def parse_jpmorgan(filepath: str, filename: str) -> Optional[dict]:
    """
    Parse a J.P. Morgan Consolidated Investment Statement PDF.
    Returns None if the file is not a J.P. Morgan statement.
    """
    with pdfplumber.open(filepath) as pdf:
        if not is_jpmorgan(pdf):
            return None

        # Summary data lives in the first ~6 pages
        summary_text = "\n".join(
            (page.extract_text() or "") for page in pdf.pages[:7]
        )

        statement_date = _extract_date(summary_text)
        prev_value, total_value = _extract_portfolio_values(summary_text)
        asset_alloc = _extract_asset_allocation(summary_text)
        net_deposits = _extract_net_deposits(summary_text)

        market_gain = None
        if total_value is not None and prev_value is not None:
            market_gain = round(total_value - prev_value - (net_deposits or 0), 2)

        holdings = _extract_holdings(pdf)

    return {
        "statement_date": statement_date,
        "filename":       filename,
        "total_value":    total_value,
        "prev_value":     prev_value,
        "cash_value":     asset_alloc.get("cash"),
        "equity_value":   asset_alloc.get("equity"),
        "net_deposits":   net_deposits,
        "market_gain":    market_gain,
        "holdings":       holdings,
    }
