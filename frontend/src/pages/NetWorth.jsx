import React, { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, Area, AreaChart,
  PieChart, Pie, Cell,
} from "recharts";
import { fetchNetWorth } from "../api";

const fmt = (n) =>
  n == null
    ? "—"
    : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

const fmtShort = (n) => {
  if (n == null) return "—";
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000)     return `$${(n / 1_000).toFixed(1)}k`;
  return fmt(n);
};

function StatCard({ label, value, sub, color = "indigo" }) {
  const styles = {
    indigo:  "bg-indigo-50  border-indigo-200  text-indigo-700",
    green:   "bg-green-50   border-green-200   text-green-700",
    amber:   "bg-amber-50   border-amber-200   text-amber-700",
    emerald: "bg-emerald-50 border-emerald-200 text-emerald-700",
    red:     "bg-red-50     border-red-200     text-red-700",
  };
  return (
    <div className={`rounded-xl border p-4 ${styles[color]}`}>
      <p className="text-sm font-medium opacity-70">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
      {sub && <p className="text-xs mt-1 opacity-60">{sub}</p>}
    </div>
  );
}

const ASSET_CLASS_COLORS = {
  equity:       "#2196F3",
  cash:         "#4CAF50",
  fixed_income: "#FF9800",
};
const ASSET_CLASS_LABELS = {
  equity:       "Equities",
  cash:         "Cash / Money Market",
  fixed_income: "Fixed Income",
};

// Pie chart asset composition colors
const PIE_COLORS = {
  "Stocks (Brokerage)":  "#2196F3",
  "Portfolio Cash":      "#4CAF50",
  "Checking":            "#FF9800",
  "Emergency Fund":      "#9C27B0",
};

const CustomPieLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, name, percent }) => {
  if (percent < 0.04) return null;
  const RADIAN = Math.PI / 180;
  const r = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + r * Math.cos(-midAngle * RADIAN);
  const y = cy + r * Math.sin(-midAngle * RADIAN);
  return (
    <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central"
      fontSize={11} fontWeight="600">
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
};

export default function NetWorth() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchNetWorth().then(setData).finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-gray-400 py-10 text-center">Loading…</p>;

  if (!data || (data.timeline.length === 0 && data.current_holdings.length === 0)) {
    return (
      <div className="text-center py-20 text-gray-400">
        <p className="text-5xl mb-4">📈</p>
        <p className="text-lg">
          Drop J.P. Morgan or Fidelity investment PDFs and Capital One savings PDFs into{" "}
          <code className="bg-gray-100 px-1 rounded">data/statements/</code> to populate.
        </p>
      </div>
    );
  }

  const snap = data.current_snapshot;
  const assets = data.current_assets;
  const checking = data.latest_checking;
  const savings  = data.latest_savings;

  // Latest net worth entry
  const latestNW = [...data.timeline].reverse().find(t => t.net_worth != null) ?? {};
  const prevNW   = [...data.timeline]
    .reverse()
    .filter(t => t.net_worth != null)
    .slice(1, 2)[0];
  const nwChange = latestNW.net_worth != null && prevNW?.net_worth != null
    ? latestNW.net_worth - prevNW.net_worth : null;
  const portChange = snap?.market_gain;

  // Build asset composition pie
  const pieData = [];
  if (assets?.portfolio_equity) {
    pieData.push({ name: "Stocks (Brokerage)", value: assets.portfolio_equity });
  }
  if (assets?.portfolio_cash) {
    pieData.push({ name: "Portfolio Cash", value: assets.portfolio_cash });
  }
  if (checking) {
    pieData.push({ name: "Checking", value: checking });
  }
  if (savings) {
    pieData.push({ name: "Emergency Fund", value: savings });
  }
  const totalForPie = pieData.reduce((s, d) => s + d.value, 0);

  // Chart data
  const chartData = data.timeline.map((t) => ({
    month:       t.date,
    "Net Worth": t.net_worth,
    "Portfolio": t.portfolio,
    "Checking":  t.checking,
    "Savings":   t.savings,
  }));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Net Worth</h1>

      {/* Summary stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Total Net Worth"
          value={fmt(latestNW.net_worth)}
          sub={nwChange != null ? `${nwChange >= 0 ? "+" : ""}${fmt(nwChange)} vs prev month` : undefined}
          color={latestNW.net_worth >= 0 ? "indigo" : "red"}
        />
        <StatCard
          label="Portfolio"
          value={fmt(snap?.total_value ?? latestNW.portfolio)}
          sub={portChange != null ? `${portChange >= 0 ? "+" : ""}${fmt(portChange)} market gain` : "Brokerage + IRA"}
          color="indigo"
        />
        <StatCard
          label="Checking"
          value={fmt(checking)}
          sub="Chase Total Checking"
          color="amber"
        />
        <StatCard
          label="Emergency Fund"
          value={fmt(savings)}
          sub="Capital One 360 Savings"
          color="emerald"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Asset Composition Pie */}
        {pieData.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h2 className="font-semibold text-gray-700 mb-1">Asset Composition</h2>
            {assets && (
              <p className="text-xs text-gray-400 mb-3">
                Portfolio as of {assets.snapshot_date} · Other balances as of latest statement
              </p>
            )}
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie
                  data={pieData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={95}
                  labelLine={false}
                  label={CustomPieLabel}
                >
                  {pieData.map((entry) => (
                    <Cell key={entry.name} fill={PIE_COLORS[entry.name] ?? "#999"} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => fmt(v)} />
              </PieChart>
            </ResponsiveContainer>
            {/* Legend */}
            <div className="mt-2 space-y-1">
              {pieData.map((d) => (
                <div key={d.name} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span
                      className="w-3 h-3 rounded-full flex-shrink-0"
                      style={{ background: PIE_COLORS[d.name] ?? "#999" }}
                    />
                    <span className="text-gray-600">{d.name}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-gray-400 text-xs">
                      {((d.value / totalForPie) * 100).toFixed(1)}%
                    </span>
                    <span className="font-medium text-gray-800 tabular-nums">{fmt(d.value)}</span>
                  </div>
                </div>
              ))}
              <div className="flex items-center justify-between text-sm font-semibold pt-1 border-t">
                <span className="text-gray-700">Total</span>
                <span className="text-gray-900">{fmt(totalForPie)}</span>
              </div>
            </div>
          </div>
        )}

        {/* Portfolio breakdown if we have per-class data */}
        {snap && (
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h2 className="font-semibold text-gray-700 mb-1">Portfolio Detail</h2>
            <p className="text-xs text-gray-400 mb-3">as of {snap.statement_date}</p>
            <div className="space-y-3">
              {[
                { label: "Equities",        value: snap.equity_value, color: "#2196F3" },
                { label: "Cash / Money Mkt", value: snap.cash_value,   color: "#4CAF50" },
              ].map(({ label, value, color }) => (
                <div key={label} className="flex items-center gap-3">
                  <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: color }} />
                  <span className="text-sm text-gray-600 flex-1">{label}</span>
                  <span className="text-sm font-medium text-gray-800">{fmt(value)}</span>
                </div>
              ))}
              <div className="flex items-center gap-3 pt-2 border-t">
                <span className="w-3 h-3 rounded-full flex-shrink-0 bg-indigo-500" />
                <span className="text-sm text-gray-600 flex-1">Net Deposits (this month)</span>
                <span className="text-sm font-medium text-gray-800">{fmt(snap.net_deposits)}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="w-3 h-3 rounded-full flex-shrink-0 bg-green-500" />
                <span className="text-sm text-gray-600 flex-1">Market Gain (this month)</span>
                <span className={`text-sm font-medium ${snap.market_gain >= 0 ? "text-green-600" : "text-red-600"}`}>
                  {snap.market_gain >= 0 ? "+" : ""}{fmt(snap.market_gain)}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Net Worth over time */}
      {chartData.length >= 1 && (
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h2 className="font-semibold text-gray-700 mb-3">Net Worth Over Time</h2>
          {chartData.length === 1 ? (
            <div className="flex items-center gap-6 py-4">
              {[
                { label: "Net Worth", val: chartData[0]["Net Worth"], color: "text-indigo-600" },
                { label: "Portfolio",  val: chartData[0].Portfolio,   color: "text-blue-600" },
                { label: "Checking",   val: chartData[0].Checking,    color: "text-amber-600" },
                { label: "Savings",    val: chartData[0].Savings,     color: "text-emerald-600" },
              ].filter(x => x.val != null).map(({ label, val, color }) => (
                <div key={label} className="text-center flex-1">
                  <p className="text-sm text-gray-500">{label}</p>
                  <p className={`text-xl font-bold ${color}`}>{fmt(val)}</p>
                </div>
              ))}
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="nwGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={fmtShort} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => fmt(v)} />
                <Legend />
                <Area type="monotone" dataKey="Net Worth" stroke="#6366f1" fill="url(#nwGrad)"
                  strokeWidth={2} dot={{ r: 3 }} connectNulls />
                <Line type="monotone" dataKey="Portfolio" stroke="#2196F3"
                  strokeWidth={1.5} dot={{ r: 2 }} strokeDasharray="4 2" connectNulls />
                <Line type="monotone" dataKey="Checking" stroke="#FF9800"
                  strokeWidth={1.5} dot={{ r: 2 }} strokeDasharray="4 2" connectNulls />
                <Line type="monotone" dataKey="Savings" stroke="#9C27B0"
                  strokeWidth={1.5} dot={{ r: 2 }} strokeDasharray="4 2" connectNulls />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      )}

      {/* Holdings table */}
      {data.current_holdings.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h2 className="font-semibold text-gray-700 mb-3">
            Current Holdings
            {snap && (
              <span className="ml-2 text-xs font-normal text-gray-400">as of {snap.statement_date}</span>
            )}
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b text-xs">
                  <th className="pb-2 pr-4">Account</th>
                  <th className="pb-2 pr-4">Symbol</th>
                  <th className="pb-2 pr-4">Name</th>
                  <th className="pb-2 pr-4">Type</th>
                  <th className="pb-2 pr-4 text-right">Qty</th>
                  <th className="pb-2 pr-4 text-right">Price</th>
                  <th className="pb-2 pr-4 text-right">Market Value</th>
                  <th className="pb-2 pr-4 text-right">Cost Basis</th>
                  <th className="pb-2 text-right">Unrealized G/L</th>
                </tr>
              </thead>
              <tbody>
                {data.current_holdings.map((h) => {
                  const gl = h.unrealized_gl;
                  const glColor = gl == null ? "" : gl >= 0 ? "text-green-600" : "text-red-600";
                  return (
                    <tr key={h.id} className="border-b last:border-0 hover:bg-gray-50">
                      <td className="py-2 pr-4 text-gray-500 whitespace-nowrap">{h.account}</td>
                      <td className="py-2 pr-4 font-mono font-semibold text-indigo-700">
                        {h.symbol === "SWEEP" ? "—" : h.symbol}
                      </td>
                      <td className="py-2 pr-4 text-gray-700 max-w-xs truncate" title={h.name}>
                        {h.name}
                      </td>
                      <td className="py-2 pr-4">
                        <span
                          className="text-xs px-2 py-0.5 rounded-full font-medium"
                          style={{
                            background: (ASSET_CLASS_COLORS[h.asset_class] ?? "#999") + "22",
                            color: ASSET_CLASS_COLORS[h.asset_class] ?? "#555",
                          }}
                        >
                          {ASSET_CLASS_LABELS[h.asset_class] ?? h.asset_class}
                        </span>
                      </td>
                      <td className="py-2 pr-4 text-right text-gray-600">
                        {h.quantity != null ? h.quantity.toLocaleString() : "—"}
                      </td>
                      <td className="py-2 pr-4 text-right text-gray-600">
                        {h.price != null ? fmt(h.price) : "—"}
                      </td>
                      <td className="py-2 pr-4 text-right font-medium text-gray-800">
                        {fmt(h.market_value)}
                      </td>
                      <td className="py-2 pr-4 text-right text-gray-500">
                        {h.cost_basis != null ? fmt(h.cost_basis) : "—"}
                      </td>
                      <td className={`py-2 text-right font-medium ${glColor}`}>
                        {gl != null ? `${gl >= 0 ? "+" : ""}${fmt(gl)}` : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot className="border-t font-semibold text-gray-700 text-sm">
                <tr>
                  <td colSpan={6} className="pt-2 text-right text-gray-500">Total</td>
                  <td className="pt-2 pr-4 text-right">
                    {fmt(data.current_holdings.reduce((s, h) => s + h.market_value, 0))}
                  </td>
                  <td className="pt-2 pr-4 text-right text-gray-500">
                    {fmt(data.current_holdings.reduce((s, h) => s + (h.cost_basis ?? 0), 0))}
                  </td>
                  <td className={`pt-2 text-right ${
                    data.current_holdings.reduce((s, h) => s + (h.unrealized_gl ?? 0), 0) >= 0
                      ? "text-green-600" : "text-red-600"
                  }`}>
                    {(() => {
                      const t = data.current_holdings.reduce((s, h) => s + (h.unrealized_gl ?? 0), 0);
                      return `${t >= 0 ? "+" : ""}${fmt(t)}`;
                    })()}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
