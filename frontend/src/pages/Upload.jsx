import React, { useState, useEffect, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { uploadStatement, fetchStatements, deleteStatement } from "../api";

export default function Upload({ onUploadSuccess }) {
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [statements, setStatements] = useState([]);

  const loadStatements = () => fetchStatements().then(setStatements);

  useEffect(() => { loadStatements(); }, []);

  const onDrop = useCallback(async (files) => {
    const file = files[0];
    if (!file) return;
    setUploading(true);
    setResult(null);
    setError(null);
    try {
      const { data } = await uploadStatement(file);
      setResult(data);
      onUploadSuccess?.();
      loadStatements();
    } catch (e) {
      setError(e.response?.data?.detail || "Upload failed. Make sure it's a Chase PDF.");
    } finally {
      setUploading(false);
    }
  }, [onUploadSuccess]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    maxFiles: 1,
  });

  const handleDelete = async (id) => {
    if (!confirm("Delete this statement and all its transactions?")) return;
    await deleteStatement(id);
    loadStatements();
    onUploadSuccess?.();
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-800">Upload Statement</h1>

      {/* drop zone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors ${
          isDragActive
            ? "border-indigo-400 bg-indigo-50"
            : "border-gray-300 hover:border-indigo-300 hover:bg-gray-50"
        }`}
      >
        <input {...getInputProps()} />
        <p className="text-4xl mb-3">📄</p>
        {uploading ? (
          <p className="text-indigo-600 font-medium">Parsing statement…</p>
        ) : isDragActive ? (
          <p className="text-indigo-600 font-medium">Drop it here…</p>
        ) : (
          <>
            <p className="font-medium text-gray-700">
              Drag & drop a Chase PDF, or click to select
            </p>
            <p className="text-sm text-gray-400 mt-1">
              Supports Chase checking and credit card statements
            </p>
          </>
        )}
      </div>

      {result && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 text-green-800">
          <p className="font-semibold">✅ Uploaded successfully!</p>
          <p className="text-sm mt-1">
            {result.account_type === "credit" ? "Credit card" : "Checking"} statement for{" "}
            <strong>{result.month}</strong> — {result.transaction_count} transactions imported.
          </p>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-800">
          <p className="font-semibold">❌ Error</p>
          <p className="text-sm mt-1">{error}</p>
        </div>
      )}

      {/* uploaded statements */}
      {statements.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 border-b">
            <h2 className="font-semibold text-gray-700">Uploaded Statements</h2>
          </div>
          <table className="w-full text-sm">
            <thead className="text-gray-400 text-left border-b">
              <tr>
                <th className="px-4 py-2">Filename</th>
                <th className="px-4 py-2">Type</th>
                <th className="px-4 py-2">Month</th>
                <th className="px-4 py-2">Uploaded</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {statements.map((s) => (
                <tr key={s.id} className="border-t hover:bg-gray-50">
                  <td className="px-4 py-2 max-w-xs truncate text-gray-700">
                    {s.filename}
                  </td>
                  <td className="px-4 py-2 capitalize text-gray-500">
                    {s.account_type}
                  </td>
                  <td className="px-4 py-2 font-medium">{s.month}</td>
                  <td className="px-4 py-2 text-gray-400">
                    {s.uploaded_at?.slice(0, 10)}
                  </td>
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
      )}
    </div>
  );
}
