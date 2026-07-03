import React, { useEffect, useState } from "react";
import { fetchTransactions, updateTransaction, fetchCategories } from "../api";

const fmt = (n) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

export default function Transactions({ month }) {
  const [data, setData]             = useState({ total: 0, items: [] });
  const [categories, setCategories] = useState([]);
  const [catsByType, setCatsByType] = useState({});
  const [catColors, setCatColors]   = useState({});
  const [filterCat, setFilterCat]   = useState("");
  const [filterType, setFilterType] = useState("");

  // inline action states
  const [amortId, setAmortId]       = useState(null);
  const [amortMonths, setAmortMonths] = useState(12);
  const [excludeId, setExcludeId]   = useState(null);

  const effectiveMonth = (month === "average") ? null : month;

  const load = () => {
    const params = {};
    if (effectiveMonth) params.month    = effectiveMonth;
    if (filterCat)      params.category = filterCat;
    if (filterType)     params.tx_type  = filterType;
    fetchTransactions(params).then(setData);
  };

  useEffect(load, [month, filterCat, filterType]);

  useEffect(() => {
    fetchCategories().then(({ categories, by_type, colors }) => {
      setCategories(categories);
      setCatsByType(by_type || {});
      setCatColors(colors);
    });
  }, []);

  const closeInline = () => {
    setAmortId(null);
    setExcludeId(null);
  };

  const saveCategory = async (id, cat) => {
    await updateTransaction(id, { category: cat });
    load();
  };

  const saveType = async (id, tx_type) => {
    await updateTransaction(id, { tx_type });
    load();
  };

  const saveAmort = async (id, is_amortized) => {
    if (is_amortized) {
      await updateTransaction(id, { is_amortized: 1, amortization_months: amortMonths });
    } else {
      await updateTransaction(id, { is_amortized: 0, amortization_months: null });
    }
    closeInline();
    load();
  };

  const saveExclude = async (id, is_excluded) => {
    await updateTransaction(id, { is_excluded });
    closeInline();
    load();
  };

  const typeColor = (t) => {
    if (t === "income")  return "text-green-600";
    if (t === "expense") return "text-red-600";
    return "text-gray-500";
  };

  if (month === "average") {
    // fall through — load all transactions without month filter
  } else if (!month) {
    return <p className="text-gray-400 py-10 text-center">Select a month above.</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-gray-800">
          Transactions {effectiveMonth ? `— ${effectiveMonth}` : "— All Months"}
        </h1>
        <div className="flex gap-2">
          <select className="text-sm border rounded px-2 py-1" value={filterCat}
            onChange={(e) => setFilterCat(e.target.value)}>
            <option value="">All categories</option>
            {categories.map((c) => <option key={c}>{c}</option>)}
          </select>
          <select className="text-sm border rounded px-2 py-1" value={filterType}
            onChange={(e) => setFilterType(e.target.value)}>
            <option value="">All types</option>
            <option value="expense">Expense</option>
            <option value="income">Income</option>
            <option value="transfer">Transfer</option>
          </select>
        </div>
      </div>

      <p className="text-sm text-gray-500">{data.total} transactions</p>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-500 text-left">
            <tr>
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3">Description</th>
              <th className="px-4 py-3">Category</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3 text-right">Amount</th>
              <th className="px-4 py-3 w-16"></th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((t) => (
              <React.Fragment key={t.id}>
                <tr className={`border-t hover:bg-gray-50 ${
                  t.is_excluded  ? "bg-red-50 opacity-50" :
                  t.is_amortized ? "bg-purple-50 opacity-70" : ""
                }`}>
                  <td className="px-4 py-2 text-gray-500 whitespace-nowrap">{t.date}</td>
                  <td className="px-4 py-2 max-w-xs">
                    <span className="truncate block" title={t.description}>{t.description}</span>
                    <div className="flex gap-1 mt-0.5">
                      {t.is_excluded  === 1 && <span className="text-xs text-red-400">🚫 excluded</span>}
                      {t.is_amortized === 1 && <span className="text-xs text-purple-500">⏱ amortized over {t.amortization_months}mo</span>}
                    </div>
                  </td>
                  <td className="px-4 py-2">
                    {/* auto-save on change, no Save button */}
                    <select
                      value={t.category}
                      onChange={(e) => saveCategory(t.id, e.target.value)}
                      className="text-xs px-2 py-0.5 rounded cursor-pointer focus:outline-none focus:ring-1 focus:ring-indigo-300"
                      style={{
                        background: (catColors[t.category] || "#ccc") + "22",
                        color:      catColors[t.category] || "#444",
                        border:     `1px solid ${(catColors[t.category] || "#ccc")}55`,
                      }}
                    >
                      {(catsByType[t.tx_type] || categories).map((c) => <option key={c}>{c}</option>)}
                    </select>
                  </td>
                  <td className="px-4 py-2">
                    <select
                      value={t.tx_type}
                      onChange={(e) => saveType(t.id, e.target.value)}
                      className={`text-xs px-2 py-0.5 rounded border cursor-pointer focus:outline-none focus:ring-1 focus:ring-indigo-300 capitalize ${typeColor(t.tx_type)}`}
                      style={{ background: "transparent" }}
                    >
                      <option value="income">income</option>
                      <option value="expense">expense</option>
                      <option value="transfer">transfer</option>
                    </select>
                  </td>
                  <td className={`px-4 py-2 text-right font-medium ${typeColor(t.tx_type)}`}>
                    {t.amount >= 0 ? "+" : ""}{fmt(t.amount)}
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex gap-1 justify-end">
                      {/* amortize: available for expense and transfer types */}
                      {(t.tx_type === "expense" || t.tx_type === "transfer") && !t.is_excluded && (
                        t.is_amortized === 1 ? (
                          <button onClick={() => saveAmort(t.id, false)}
                            className="text-xs text-purple-400 hover:text-red-500" title="Remove amortization">⏱✕</button>
                        ) : (
                          <button onClick={() => { closeInline(); setAmortId(t.id); setAmortMonths(12); }}
                            className="text-xs text-gray-300 hover:text-purple-500" title="Amortize over N months">⏱</button>
                        )
                      )}
                      {/* exclude: available for any transaction */}
                      {t.is_excluded === 1 ? (
                        <button onClick={() => saveExclude(t.id, 0)}
                          className="text-xs text-red-400 hover:text-green-500" title="Restore (un-exclude)">🚫✕</button>
                      ) : (
                        <button onClick={() => { closeInline(); setExcludeId(t.id); }}
                          className="text-xs text-gray-300 hover:text-red-400" title="Exclude from totals">🚫</button>
                      )}
                    </div>
                  </td>
                </tr>

                {/* amortization inline form */}
                {amortId === t.id && (
                  <tr className="bg-purple-50 border-t">
                    <td colSpan={6} className="px-4 py-3">
                      <div className="flex items-center gap-3 text-sm">
                        <span className="text-purple-700 font-medium">Amortize over:</span>
                        <input type="number" min="2" max="120"
                          value={amortMonths}
                          onChange={(e) => setAmortMonths(Number(e.target.value))}
                          className="border rounded px-2 py-1 text-sm w-20" />
                        <span className="text-purple-600">months</span>
                        <span className="text-gray-400 text-xs">
                          = {fmt(Math.abs(t.amount) / amortMonths)}/mo for {amortMonths} months
                        </span>
                        <button onClick={() => saveAmort(t.id, true)}
                          className="bg-purple-600 text-white px-3 py-1 rounded text-xs">Confirm</button>
                        <button onClick={closeInline} className="text-gray-400 text-xs">Cancel</button>
                      </div>
                    </td>
                  </tr>
                )}

                {/* exclude inline confirmation */}
                {excludeId === t.id && (
                  <tr className="bg-red-50 border-t">
                    <td colSpan={6} className="px-4 py-3">
                      <div className="flex items-center gap-3 text-sm">
                        <span className="text-red-700 font-medium">Exclude from all totals?</span>
                        <span className="text-gray-500 text-xs">This transaction won't be counted in income or expenses.</span>
                        <button onClick={() => saveExclude(t.id, 1)}
                          className="bg-red-500 text-white px-3 py-1 rounded text-xs">Exclude</button>
                        <button onClick={closeInline} className="text-gray-400 text-xs">Cancel</button>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
            {data.items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                  No transactions found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
