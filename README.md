# 💰 Finance Tracker

A local, self-hosted personal finance dashboard. Drop your bank statement PDFs
into a folder and it parses them, categorizes transactions, and gives you
spending breakdowns, net-worth tracking, savings goals, and budgeting advice —
all running on your own machine. No data ever leaves your computer.

## Features

- **Automatic statement parsing** — drop PDFs into `data/statements/` and they're
  imported on app open. Supports:
  - Chase checking & credit card statements
  - J.P. Morgan brokerage statements (portfolio value + holdings)
  - Capital One savings statements (balance)
  - Fidelity brokeage statements
- **Dashboard** — monthly income, expenses, net savings, and spending by category,
  with an "Average (All Months)" view.
- **Transactions** — review, re-categorize, and flag transactions. Mark one-time
  "capital" purchases or amortize large expenses across months.
- **Net Worth** — timeline across brokerage, checking, and savings, plus current
  holdings breakdown.
- **Goals & Advice** — set a monthly savings goal and get automated budgeting advice.

## Tech Stack

| Layer    | Stack                                                   |
| -------- | ------------------------------------------------------- |
| Backend  | Python · FastAPI · Uvicorn · pdfplumber · SQLite         |
| Frontend | React 18 · Vite · Tailwind CSS · Recharts · React Router |

The frontend (port `5173`) proxies `/api` requests to the backend (port `8000`).
Data is stored in a local SQLite database at `data/finance.db`.

## Prerequisites

- **Python** 3.10+
- **Node.js** 18+ (with `npm`)

## Installation

Clone the repo, then set up the backend and frontend.

### 1. Backend (Python)

Create a virtual environment and install dependencies:

```bash
cd backend

# Option A — venv
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Option B — conda (matches start.sh, which expects an env named "finance_tracker")
conda create -n finance_tracker python=3.11 -y
conda activate finance_tracker
pip install -r requirements.txt
```

### 2. Frontend (Node)

```bash
cd frontend
npm install
```

## Running the App

### Quick start (both servers)

From the project root:

```bash
./start.sh
```

This launches the backend and frontend together.

> **Note:** `start.sh` runs the backend via `conda run -n finance_tracker`, so it
> assumes a conda environment named `finance_tracker` (see Option B above). If you
> used a `venv` instead, either edit the `conda run` line in `start.sh` or start
> the two servers manually as shown below.

### Manual start (two terminals)

**Terminal 1 — backend:**

```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Terminal 2 — frontend:**

```bash
cd frontend
npm run dev
```

Then open:

- Frontend UI → **http://localhost:5173**
- Backend API → **http://localhost:8000** (interactive docs at `/docs`)

## Usage

1. Put your statement PDFs into `data/statements/` (the folder is created
   automatically on first run).
2. Open the app — it auto-scans the folder and imports any new statements.
   Files are renamed to a friendly format like `2026-Jan-Checking-Chase.pdf`.
3. Browse the **Dashboard**, adjust categories in **Transactions**, and set your
   goal under **Goals**.

You can also trigger a re-scan any time from the **Statements** page.

## Project Structure

```
finance_tracker/
├── backend/              # FastAPI app
│   ├── main.py           # API routes + statement scanning
│   ├── database.py       # SQLite schema & connection
│   ├── categorizer.py    # transaction categorization
│   ├── advice.py         # budgeting advice generation
│   ├── parsers/          # per-bank PDF parsers
│   └── requirements.txt
├── frontend/             # React + Vite app
│   └── src/pages/        # Dashboard, Transactions, NetWorth, ...
├── data/                 # SQLite DB + statement PDFs (git-ignored)
└── start.sh              # launches backend + frontend
```

## Notes

- Your financial data — the SQLite database and all statement PDFs under `data/` —
  is **git-ignored** and stays local.
- The database is created automatically on first backend start; no migration step
  is needed.
