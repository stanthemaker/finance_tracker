import React, { useState, useEffect } from "react";
import { Routes, Route, NavLink } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Transactions from "./pages/Transactions";
import Goals from "./pages/Goals";
import Advice from "./pages/Advice";
import Statements from "./pages/Statements";
import Excluded from "./pages/Excluded";
import NetWorth from "./pages/NetWorth";
import { fetchMonths, scanStatements } from "./api";

export default function App() {
  const [months, setMonths] = useState([]);
  const [activeMonth, setActiveMonth] = useState(null);
  const [newImports, setNewImports] = useState(0);

  const refreshMonths = () =>
    fetchMonths().then((list) => {
      setMonths(list);
      setActiveMonth((prev) => prev ?? list[0] ?? null);
    });

  useEffect(() => {
    // auto-scan on every app open to pick up new PDFs dropped in data/statements/
    scanStatements().then((result) => {
      if (result.imported?.length > 0) {
        setNewImports(result.imported.length);
        refreshMonths();
      } else {
        refreshMonths();
      }
    }).catch(() => refreshMonths());
  }, []);

  const navCls = ({ isActive }) =>
    `px-4 py-2 rounded-md text-sm font-medium transition-colors ${
      isActive ? "bg-indigo-600 text-white" : "text-gray-600 hover:bg-gray-200"
    }`;

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <span className="text-xl font-bold text-indigo-600">💰 Finance Tracker</span>
          <nav className="flex gap-2">
            <NavLink to="/networth"         className={navCls}>Net Worth</NavLink>
            <NavLink to="/"             end className={navCls}>Dashboard</NavLink>
            <NavLink to="/transactions"     className={navCls}>Transactions</NavLink>
            <NavLink to="/goals"            className={navCls}>Goals</NavLink>
            <NavLink to="/advice"           className={navCls}>Advice</NavLink>
            <NavLink to="/statements"       className={navCls}>Statements</NavLink>
            <NavLink to="/excluded"         className={navCls}>Excluded</NavLink>
          </nav>
        </div>
      </header>

      {months.length > 0 && (
        <div className="bg-white border-b border-gray-100 px-4 py-2">
          <div className="max-w-6xl mx-auto flex items-center gap-3">
            <label className="text-sm text-gray-500" htmlFor="month-select">Month:</label>
            <select
              id="month-select"
              value={activeMonth ?? ""}
              onChange={(e) => setActiveMonth(e.target.value)}
              className="text-sm border border-gray-300 rounded px-2 py-1 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-300"
            >
              <option value="average">📊 Average (All Months)</option>
              <option disabled>──────────────</option>
              {months.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
        </div>
      )}

      {newImports > 0 && (
        <div className="bg-green-50 border-b border-green-200 px-4 py-2 text-sm text-green-700 flex items-center justify-between">
          <span>✅ Auto-imported {newImports} new statement{newImports > 1 ? "s" : ""} from <code className="bg-green-100 px-1 rounded">data/statements/</code></span>
          <button onClick={() => setNewImports(0)} className="text-green-400 hover:text-green-600 ml-4">✕</button>
        </div>
      )}

      <main className="flex-1 max-w-6xl mx-auto w-full px-4 py-6">
        <Routes>
          <Route path="/"             element={<Dashboard month={activeMonth} onMonthChange={setActiveMonth} />} />
          <Route path="/transactions" element={<Transactions month={activeMonth} />} />
          <Route path="/goals"        element={<Goals month={activeMonth} />} />
          <Route path="/advice"       element={<Advice month={activeMonth} />} />
          <Route path="/networth"     element={<NetWorth />} />
          <Route path="/statements"   element={<Statements onScanSuccess={refreshMonths} />} />
          <Route path="/excluded"     element={<Excluded />} />
        </Routes>
      </main>
    </div>
  );
}
