import os
import calendar
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import get_conn, init_db
from categorizer import categorize, infer_tx_type, ALL_CATEGORIES, CATEGORY_COLORS
from parsers.chase_pdf import parse_statement
from parsers.jpmorgan_pdf import is_jpmorgan, parse_jpmorgan
from parsers.capitalone_pdf import is_capitalone_savings, parse_capitalone_savings
from advice import generate_advice

app = FastAPI(title="Finance Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATEMENTS_DIR = Path(__file__).parent.parent / "data" / "statements"


@app.on_event("startup")
def startup():
    init_db()
    STATEMENTS_DIR.mkdir(parents=True, exist_ok=True)
    _scan_statements()


# ── month math helpers ────────────────────────────────────────────────────────

def _month_add(month: str, n: int) -> str:
    """Return YYYY-MM + n calendar months."""
    y, m = map(int, month.split("-"))
    m += n
    y += (m - 1) // 12
    m = ((m - 1) % 12) + 1
    return f"{y:04d}-{m:02d}"


# ── folder scan ───────────────────────────────────────────────────────────────

def _friendly_filename(primary_month: str, account_type: str, broker: str = "Chase") -> str:
    """Build a human-friendly filename."""
    year, mon = primary_month.split("-")
    mon_abbr = calendar.month_abbr[int(mon)]
    if broker == "JPMorgan":
        return f"{year}-{mon_abbr}-Brokerage-JPMorgan.pdf"
    if broker == "CapitalOne":
        return f"{year}-{mon_abbr}-Savings-CapitalOne.pdf"
    kind = "Credit" if account_type == "credit" else "Checking"
    return f"{year}-{mon_abbr}-{kind}-Chase.pdf"


def _rename_pdf(pdf_path, new_name: str):
    """Rename PDF to new_name (with collision handling). Returns final filename."""
    new_path = STATEMENTS_DIR / new_name
    if new_path.exists() and new_path != pdf_path:
        stem = new_name[:-4]
        counter = 2
        while new_path.exists():
            new_name = f"{stem}-{counter}.pdf"
            new_path = STATEMENTS_DIR / new_name
            counter += 1
    if new_path != pdf_path:
        pdf_path.rename(new_path)
    return new_name


def _scan_statements() -> dict:
    pdfs = sorted(STATEMENTS_DIR.glob("*.pdf"))
    imported, skipped, errors = [], [], []

    with get_conn() as conn:
        known_statements = {row["filename"] for row in conn.execute("SELECT filename FROM statements")}
        known_portfolio  = {row["filename"] for row in conn.execute("SELECT filename FROM portfolio_snapshots")}
        known_balances   = {row["filename"] for row in conn.execute("SELECT filename FROM account_balances")}
    known = known_statements | known_portfolio | known_balances

    for pdf_path in pdfs:
        filename = pdf_path.name
        if filename in known:
            skipped.append(filename)
            continue

        # ── Detect PDF type (open once) ──────────────────────────────────────
        try:
            import pdfplumber
            with pdfplumber.open(str(pdf_path)) as _pdf:
                _is_jpm = is_jpmorgan(_pdf)
                _is_c1  = is_capitalone_savings(_pdf)
        except Exception as e:
            errors.append({"file": filename, "error": str(e)})
            continue

        if _is_c1:
            try:
                c1 = parse_capitalone_savings(str(pdf_path), filename)
            except Exception as e:
                errors.append({"file": filename, "error": f"CapitalOne parse error: {e}"})
                continue

            if not c1 or c1.get("balance") is None:
                errors.append({"file": filename, "error": "CapitalOne: no balance found"})
                continue

            primary_month = c1["statement_date"] or filename[:7]
            filename = _rename_pdf(pdf_path, _friendly_filename(primary_month, "savings", "CapitalOne"))
            with get_conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO account_balances"
                    "(statement_date,account_type,filename,balance) VALUES (?,?,?,?)",
                    (primary_month, "savings", filename, c1["balance"]),
                )
            imported.append({
                "file": filename, "month": primary_month,
                "type": "savings", "balance": c1["balance"],
            })
            continue

        if _is_jpm:
            try:
                result = parse_jpmorgan(str(pdf_path), filename)
            except Exception as e:
                errors.append({"file": filename, "error": f"JPMorgan parse error: {e}"})
                continue

            if not result or result.get("total_value") is None:
                errors.append({"file": filename, "error": "JPMorgan: no portfolio value found"})
                continue

            primary_month = result["statement_date"] or filename[:7]
            filename = _rename_pdf(pdf_path, _friendly_filename(primary_month, "brokerage", "JPMorgan"))
            result["filename"] = filename

            with get_conn() as conn:
                cur = conn.execute(
                    "INSERT OR REPLACE INTO portfolio_snapshots"
                    "(statement_date,filename,total_value,prev_value,cash_value,"
                    "equity_value,net_deposits,market_gain) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        result["statement_date"], filename,
                        result["total_value"], result["prev_value"],
                        result["cash_value"], result["equity_value"],
                        result["net_deposits"], result["market_gain"],
                    ),
                )
                snap_id = cur.lastrowid
                # Remove old holdings for this snapshot (covers INSERT OR REPLACE case)
                conn.execute("DELETE FROM portfolio_holdings WHERE snapshot_id=?", (snap_id,))
                for h in result.get("holdings", []):
                    conn.execute(
                        "INSERT INTO portfolio_holdings"
                        "(snapshot_id,account,asset_class,symbol,name,"
                        "quantity,price,market_value,cost_basis,unrealized_gl)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (
                            snap_id, h["account"], h["asset_class"], h["symbol"], h["name"],
                            h["quantity"], h["price"], h["market_value"],
                            h["cost_basis"], h["unrealized_gl"],
                        ),
                    )

            imported.append({
                "file": filename, "month": primary_month,
                "type": "brokerage", "holdings": len(result.get("holdings", [])),
            })
            continue

        # ── Chase checking / credit card ─────────────────────────────────────
        try:
            account_type, raw_txns, pdf_closing_month, ending_balance = parse_statement(
                str(pdf_path), filename
            )
        except Exception as e:
            errors.append({"file": filename, "error": str(e)})
            continue

        if not raw_txns:
            errors.append({"file": filename, "error": "No transactions found"})
            continue

        if account_type == "credit" and pdf_closing_month:
            primary_month = pdf_closing_month
        else:
            primary_month = _most_common_month(raw_txns)

        filename = _rename_pdf(pdf_path, _friendly_filename(primary_month, account_type))

        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO statements(filename, account_type, month) VALUES (?,?,?)",
                (filename, account_type, primary_month),
            )
            stmt_id = cur.lastrowid

            rows = []
            for t in raw_txns:
                cat = categorize(t["description"])
                tx_type = infer_tx_type(t["description"], t["amount"], account_type)
                if tx_type == "payment":
                    continue
                if tx_type == "transfer" and account_type == "checking":
                    desc_lc = t["description"].lower()
                    if any(kw in desc_lc for kw in [
                        "chase credit crd", "payment to chase card", "autopay",
                    ]):
                        continue
                rows.append((
                    stmt_id, t["date"], t["description"], t["amount"],
                    cat, 0, tx_type, t["date"][:7], 0, None, 0, None, 0,
                ))

            conn.executemany(
                "INSERT INTO transactions"
                "(statement_id,date,description,amount,category,is_override,tx_type,month,"
                "is_capital,capital_note,is_amortized,amortization_months,is_excluded)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                rows,
            )

            # Store checking ending balance for net worth calculation
            # (credit card skipped — paid in full each month, not a meaningful liability)
            if ending_balance is not None and account_type == "checking":
                conn.execute(
                    "INSERT OR REPLACE INTO account_balances"
                    "(statement_date,account_type,filename,balance) VALUES (?,?,?,?)",
                    (primary_month, "checking", filename, ending_balance),
                )

        imported.append({
            "file": filename, "month": primary_month,
            "count": len(raw_txns), "type": account_type,
        })

    return {"imported": imported, "skipped": skipped, "errors": errors}


