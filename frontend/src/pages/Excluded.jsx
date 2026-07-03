import React, { useEffect, useState } from "react";
import { fetchTransactions, updateTransaction } from "../api";

const fmt = (n) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

const typeColor = (t) => {
  if (t === "income")  return "text-green-600";
  if (t === "expense") return "text-red-600";
  if (t === "payment") return "text-blue-600";
  return "text-gray-500";
};

export default function Excluded() {
  const [items, setItems] = useState([]);

  const load = () =>
    fetchTransactions({ is_excluded: 1, limit: 1000 }).then((d) => setItems(d.items));

  useEffect(() => { load(); }, []);

  const restore = async (id) => {
    await updateTransaction(id, { is_excluded: 0 });
    load();
  };

  // Group by month for readability
  const byMonth = items.reduce((acc, t) => {
    (acc[t.month] = acc[t.month] || []).push(t);
    return acc;
  }, {});
  const months = Object.keys(byMonth).sort((a, b) => b.localeCompare(a));

  return (
    <div className="space-y-6">
      <div className="flex items-baseline gap-3">
        <h1 className="text-2xl font-bold text-gray-800">Excluded Transactions</h1>
        <span className="text-sm text-gray-400">{items.length} total</span>
      </div>

      {items.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400">
          <p className="text-4xl mb-3">🚫</p>
          <p>No excluded transactions yet.</p>
          <p className="text-sm mt-1">
            Click the 🚫 button on any transaction to exclude it from income and expense totals.
          </p>
        </div>
      ) : (
        months.map((month) => (
          <div key={month} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="bg-gray-50 px-4 py-2 border-b">
              <span className="font-semibold text-gray-700">{month}</span>
              <span className="ml-2 text-xs text-gray-400">{byMonth[month].length} excluded</span>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b">
                  <th className="px-4 py-2">Date</th>
                  <th className="px-4 py-2">Description</th>
                  <th className="px-4 py-2">Category</th>
                  <th className="px-4 py-2">Type</th>
                  <th className="px-4 py-2 text-right">Amount</th>
                  <th className="px-4 py-2 w-20"></th>
                </tr>
              </thead>
              <tbody>
                {byMonth[month].map((t) => (
                  <tr key={t.id} className="border-t bg-red-50 opacity-70 hover:opacity-100">
                    <td className="px-4 py-2 text-gray-500 whitespace-nowrap">{t.date}</td>
                    <td className="px-4 py-2 max-w-xs truncate" title={t.description}>
                      {t.description}
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-600">{t.category}</td>
                    <td className={`px-4 py-2 text-xs capitalize ${typeColor(t.tx_type)}`}>
                      {t.tx_type}
                    </td>
                    <td className={`px-4 py-2 text-right font-medium ${typeColor(t.tx_type)}`}>
                      {t.amount >= 0 ? "+" : ""}{fmt(t.amount)}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <button
                        onClick={() => restore(t.id)}
                        className="text-xs text-gray-400 hover:text-green-600 px-2 py-1 rounded border hover:border-green-300"
                        title="Restore — include in totals again"
                      >
                        Restore
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))
      )}
    </div>
  );
}
