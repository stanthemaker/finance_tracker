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
                tx_type       TEXT NOT NULL,       -- 'income' | 'expense' | 'transfer'
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

        # content_hash: sha256 of the source PDF, used to reject duplicate
        # re-uploads of the same file (even under a different filename).
        for tbl in ("statements", "portfolio_snapshots", "account_balances"):
            tcols = {row[1] for row in conn.execute(f"PRAGMA table_info({tbl})")}
            if "content_hash" not in tcols:
                conn.execute(f"ALTER TABLE {tbl} ADD COLUMN content_hash TEXT")

        # portfolio_snapshots originally had UNIQUE(statement_date), which assumed a
        # single brokerage. With more than one broker (J.P. Morgan + Fidelity) reporting
        # in the same month, that constraint is too strict. Rebuild the table with a
        # `broker` column and UNIQUE(statement_date, broker) so each broker keeps its own
        # monthly snapshot. Runs once (guarded on the `broker` column not existing yet).
        ps_cols = {row[1] for row in conn.execute("PRAGMA table_info(portfolio_snapshots)")}
        if "broker" not in ps_cols:
            conn.executescript("""
                CREATE TABLE portfolio_snapshots_new (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    statement_date TEXT,
                    broker         TEXT,
                    filename       TEXT,
                    total_value    REAL,
                    prev_value     REAL,
                    cash_value     REAL,
                    equity_value   REAL,
                    net_deposits   REAL,
                    market_gain    REAL,
                    content_hash   TEXT,
                    UNIQUE(statement_date, broker)
                );
                INSERT INTO portfolio_snapshots_new
                    (id, statement_date, filename, total_value, prev_value, cash_value,
                     equity_value, net_deposits, market_gain, content_hash, broker)
                SELECT id, statement_date, filename, total_value, prev_value, cash_value,
                     equity_value, net_deposits, market_gain, content_hash,
                     CASE WHEN filename LIKE '%Fidelity%' THEN 'Fidelity' ELSE 'JPMorgan' END
                FROM portfolio_snapshots;
                DROP TABLE portfolio_snapshots;
                ALTER TABLE portfolio_snapshots_new RENAME TO portfolio_snapshots;
            """)
