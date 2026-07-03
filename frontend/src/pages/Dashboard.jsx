import React, { useEffect, useState } from "react";
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend,
} from "recharts";
import { fetchDashboard, fetchAverages } from "../api";

const fmt = (n) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n ?? 0);

function StatCard({ label, value, sub, color = "indigo" }) {
  const styles = {
    indigo: "bg-indigo-50 border-indigo-200 text-indigo-700",
    green:  "bg-green-50  border-green-200  text-green-700",
    red:    "bg-red-50    border-red-200    text-red-700",
    amber:  "bg-amber-50  border-amber-200  text-amber-700",
  };
  return (
    <div className={`rounded-xl border p-4 ${styles[color]}`}>
      <p className="text-sm font-medium opacity-70">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
      {sub && <p className="text-xs mt-1 opacity-60">{sub}</p>}
    </div>
  );
}

// ── Average view ──────────────────────────────────────────────────────────────

function AverageView({ avgs }) {
  if (!avgs || avgs.months_count === 0)
    return <p className="text-gray-400 py-10 text-center">No data yet.</p>;

  const pieData = Object.entries(avgs.avg_by_category)
    .sort((a, b) => b[1] - a[1])
    .map(([name, value]) => ({ name, value, color: avgs.category_colors[name] || "#ccc" }));

  const barData = (avgs.per_month || []).map((d) => ({
    month: d.month,
    Income:   d.total_income,
    Expenses: d.total_expense,
    Savings:  Math.max(d.net_savings, 0),
  }));

  return (
    <div className="space-y-6">
      <div className="flex items-baseline gap-3">
        <h1 className="text-2xl font-bold text-gray-800">All-Time Average</h1>
        <span className="text-sm text-gray-400">across {avgs.months_count} months</span>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Avg Monthly Income"   value={fmt(avgs.avg_income)}  color="green" />
        <StatCard label="Avg Monthly Spending" value={fmt(avgs.avg_expense)} color="red" />
        <StatCard
          label="Avg Monthly Savings"
          value={fmt(avgs.avg_savings)}
          color={avgs.avg_savings >= 0 ? "indigo" : "red"}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h2 className="font-semibold text-gray-700 mb-3">Avg Spending by Category</h2>
          {pieData.length === 0 ? (
            <p className="text-gray-400 text-sm">No expense data.</p>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name"
                  cx="50%" cy="50%" outerRadius={90}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  labelLine={false}
                >
                  {pieData.map((e) => <Cell key={e.name} fill={e.color} />)}
                </Pie>
                <Tooltip formatter={(v) => fmt(v)} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h2 className="font-semibold text-gray-700 mb-3">Month-by-Month Trend</h2>
          {barData.length < 2 ? (
            <p className="text-gray-400 text-sm">Need at least 2 months.</p>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => fmt(v)} />
                <Legend />
                <Bar dataKey="Income"   fill="#4CAF50" radius={[3,3,0,0]} />
                <Bar dataKey="Expenses" fill="#F44336" radius={[3,3,0,0]} />
                <Bar dataKey="Savings"  fill="#2196F3" radius={[3,3,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* per-category breakdown table */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <h2 className="font-semibold text-gray-700 mb-3">Average Monthly Spend by Category</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {Object.entries(avgs.avg_by_category)
            .sort((a, b) => b[1] - a[1])
            .map(([cat, amt]) => (
              <div key={cat} className="flex items-center gap-2">
                <span
                  className="w-3 h-3 rounded-full flex-shrink-0"
                  style={{ background: avgs.category_colors[cat] || "#ccc" }}
                />
                <span className="text-sm text-gray-600 flex-1">{cat}</span>
                <span className="text-sm font-medium text-gray-800">{fmt(amt)}</span>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}

// ── Month view ────────────────────────────────────────────────────────────────

export default function Dashboard({ month, onMonthChange }) {
  const [data, setData]   = useState(null);
  const [avgs, setAvgs]   = useState(null);
  const [allData, setAllData] = useState([]);

  useEffect(() => {
    fetchAverages().then((a) => {
      setAvgs(a);
      if (a.months?.length > 0) {
        Promise.all(a.months.slice(-6).map(fetchDashboard)).then(setAllData);
      }
    });
  }, []);

  useEffect(() => {
    if (!month || month === "average") { setData(null); return; }
    fetchDashboard(month).then(setData);
  }, [month]);

  if (!month)
    return (
      <div className="text-center py-20 text-gray-400">
        <p className="text-5xl mb-4">📂</p>
        <p className="text-lg">
          Drop Chase PDFs into{" "}
          <code className="bg-gray-100 px-1 rounded">data/statements/</code> then open
          the app — it auto-imports on startup.
        </p>
      </div>
    );

  if (month === "average") return <AverageView avgs={avgs} />;

  if (!data) return <p className="text-gray-400 py-10 text-center">Loading…</p>;

  const pieData = Object.entries(data.by_category).map(([name, value]) => ({
    name, value, color: data.category_colors[name] || "#ccc",
  }));

  const barData = allData.map((d) => ({
    month: d.month,
    Income:   d.total_income,
    Expenses: d.total_expense,
    Savings:  Math.max(d.net_savings, 0),
  }));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Overview — {month}</h1>

      {/* summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Income"       value={fmt(data.total_income)}  color="green" />
        <StatCard label="Spending"     value={fmt(data.total_expense)} color="red" />
        <StatCard
          label="Net Savings"
          value={fmt(data.net_savings)}
          color={data.net_savings >= 0 ? "indigo" : "red"}
        />
        <StatCard label="Transactions" value={data.transaction_count} sub="this month" color="amber" />
      </div>


      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h2 className="font-semibold text-gray-700 mb-3">Spending by Category</h2>
          {pieData.length === 0 ? (
            <p className="text-gray-400 text-sm">No expense data.</p>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name"
                  cx="50%" cy="50%" outerRadius={90}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  labelLine={false}
                >
                  {pieData.map((e) => <Cell key={e.name} fill={e.color} />)}
                </Pie>
                <Tooltip formatter={(v) => fmt(v)} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h2 className="font-semibold text-gray-700 mb-3">Monthly Trend</h2>
          {barData.length < 2 ? (
            <p className="text-gray-400 text-sm">Need at least 2 months.</p>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart
                data={barData}
                onClick={(e) => e?.activePayload?.[0] && onMonthChange?.(e.activePayload[0].payload.month)}
                style={{ cursor: onMonthChange ? "pointer" : "default" }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => fmt(v)} />
                <Legend />
                <Bar dataKey="Income"   fill="#4CAF50" radius={[3,3,0,0]} />
                <Bar dataKey="Expenses" fill="#F44336" radius={[3,3,0,0]} />
                <Bar dataKey="Savings"  fill="#2196F3" radius={[3,3,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* top 5 expenses */}
      {data.top_transactions?.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h2 className="font-semibold text-gray-700 mb-3">Top 5 Expenses</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-400 border-b">
                <th className="pb-2">Date</th>
                <th className="pb-2">Description</th>
                <th className="pb-2">Category</th>
                <th className="pb-2 text-right">Amount</th>
              </tr>
            </thead>
            <tbody>
              {data.top_transactions.map((t) => (
                <tr key={t.id} className="border-b last:border-0 hover:bg-gray-50">
                  <td className="py-2 text-gray-500">{t.date}</td>
                  <td className="py-2 max-w-xs truncate">{t.description}</td>
                  <td className="py-2">
                    <span className="bg-gray-100 px-2 py-0.5 rounded text-xs">{t.category}</span>
                  </td>
                  <td className="py-2 text-right font-medium text-red-600">
                    {fmt(Math.abs(t.amount))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* amortized items this month */}
      {(data.amortized_items?.length > 0 || data.amort_slices?.length > 0) && (
        <div className="bg-white rounded-xl border border-purple-200 p-4">
          <h2 className="font-semibold text-purple-700 mb-1">
            ⏱ Amortized Expenses
            <span className="ml-2 text-xs font-normal text-gray-400">
              (original amounts excluded from totals; slices counted above)
            </span>
          </h2>
          <table className="w-full text-sm mt-2">
            <thead>
              <tr className="text-left text-gray-400 border-b">
                <th className="pb-2">Date</th>
                <th className="pb-2">Description</th>
                <th className="pb-2">Full Amount</th>
                <th className="pb-2">Period</th>
                <th className="pb-2 text-right">This Month's Slice</th>
              </tr>
            </thead>
            <tbody>
              {data.amort_slices.map((s) => (
                <tr key={s.source_id} className="border-b last:border-0">
                  <td className="py-2 text-gray-500">{s.date}</td>
                  <td className="py-2 max-w-xs truncate">{s.description}</td>
                  <td className="py-2 text-gray-500">{fmt(s.total_amount)}</td>
                  <td className="py-2 text-xs text-purple-600">
                    {s.start_month} → {s.end_month} ({s.amortization_months} mo)
                  </td>
                  <td className="py-2 text-right font-medium text-purple-700">
                    {fmt(s.slice_amount)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* capital expenses */}
      {data.capital_expenses?.length > 0 && (
        <div className="bg-white rounded-xl border border-amber-200 p-4">
          <h2 className="font-semibold text-amber-700 mb-1">
            🏷 Capital Expenses
            <span className="ml-2 text-xs font-normal text-gray-400">(excluded from totals)</span>
          </h2>
          <table className="w-full text-sm mt-2">
            <thead>
              <tr className="text-left text-gray-400 border-b">
                <th className="pb-2">Date</th>
                <th className="pb-2">Description</th>
                <th className="pb-2">Note</th>
                <th className="pb-2 text-right">Amount</th>
              </tr>
            </thead>
            <tbody>
              {data.capital_expenses.map((t) => (
                <tr key={t.id} className="border-b last:border-0">
                  <td className="py-2 text-gray-500">{t.date}</td>
                  <td className="py-2 max-w-xs truncate">{t.description}</td>
                  <td className="py-2 text-xs text-amber-600">{t.capital_note || "—"}</td>
                  <td className="py-2 text-right font-medium text-amber-600">
                    {fmt(Math.abs(t.amount))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