@app.post("/api/scan")
def scan():
    return _scan_statements()


def _most_common_month(txns: list[dict]) -> str:
    from collections import Counter
    return Counter(t["date"][:7] for t in txns).most_common(1)[0][0]


# ── months ────────────────────────────────────────────────────────────────────

@app.get("/api/months")
def list_months():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT month FROM transactions ORDER BY month DESC"
        ).fetchall()
    return [r["month"] for r in rows]


# ── transactions ──────────────────────────────────────────────────────────────

@app.get("/api/transactions")
def list_transactions(
    month: Optional[str] = None,
    category: Optional[str] = None,
    tx_type: Optional[str] = None,
    is_excluded: Optional[int] = None,
    limit: int = 500,
    offset: int = 0,
):
    filters, params = [], []
    if month:
        filters.append("month=?"); params.append(month)
    if category:
        filters.append("category=?"); params.append(category)
    if tx_type:
        filters.append("tx_type=?"); params.append(tx_type)
    if is_excluded is not None:
        filters.append("is_excluded=?"); params.append(is_excluded)

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    params += [limit, offset]

    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM transactions {where} ORDER BY date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total = conn.execute(
            f"SELECT COUNT(*) FROM transactions {where}",
            params[:-2],
        ).fetchone()[0]

    return {"total": total, "items": [dict(r) for r in rows]}


