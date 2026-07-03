import React, { useEffect, useState } from "react";
import { fetchAdvice } from "../api";

const LEVEL_STYLES = {
  success: { bg: "bg-green-50 border-green-200",  icon: "✅", text: "text-green-800"  },
  warning: { bg: "bg-amber-50 border-amber-200",   icon: "⚠️",  text: "text-amber-800"  },
  danger:  { bg: "bg-red-50 border-red-200",       icon: "🚨", text: "text-red-800"    },
  info:    { bg: "bg-blue-50 border-blue-200",     icon: "💡", text: "text-blue-800"   },
};

export default function Advice({ month }) {
  const [result, setResult]   = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!month || month === "average") return;
    setLoading(true);
    fetchAdvice(month)
      .then(setResult)
      .finally(() => setLoading(false));
  }, [month]);

  if (!month || month === "average")
    return <p className="text-gray-400 py-10 text-center">Select a specific month for advice.</p>;

  if (loading)
    return <p className="text-gray-400 py-10 text-center">Analyzing…</p>;

  const items = result?.advice ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-baseline gap-3">
        <h1 className="text-2xl font-bold text-gray-800">Advice & Insights — {month}</h1>
        {result && (
          <span className={`text-xs px-2 py-0.5 rounded-full ${
            result.ai_powered
              ? "bg-indigo-100 text-indigo-600"
              : "bg-gray-100 text-gray-500"
          }`}>
            {result.ai_powered ? "✨ AI-powered" : "Rules-based"}
          </span>
        )}
      </div>

      {items.length === 0 ? (
        <p className="text-gray-400">No advice available for this month yet.</p>
      ) : (
        <div className="space-y-3">
          {items.map((item, i) => {
            const style = LEVEL_STYLES[item.level] || LEVEL_STYLES.info;
            return (
              <div key={i} className={`rounded-xl border p-4 ${style.bg}`}>
                <div className="flex items-start gap-3">
                  <span className="text-xl mt-0.5">{style.icon}</span>
                  <div>
                    <p className={`font-semibold ${style.text}`}>{item.title}</p>
                    <p className={`text-sm mt-0.5 ${style.text} opacity-80`}>{item.message}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
