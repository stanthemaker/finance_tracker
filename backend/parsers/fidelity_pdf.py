"""
Fidelity Investment Report PDF parser.

Format confirmed from the June 2026 statement (Statement06302026.pdf):
- Page 1: header "INVESTMENT REPORT", period "May 28, 2026 - June 30, 2026",
  and the portfolio roll-up:
      Your Portfolio Value: $18,593.57
      Beginning Portfolio Valuez - -
      Additions 18,486.42 18,486.42
      Subtractions -93.97 -93.97
      Change in Investment Value * 201.12 201.12
      Ending Portfolio Value ** $18,593.57 $18,593.57
- Per-account "Holdings" pages list one position per data line:
      NAME (SYMBOL) unavailable QTY PRICE MARKET_VALUE COST GAIN/LOSS EAI
  Names may wrap onto following lines, where the (SYMBOL) sometimes lives:
      FIDELITY GOVERNMENT MONEY unavailable 2,422.190 $1.0000 $2,422.19 ...
      MARKET (SPAXX) 3.600%
  Sections: "Core Account" (money market → cash), "Stocks"/"Common Stock",
  "Exchange Traded Products", "Other" (e.g. a CD → fixed income).

Maps onto the same portfolio_snapshots / portfolio_holdings schema as the
J.P. Morgan parser so the Portfolio dashboard treats them uniformly.
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
    """Parse a money token, tolerating $ , ( ) and a trailing flag letter (e.g. '$2,000.00B')."""
    if s is None:
        return None
    s = str(s).strip().replace(",", "").replace("$", "").replace(" ", "")
    negative = s.startswith("(") or s.startswith("-")
    m = re.search(r"\d[\d.]*", s)
    if not m:
        return None
    try:
        val = float(m.group(0))
    except ValueError:
        return None
    return -val if negative else val


def is_fidelity(pdf) -> bool:
    text = (pdf.pages[0].extract_text() or "").lower()
    return "investment report" in text and "fidelity" in text


def _extract_date(text: str) -> Optional[str]:
    """From 'May 28, 2026 - June 30, 2026' return the period-end month '2026-06'."""
    m = re.search(
        r"\w+\s+\d+,\s*\d{4}\s*-\s*(\w+)\s+\d+,\s*(\d{4})",
        text,
    )
    if m:
        mn = _MONTH_NAMES.get(m.group(1).lower())
        if mn:
            return f"{int(m.group(2))}-{mn:02d}"
    return None


def _extract_summary(text: str) -> dict:
    """Pull the portfolio roll-up figures from the first page."""
    out: dict = {}

    m = re.search(r"your portfolio value:\s*\$?([\d,]+\.\d+)", text, re.IGNORECASE)
    if not m:
        m = re.search(r"ending portfolio value\s*\*{0,2}\s*\$?([\d,]+\.\d+)", text, re.IGNORECASE)
    out["total_value"] = _amt(m.group(1)) if m else None

    # Beginning value: '-' on a first-ever statement, otherwise a number.
    m = re.search(r"beginning portfolio value\w?\s+(\S+)", text, re.IGNORECASE)
    out["prev_value"] = _amt(m.group(1)) if m else None
    if out["prev_value"] is None:
        out["prev_value"] = 0.0

    m = re.search(r"\badditions\s+(-?[\d,]+\.\d+)", text, re.IGNORECASE)
    additions = _amt(m.group(1)) if m else 0.0
    m = re.search(r"\bsubtractions\s+(-?[\d,]+\.\d+)", text, re.IGNORECASE)
    subtractions = _amt(m.group(1)) if m else 0.0
    out["net_deposits"] = round((additions or 0.0) + (subtractions or 0.0), 2)

    m = re.search(r"change in investment value\s*\*?\s+(-?[\d,]+\.\d+)", text, re.IGNORECASE)
    out["market_gain"] = _amt(m.group(1)) if m else None

    return out


# A holdings data line, e.g.:
#   "ALPHABET INC CAP STK CL A (GOOGL) unavailable 1.434 $357.3700 $512.46 $499.72 $12.74 $1.26"
#   "FIDELITY GOVERNMENT MONEY unavailable 2,422.190 $1.0000 $2,422.19 not applicable ..."
# Anchor: <beginning MV = 'unavailable' or a number> <qty> <price> <market value>.
_HOLDING_RE = re.compile(
    r"^(?P<name>.+?)\s+"
    r"(?:unavailable|[\d,]+\.\d+)\s+"      # beginning market value
    r"(?P<qty>[\d,]+\.\d+)\s+"             # quantity
    r"\$?(?P<price>[\d,]+\.\d+)\s+"        # price per unit
    r"\$?(?P<mv>[\d,]+\.\d+)\b"            # ending market value
    r"(?P<rest>.*)$"
)

_SYMBOL_RE = re.compile(r"\(([A-Z]{1,6})\)")
# A clean word for name continuation: letters only (drops rates, dates, CUSIPs, dashes).
_NAME_WORD_RE = re.compile(r"[A-Za-z][A-Za-z.&/'-]*$")
# Boilerplate tokens that leak in from wrapped subtotal rows — never part of a name.
_NAME_STOPWORDS = {"unavailable", "not", "applicable"}


def _clean_name(prefix: str, continuations: list[str]) -> str:
    name = _SYMBOL_RE.sub("", prefix).strip()
    extra = []
    for cont in continuations:
        for tok in cont.split():
            tok = _SYMBOL_RE.sub("", tok).strip()
            if tok and _NAME_WORD_RE.fullmatch(tok) and tok.lower() not in _NAME_STOPWORDS:
                extra.append(tok)
    if extra:
        name = f"{name} {' '.join(extra)}".strip()
    return re.sub(r"\s+", " ", name)


def _extract_holdings(pdf) -> list[dict]:
    holdings: list[dict] = []
    account = None
    asset_class = None
    in_holdings = False
    pending: Optional[dict] = None
    cont: list[str] = []

    def finalize():
        nonlocal pending, cont
        if pending:
            pending["name"] = _clean_name(pending["_prefix"], cont)
            sym = _SYMBOL_RE.search(pending["_prefix"] + " " + " ".join(cont))
            pending["symbol"] = sym.group(1) if sym else None
            del pending["_prefix"]
            holdings.append(pending)
        pending = None
        cont = []

    for page in pdf.pages:
        text = page.extract_text() or ""
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            norm = line.lower()

            # Which account are we inside?
            if "roth ira" in norm:
                account = "Roth IRA"
            elif re.search(r"-\s*individual\b", norm):
                account = "Individual"

            # Holdings vs Activity page sections.
            if norm == "holdings":
                in_holdings = True
                asset_class = None
                finalize()
                continue
            if norm in ("activity", "account summary", "estimated cash flow",
                        "additional information and endnotes"):
                in_holdings = False
                asset_class = None
                finalize()
                continue

            if not in_holdings:
                continue

            # Section headers within a Holdings page.
            if norm.startswith("core account"):
                finalize(); asset_class = "cash"; continue
            if norm.startswith("exchange traded products") or norm == "equity etps":
                finalize(); asset_class = "etp"; continue
            if norm.startswith("stocks") or norm == "common stock":
                finalize(); asset_class = "equity"; continue
            if norm == "other":
                finalize(); asset_class = "fixed_income"; continue

            # A "Total ..." line closes the current section's holdings.
            if norm.startswith("total "):
                finalize()
                continue

            if asset_class is None:
                continue

            m = _HOLDING_RE.match(line)
            if m:
                finalize()
                rest = m.group("rest").strip()
                nums = re.findall(r"-?\$?[\d,]+\.\d+", rest)
                cost = _amt(nums[0]) if len(nums) >= 1 else None
                gl = _amt(nums[1]) if len(nums) >= 2 else None
                pending = {
                    "_prefix":      m.group("name").strip(),
                    "account":      account or "Unknown",
                    "asset_class":  asset_class,
                    "symbol":       None,
                    "name":         m.group("name").strip(),
                    "quantity":     _amt(m.group("qty")),
                    "price":        _amt(m.group("price")),
                    "market_value": _amt(m.group("mv")),
                    "cost_basis":   cost,
                    "unrealized_gl": gl if asset_class != "cash" else 0.0,
                }
                continue

            # Otherwise it's a name-continuation line for the pending holding.
            if pending is not None:
                cont.append(line)

    finalize()
    return holdings


def parse_fidelity(filepath: str, filename: str) -> Optional[dict]:
    """
    Parse a Fidelity Investment Report PDF.
    Returns None if the file is not a Fidelity statement.
    """
    with pdfplumber.open(filepath) as pdf:
        if not is_fidelity(pdf):
            return None

        summary_text = "\n".join(
            (page.extract_text() or "") for page in pdf.pages[:4]
        )
        statement_date = _extract_date(summary_text)
        summary = _extract_summary(summary_text)
        holdings = _extract_holdings(pdf)

    total_value = summary.get("total_value")
    # Cash = money-market/core positions; equity = everything else.
    cash_value = round(
        sum(h["market_value"] or 0 for h in holdings if h["asset_class"] == "cash"), 2
    ) if holdings else None
    equity_value = (
        round(total_value - cash_value, 2)
        if total_value is not None and cash_value is not None else None
    )

    market_gain = summary.get("market_gain")
    if market_gain is None and total_value is not None and summary.get("prev_value") is not None:
        market_gain = round(
            total_value - summary["prev_value"] - (summary.get("net_deposits") or 0), 2
        )

    return {
        "statement_date": statement_date,
        "filename":       filename,
        "total_value":    total_value,
        "prev_value":     summary.get("prev_value"),
        "cash_value":     cash_value,
        "equity_value":   equity_value,
        "net_deposits":   summary.get("net_deposits"),
        "market_gain":    market_gain,
        "holdings":       holdings,
    }