class TxUpdate(BaseModel):
    category: Optional[str] = None
    tx_type: Optional[str] = None
    is_capital: Optional[int] = None
    capital_note: Optional[str] = None
    is_amortized: Optional[int] = None
    amortization_months: Optional[int] = None
    is_excluded: Optional[int] = None


@app.patch("/api/transactions/{tx_id}")
def update_transaction(tx_id: int, body: TxUpdate):
    if body.category is not None and body.category not in ALL_CATEGORIES:
        raise HTTPException(400, f"Unknown category: {body.category}")
    if body.tx_type is not None and body.tx_type not in ("income", "expense", "transfer", "payment"):
        raise HTTPException(400, f"Unknown tx_type: {body.tx_type}")

    sets, params = [], []
    if body.tx_type is not None:
        sets.append("tx_type=?")
        params.append(body.tx_type)
    if body.category is not None:
        sets += ["category=?", "is_override=1"]
        params.append(body.category)
    if body.is_capital is not None:
        sets.append("is_capital=?")
        params.append(body.is_capital)
        if body.is_capital == 1:
            sets += ["is_amortized=0", "amortization_months=NULL"]
    if body.capital_note is not None:
        sets.append("capital_note=?")
        params.append(body.capital_note)
    if body.is_amortized is not None:
        sets.append("is_amortized=?")
        params.append(body.is_amortized)
        if body.is_amortized == 1:
            sets += ["is_capital=0"]  # mutually exclusive
    if body.amortization_months is not None:
        sets.append("amortization_months=?")
        params.append(body.amortization_months)
    if body.is_excluded is not None:
        sets.append("is_excluded=?")
        params.append(body.is_excluded)

    if not sets:
        return {"ok": True}

    params.append(tx_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE transactions SET {', '.join(sets)} WHERE id=?", params)
    return {"ok": True}


# ── amortization helpers ──────────────────────────────────────────────────────

def _get_amort_slices(month: str, conn) -> list[dict]:
    """
    For a given month, return all amortization slices from transactions
    (in any month) whose amortization window covers this month.
    """
    rows = conn.execute(
        "SELECT * FROM transactions WHERE is_amortized=1 AND amortization_months IS NOT NULL"
    ).fetchall()
    slices = []
    for row in rows:
        tx = dict(row)
        start = tx["month"]
        n = tx["amortization_months"]
        end = _month_add(start, n)
        if start <= month < end:
            slices.append({
                "source_id":          tx["id"],
                "date":               tx["date"],
                "description":        tx["description"],
                "category":           tx["category"],
                "slice_amount":       round(abs(tx["amount"]) / n, 2),
                "total_amount":       abs(tx["amount"]),
                "amortization_months": n,
                "start_month":        start,
                "end_month":          end,
            })
    return slices


# ── dashboard ─────────────────────────────────────────────────────────────────

@app.get("/api/dashboard/{month}")
def dashboard(month: str):
    with get_conn() as conn:
        txns = [dict(r) for r in conn.execute(
            "SELECT * FROM transactions WHERE month=?", (month,)
        ).fetchall()]
        amort_slices = _get_amort_slices(month, conn)

    return _build_summary(month, txns, amort_slices)


def _build_summary(month: str, txns: list[dict], amort_slices: list[dict] = None) -> dict:
    # Partition transactions
    expenses    = [t for t in txns if t["tx_type"] == "expense"
                   and not t.get("is_capital") and not t.get("is_amortized")
                   and not t.get("is_excluded")]
    income      = [t for t in txns if t["tx_type"] == "income" and not t.get("is_excluded")]
    capitals    = [t for t in txns if t.get("is_capital")]
    amortized   = [t for t in txns if t.get("is_amortized") and t["tx_type"] == "expense"]
    excluded    = [t for t in txns if t.get("is_excluded")]

    total_expense = sum(abs(t["amount"]) for t in expenses)
    total_income  = sum(t["amount"] for t in income)

    by_category: dict[str, float] = {}
    for t in expenses:
        by_category[t["category"]] = by_category.get(t["category"], 0) + abs(t["amount"])

    # Amortized slices are tracked but NOT added to expense totals

    net_savings = total_income - total_expense
    top5 = sorted(expenses, key=lambda t: abs(t["amount"]), reverse=True)[:5]

    return {
        "month":               month,
        "total_income":        round(total_income, 2),
        "total_expense":       round(total_expense, 2),
        "net_savings":         round(net_savings, 2),
        "by_category":         {k: round(v, 2) for k, v in by_category.items()},
        "category_colors":     CATEGORY_COLORS,
        "top_transactions":    top5,
        "capital_expenses":    [dict(t) for t in capitals],
        "amortized_items":     [dict(t) for t in amortized],
        "amort_slices":        amort_slices or [],
        "excluded_items":      [dict(t) for t in excluded],
        "transaction_count":   len(txns),
    }


# ── averages (all months) ─────────────────────────────────────────────────────

@app.get("/api/averages")
def averages():
    with get_conn() as conn:
        months = [r["month"] for r in conn.execute(
            "SELECT DISTINCT month FROM transactions ORDER BY month"
        ).fetchall()]

    if not months:
        return {"months_count": 0}

    summaries = []
    for m in months:
        with get_conn() as conn:
            txns = [dict(r) for r in conn.execute(
                "SELECT * FROM transactions WHERE month=?", (m,)
            ).fetchall()]
            amort_slices = _get_amort_slices(m, conn)
        summaries.append(_build_summary(m, txns, amort_slices))

    n = len(summaries)
    avg_income  = sum(s["total_income"]  for s in summaries) / n
    avg_expense = sum(s["total_expense"] for s in summaries) / n
    avg_savings = sum(s["net_savings"]   for s in summaries) / n

    cat_totals: dict[str, list[float]] = {}
    for s in summaries:
        for cat, amt in s["by_category"].items():
            cat_totals.setdefault(cat, []).append(amt)
    avg_by_category = {
        cat: round(sum(vals) / n, 2)
        for cat, vals in cat_totals.items()
    }

    return {
        "months_count":    n,
        "months":          months,
        "avg_income":      round(avg_income, 2),
        "avg_expense":     round(avg_expense, 2),
        "avg_savings":     round(avg_savings, 2),
        "avg_by_category": avg_by_category,
        "category_colors": CATEGORY_COLORS,
        "per_month":       summaries,
    }


# ── settings ──────────────────────────────────────────────────────────────────

@app.get("/api/settings")
def get_settings():
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


class SettingsUpdate(BaseModel):
    savings_goal: Optional[float] = None


@app.put("/api/settings")
def update_settings(body: SettingsUpdate):
    with get_conn() as conn:
        if body.savings_goal is not None:
            conn.execute(
                "INSERT OR REPLACE INTO settings(key,value) VALUES ('savings_goal',?)",
                (str(body.savings_goal),),
            )
    return {"ok": True}


# ── advice ────────────────────────────────────────────────────────────────────

@app.get("/api/advice/{month}")
def get_advice(month: str):
    with get_conn() as conn:
        settings = {r["key"]: r["value"] for r in conn.execute(
            "SELECT key,value FROM settings"
        ).fetchall()}
        savings_goal = float(settings.get("savings_goal", 1000))

        txns = [dict(r) for r in conn.execute(
            "SELECT * FROM transactions WHERE month=?", (month,)
        ).fetchall()]
        amort_slices = _get_amort_slices(month, conn)
        summary = _build_summary(month, txns, amort_slices)

        all_months = [r["month"] for r in conn.execute(
            "SELECT DISTINCT month FROM transactions WHERE month<? ORDER BY month DESC LIMIT 3",
            (month,),
        ).fetchall()]

        history = []
        for m in reversed(all_months):
            m_txns = [dict(r) for r in conn.execute(
                "SELECT * FROM transactions WHERE month=?", (m,)
            ).fetchall()]
            m_slices = _get_amort_slices(m, conn)
            history.append(_build_summary(m, m_txns, m_slices))

    return generate_advice(summary, history, savings_goal)


# ── statements ────────────────────────────────────────────────────────────────

@app.get("/api/statements")
def list_statements():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM statements ORDER BY month DESC").fetchall()
    known = {r["filename"] for r in rows}
    pending = [p.name for p in STATEMENTS_DIR.glob("*.pdf") if p.name not in known]
    return {"statements": [dict(r) for r in rows], "pending": pending}


@app.delete("/api/statements/{stmt_id}")
def delete_statement(stmt_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT filename FROM statements WHERE id=?", (stmt_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Statement not found")
        conn.execute("DELETE FROM transactions WHERE statement_id=?", (stmt_id,))
        conn.execute("DELETE FROM statements WHERE id=?", (stmt_id,))
    return {"ok": True}


# ── categories ────────────────────────────────────────────────────────────────

@app.get("/api/categories")
def list_categories():
    return {"categories": ALL_CATEGORIES, "colors": CATEGORY_COLORS}


# ── net worth ─────────────────────────────────────────────────────────────────

@app.get("/api/networth")
def get_networth():
    with get_conn() as conn:
        snapshots = [dict(r) for r in conn.execute(
            "SELECT * FROM portfolio_snapshots ORDER BY statement_date"
        ).fetchall()]

        balances = conn.execute(
            "SELECT * FROM account_balances ORDER BY statement_date"
        ).fetchall()

    # Build balance lookup: {(date, account_type) -> balance}
    balance_map: dict[tuple, float] = {}
    for b in balances:
        balance_map[(b["statement_date"], b["account_type"])] = b["balance"]

    # Gather all months across all tables
    all_months = sorted({
        s["statement_date"] for s in snapshots
    } | {
        b["statement_date"] for b in balances
    })

    # Current snapshot with asset class breakdown for pie chart
    current_assets = None
    if snapshots:
        s = snapshots[-1]
        current_assets = {
            "portfolio_equity": s["equity_value"],
            "portfolio_cash":   s["cash_value"],
            "snapshot_date":    s["statement_date"],
        }

    timeline = []
    for month in all_months:
        portfolio = next((s["total_value"] for s in snapshots if s["statement_date"] == month), None)
        checking  = balance_map.get((month, "checking"))
        savings   = balance_map.get((month, "savings"))

        components = [v for v in [portfolio, checking, savings] if v is not None]
        net_worth  = round(sum(components), 2) if components else None

        timeline.append({
            "date":      month,
            "portfolio": portfolio,
            "checking":  checking,
            "savings":   savings,
            "net_worth": net_worth,
        })

    # Current snapshot holdings
    current_holdings: list[dict] = []
    current_snapshot: Optional[dict] = None
    if snapshots:
        latest = snapshots[-1]
        current_snapshot = latest
        with get_conn() as conn:
            current_holdings = [dict(r) for r in conn.execute(
                "SELECT * FROM portfolio_holdings WHERE snapshot_id=? ORDER BY market_value DESC",
                (latest["id"],),
            ).fetchall()]

    # Latest balance for each account type (for pie chart)
    latest_checking = next((t["checking"] for t in reversed(timeline) if t["checking"] is not None), None)
    latest_savings  = next((t["savings"]  for t in reversed(timeline) if t["savings"]  is not None), None)

    return {
        "timeline":         timeline,
        "current_snapshot": current_snapshot,
        "current_holdings": current_holdings,
        "current_assets":   current_assets,
        "latest_checking":  latest_checking,
        "latest_savings":   latest_savings,
    }


@app.delete("/api/portfolio/{snapshot_id}")
def delete_portfolio_snapshot(snapshot_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM portfolio_snapshots WHERE id=?", (snapshot_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Snapshot not found")
        conn.execute("DELETE FROM portfolio_holdings WHERE snapshot_id=?", (snapshot_id,))
        conn.execute("DELETE FROM portfolio_snapshots WHERE id=?", (snapshot_id,))
    return {"ok": True}
