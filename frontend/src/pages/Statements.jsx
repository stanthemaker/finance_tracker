import React, { useState, useEffect } from "react";
import { fetchStatements, deleteStatement, scanStatements } from "../api";

export default function Statements({ onScanSuccess }) {
  const [data, setData]       = useState({ statements: [], pending: [] });
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState(null);

  const load = () => fetchStatements().then(setData);
  useEffect(() => { load(); }, []);

  const handleScan = async () => {
    setScanning(true);
    setScanResult(null);
    try {
      const result = await scanStatements();
      setScanResult(result);
      onScanSuccess?.();
      load();
    } finally {
      setScanning(false);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm("Delete this statement and all its transactions?")) return;
    await deleteStatement(id);
    load();
    onScanSuccess?.();
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-800">Statements</h1>
        <button
          onClick={handleScan}
          disabled={scanning}
          className="bg-indigo-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-2"
        >
          {scanning ? "Scanning…" : "🔍 Scan for New PDFs"}
        </button>
      </div>

      {/* folder instructions */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-800">
        <p className="font-semibold mb-1">How to add statements</p>
        <p>
          Copy Chase PDF statements into{" "}
          <code className="bg-blue-100 px-1 rounded font-mono">data/statements/</code>{" "}
          then click <strong>Scan for New PDFs</strong>. The app will auto-detect and parse any
          new files.
        </p>
      </div>

      {/* scan result */}
      {scanResult && (
        <div className="rounded-xl border p-4 space-y-1 text-sm">
          {scanResult.imported.length > 0 && (
            <p className="text-green-700">
              ✅ Imported {scanResult.imported.length} statement(s):{" "}
              {scanResult.imported.map((i) => `${i.file} (${i.count} txns)`).join(", ")}
            </p>
          )}
          {scanResult.skipped.length > 0 && (
            <p className="text-gray-500">⏭ Skipped (already imported): {scanResult.skipped.join(", ")}</p>
          )}
          {scanResult.errors.length > 0 && (
            <p className="text-red-600">
              ❌ Errors: {scanResult.errors.map((e) => `${e.file}: ${e.error}`).join("; ")}
            </p>
          )}
          {scanResult.imported.length === 0 && scanResult.errors.length === 0 && (
            <p className="text-gray-500">No new statements found.</p>
          )}
        </div>
      )}

      {/* pending PDFs (in folder but not yet imported) */}
      {data.pending?.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
          <p className="font-semibold mb-1">⏳ Pending (click Scan to import)</p>
          <ul className="list-disc list-inside space-y-0.5">
            {data.pending.map((f) => <li key={f}>{f}</li>)}
          </ul>
        </div>
      )}

      {/* imported statements table */}
      {data.statements.length > 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 border-b">
            <h2 className="font-semibold text-gray-700">Imported Statements</h2>
          </div>
          <table className="w-full text-sm">
            <thead className="text-gray-400 text-left border-b">
              <tr>
                <th className="px-4 py-2">Filename</th>
                <th className="px-4 py-2">Type</th>
                <th className="px-4 py-2">Month</th>
                <th className="px-4 py-2">Imported</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {data.statements.map((s) => (
                <tr key={s.id} className="border-t hover:bg-gray-50">
                  <td className="px-4 py-2 max-w-xs truncate text-gray-700">{s.filename}</td>
                  <td className="px-4 py-2 capitalize text-gray-500">{s.account_type}</td>
                  <td className="px-4 py-2 font-medium">{s.month}</td>
                  <td className="px-4 py-2 text-gray-400">{s.uploaded_at?.slice(0, 10)}</td>
                  <td className="px-4 py-2">
                    <button
                      onClick={() => handleDelete(s.id)}
                      className="text-xs text-red-400 hover:text-red-600"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-gray-400 text-sm">No statements imported yet.</p>
      )}
    </div>
  );
}
