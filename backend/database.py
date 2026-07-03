import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "finance.db"


def get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS statements (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                filename   TEXT NOT NULL,
                account_type TEXT NOT NULL,  -- 'checking' | 'credit'
                month      TEXT NOT NULL,    -- 'YYYY-MM'
                uploaded_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                statement_id  INTEGER REFERENCES statements(id) ON DELETE CASCADE,
                date          TEXT NOT NULL,       -- 'YYYY-MM-DD'
                description   TEXT NOT NULL,
                amount        REAL NOT NULL,       -- negative = expense, positive = income
                category      TEXT NOT NULL,
                is_override   INTEGER DEFAULT 0,   -- 1 if user manually set category
                tx_type       TEXT NOT NULL,       -- 'income' | 'expense' | 'transfer' | 'payment'
                month         TEXT NOT NULL,       -- 'YYYY-MM'
                is_capital    INTEGER DEFAULT 0,   -- 1 = big one-time purchase, excluded from totals
                capital_note  TEXT DEFAULT NULL    -- optional label e.g. "MacBook"
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            INSERT OR IGNORE INTO settings(key, value) VALUES ('savings_goal', '1000');
            INSERT OR IGNORE INTO settings(key, value) VALUES ('currency', 'USD');
        """)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                statement_date TEXT UNIQUE,
                filename       TEXT,
                total_value    REAL,
                prev_value     REAL,
                cash_value     REAL,
                equity_value   REAL,
                net_deposits   REAL,
                market_gain    REAL
            );

            CREATE TABLE IF NOT EXISTS portfolio_holdings (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id    INTEGER REFERENCES portfolio_snapshots(id) ON DELETE CASCADE,
                account        TEXT,
                asset_class    TEXT,
                symbol         TEXT,
                name           TEXT,
                quantity       REAL,
                price          REAL,
                market_value   REAL,
                cost_basis     REAL,
                unrealized_gl  REAL
            );

            CREATE TABLE IF NOT EXISTS account_balances (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                statement_date TEXT,
                account_type   TEXT,
                filename       TEXT,
                balance        REAL,
                UNIQUE(statement_date, account_type)
            );
        """)

        # migrations for columns added after initial release
        cols = {row[1] for row in conn.execute("PRAGMA table_info(transactions)")}
        if "is_capital" not in cols:
            conn.execute("ALTER TABLE transactions ADD COLUMN is_capital INTEGER DEFAULT 0")
        if "capital_note" not in cols:
            conn.execute("ALTER TABLE transactions ADD COLUMN capital_note TEXT DEFAULT NULL")
        if "is_amortized" not in cols:
            conn.execute("ALTER TABLE transactions ADD COLUMN is_amortized INTEGER DEFAULT 0")
        if "amortization_months" not in cols:
            conn.execute("ALTER TABLE transactions ADD COLUMN amortization_months INTEGER DEFAULT NULL")
        if "is_excluded" not in cols:
            conn.execute("ALTER TABLE transactions ADD COLUMN is_excluded INTEGER DEFAULT 0")
