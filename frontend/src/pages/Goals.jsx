import React, { useEffect, useState } from "react";
import { fetchSettings, updateSettings, fetchDashboard, fetchAverages } from "../api";

const fmt = (n) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

export default function Goals({ month }) {
  const [goal, setGoal] = useState(1000);
  const [inputGoal, setInputGoal] = useState("1000");
  const [saving, setSaving] = useState(false);
  const [summary, setSummary] = useState(null);
  const [avgs, setAvgs] = useState(null);

  useEffect(() => {
    fetchSettings().then((s) => {
      const g = parseFloat(s.savings_goal || 1000);
      setGoal(g);
      setInputGoal(String(g));
    });
    fetchAverages().then(setAvgs);
  }, []);

  useEffect(() => {
    if (month && month !== "average") fetchDashboard(month).then(setSummary);
    else setSummary(null);
  }, [month]);

  const saveGoal = async () => {
    const val = parseFloat(inputGoal);
    if (isNaN(val) || val < 0) return;
    setSaving(true);
    await updateSettings({ savings_goal: val });
    setGoal(val);
    setSaving(false);
  };

  const net = summary?.net_savings ?? 0;
  const progress = goal > 0 ? Math.min((net / goal) * 100, 100) : 0;
  const onTrack = net >= goal;

  return (
    <div className="space-y-6 max-w-lg">
      <h1 className="text-2xl font-bold text-gray-800">Savings Goal</h1>

      {/* set goal */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="font-semibold text-gray-700 mb-3">Monthly Target</h2>
        <div className="flex gap-2 items-center">
          <span className="text-gray-500">$</span>
          <input
            type="number"
            min="0"
            step="100"
            value={inputGoal}
            onChange={(e) => setInputGoal(e.target.value)}
            className="border rounded px-3 py-1.5 w-32 text-sm"
          />
          <button
            onClick={saveGoal}
            disabled={saving}
            className="bg-indigo-600 text-white text-sm px-4 py-1.5 rounded hover:bg-indigo-700 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>

      {/* progress */}
      {month && summary && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
          <h2 className="font-semibold text-gray-700">
            Progress — {month}
          </h2>

          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="bg-green-50 rounded-lg p-3">
              <p className="text-xs text-gray-500">Income</p>
              <p className="font-bold text-green-700">{fmt(summary.total_income)}</p>
            </div>
            <div className="bg-red-50 rounded-lg p-3">
              <p className="text-xs text-gray-500">Expenses</p>
              <p className="font-bold text-red-600">{fmt(summary.total_expense)}</p>
            </div>
            <div className={`rounded-lg p-3 ${net >= 0 ? "bg-indigo-50" : "bg-orange-50"}`}>
              <p className="text-xs text-gray-500">Net Saved</p>
              <p className={`font-bold ${net >= 0 ? "text-indigo-700" : "text-orange-600"}`}>
                {fmt(net)}
              </p>
            </div>
          </div>

          {/* progress bar */}
          <div>
            <div className="flex justify-between text-sm text-gray-500 mb-1">
              <span>{fmt(Math.max(net, 0))} saved</span>
              <span>goal: {fmt(goal)}</span>
            </div>
            <div className="h-4 bg-gray-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  onTrack ? "bg-green-500" : "bg-indigo-400"
                }`}
                style={{ width: `${Math.max(progress, 0)}%` }}
              />
            </div>
            <p className="text-right text-xs text-gray-400 mt-1">
              {progress.toFixed(0)}%
            </p>
          </div>

          {onTrack ? (
            <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-green-700 text-sm">
              🎉 Goal met! You saved {fmt(net - goal)} extra this month.
            </div>
          ) : (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-amber-700 text-sm">
              {fmt(goal - net)} more needed to hit your goal this month.
            </div>
          )}
        </div>
      )}

      {/* average view */}
      {month === "average" && avgs && avgs.months_count > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
          <h2 className="font-semibold text-gray-700">
            Average Progress
            <span className="ml-2 text-xs font-normal text-gray-400">({avgs.months_count} months)</span>
          </h2>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="bg-green-50 rounded-lg p-3">
              <p className="text-xs text-gray-500">Avg Income</p>
              <p className="font-bold text-green-700">{fmt(avgs.avg_income)}</p>
            </div>
            <div className="bg-red-50 rounded-lg p-3">
              <p className="text-xs text-gray-500">Avg Spending</p>
              <p className="font-bold text-red-600">{fmt(avgs.avg_expense)}</p>
            </div>
            <div className={`rounded-lg p-3 ${avgs.avg_savings >= 0 ? "bg-indigo-50" : "bg-orange-50"}`}>
              <p className="text-xs text-gray-500">Avg Saved</p>
              <p className={`font-bold ${avgs.avg_savings >= 0 ? "text-indigo-700" : "text-orange-600"}`}>
                {fmt(avgs.avg_savings)}
              </p>
            </div>
          </div>
          {(() => {
            const avgNet = avgs.avg_savings;
            const progress = goal > 0 ? Math.min((avgNet / goal) * 100, 100) : 0;
            return (
              <div>
                <div className="flex justify-between text-sm text-gray-500 mb-1">
                  <span>avg {fmt(Math.max(avgNet, 0))} saved/mo</span>
                  <span>goal: {fmt(goal)}</span>
                </div>
                <div className="h-4 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${avgNet >= goal ? "bg-green-500" : "bg-indigo-400"}`}
                    style={{ width: `${Math.max(progress, 0)}%` }}
                  />
                </div>
                <p className="text-right text-xs text-gray-400 mt-1">{Math.max(progress, 0).toFixed(0)}%</p>
                <p className={`mt-2 text-sm ${avgNet >= goal ? "text-green-700" : "text-amber-700"}`}>
                  {avgNet >= goal
                    ? `On average you exceed your goal by ${fmt(avgNet - goal)}/month.`
                    : `On average you're ${fmt(goal - avgNet)} short of your goal each month.`}
                </p>
              </div>
            );
          })()}
        </div>
      )}

      {!month && (
        <p className="text-gray-400 text-sm">Select a month above to see progress.</p>
      )}
    </div>
  );
}
