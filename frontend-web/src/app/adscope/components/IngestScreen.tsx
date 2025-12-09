"use client";

import { useCallback, useState, useEffect, useRef } from "react";

interface IngestScreenProps {
  onSubmit: (bulkFile: File, strFile: File, brandKeywords: string) => void;
  processing: boolean;
  error: string | null;
}

export function IngestScreen({ onSubmit, processing, error }: IngestScreenProps) {
  const [bulkFile, setBulkFile] = useState<File | null>(null);
  const [strFile, setStrFile] = useState<File | null>(null);
  const [brandKeywords, setBrandKeywords] = useState("");
  const [processingStatus, setProcessingStatus] = useState("Run Audit");

  const phrasesRef = useRef([
    "Analyzing campaign structures",
    "Computing performance metrics",
    "Identifying money pits",
    "Scanning for waste",
    "Calculating ROAS trajectories",
    "Detecting budget cappers",
    "Mapping keyword hierarchies",
    "Evaluating match type efficiency",
    "Assessing placement strategies",
    "Parsing n-gram patterns",
    "Detecting duplicate keywords",
    "Computing portfolio metrics",
  ]);

  useEffect(() => {
    if (!processing) {
      setProcessingStatus("Run Audit");
      return;
    }
    let idx = 0;
    setProcessingStatus(phrasesRef.current[idx]);
    const id = setInterval(() => {
      idx = (idx + 1) % phrasesRef.current.length;
      setProcessingStatus(phrasesRef.current[idx]);
    }, 3000);
    return () => clearInterval(id);
  }, [processing]);

  const handleBulkDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file && file.name.match(/\.(xlsx|xls)$/i)) {
      setBulkFile(file);
    }
  }, []);

  const handleStrDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file && file.name.match(/\.(csv|xlsx|xls)$/i)) {
      setStrFile(file);
    }
  }, []);

  const handleSubmit = useCallback(() => {
    if (bulkFile && strFile && !processing) {
      onSubmit(bulkFile, strFile, brandKeywords);
    }
  }, [bulkFile, strFile, brandKeywords, processing, onSubmit]);

  const canSubmit = bulkFile && strFile && !processing;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <header className="border-b border-slate-700 bg-slate-900/50 px-6 py-4 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-baseline gap-3">
          <h1 className="text-xl font-bold tracking-tight text-slate-100">
            ADSCOPE
          </h1>
          <p className="text-sm text-slate-400">
            Amazon Ads Performance Audit
          </p>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex flex-1 items-start justify-center px-4 pb-16 pt-10">
        <div className="w-full max-w-6xl">
          <div className="rounded-2xl bg-slate-800/50 p-8 shadow-2xl backdrop-blur-sm border border-slate-700">
            {/* Title */}
            <div className="mb-6">
              <h2 className="text-lg font-semibold text-slate-100">
                Upload Campaign Data
              </h2>
              <p className="text-sm text-slate-400 mt-1">
                Upload your Bulk Operations file and Search Term Report to generate a comprehensive performance audit.
              </p>
            </div>

            {/* Two Dropzones */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
              {/* Bulk File Dropzone */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Bulk Operations File *
                </label>
                <div
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={handleBulkDrop}
                  className={`rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
                    bulkFile
                      ? "border-emerald-500 bg-emerald-500/10"
                      : "border-slate-600 bg-slate-900/50 hover:border-slate-500"
                  }`}
                >
                  <svg
                    className="mx-auto h-12 w-12 text-slate-500 mb-3"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                    />
                  </svg>
                  <p className="text-sm font-semibold text-slate-300">
                    {bulkFile ? bulkFile.name : "Drag & drop Bulk file"}
                  </p>
                  <p className="text-xs text-slate-500 mt-1">
                    .xlsx or .xls
                  </p>
                  <label className="mt-4 inline-block cursor-pointer rounded-lg bg-slate-700 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-600 transition-colors">
                    <input
                      type="file"
                      accept=".xlsx,.xls"
                      className="hidden"
                      onChange={(e) => setBulkFile(e.target.files?.[0] || null)}
                    />
                    Browse files
                  </label>
                </div>
              </div>

              {/* STR File Dropzone */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Search Term Report *
                </label>
                <div
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={handleStrDrop}
                  className={`rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
                    strFile
                      ? "border-emerald-500 bg-emerald-500/10"
                      : "border-slate-600 bg-slate-900/50 hover:border-slate-500"
                  }`}
                >
                  <svg
                    className="mx-auto h-12 w-12 text-slate-500 mb-3"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                    />
                  </svg>
                  <p className="text-sm font-semibold text-slate-300">
                    {strFile ? strFile.name : "Drag & drop STR file"}
                  </p>
                  <p className="text-xs text-slate-500 mt-1">
                    .csv, .xlsx, or .xls
                  </p>
                  <label className="mt-4 inline-block cursor-pointer rounded-lg bg-slate-700 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-600 transition-colors">
                    <input
                      type="file"
                      accept=".csv,.xlsx,.xls"
                      className="hidden"
                      onChange={(e) => setStrFile(e.target.files?.[0] || null)}
                    />
                    Browse files
                  </label>
                </div>
              </div>
            </div>

            {/* Brand Keywords Input */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Brand Keywords (optional)
              </label>
              <input
                type="text"
                value={brandKeywords}
                onChange={(e) => setBrandKeywords(e.target.value)}
                placeholder="e.g., Nike, Adidas, Reebok"
                className="w-full rounded-lg border border-slate-600 bg-slate-900/50 px-4 py-3 text-sm text-slate-200 placeholder-slate-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <p className="text-xs text-slate-500 mt-1">
                Comma-separated list for branded vs generic analysis
              </p>
            </div>

            {/* Submit Button */}
            <button
              onClick={handleSubmit}
              disabled={!canSubmit}
              className={`w-full rounded-xl px-6 py-4 text-sm font-semibold text-white transition-all ${
                processing
                  ? "bg-blue-600 animate-pulse cursor-wait"
                  : canSubmit
                  ? "bg-blue-600 hover:bg-blue-500 shadow-lg shadow-blue-500/50"
                  : "bg-slate-700 cursor-not-allowed text-slate-500"
              }`}
            >
              {processing ? processingStatus : "Run Audit"}
            </button>

            {/* Error Display */}
            {error && (
              <div className="mt-4 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3">
                <p className="text-sm text-red-400">{error}</p>
              </div>
            )}

            {/* Info */}
            <div className="mt-6 rounded-xl bg-slate-900/50 border border-slate-700 p-4">
              <h3 className="text-sm font-semibold text-slate-300 mb-2">
                What you'll get:
              </h3>
              <ul className="space-y-1 text-xs text-slate-400">
                <li>• Performance overview with ACOS, ROAS, and spend breakdown</li>
                <li>• Money pits analysis (high-spend, low-return ASINs)</li>
                <li>• Waste detection (search terms with spend but no sales)</li>
                <li>• Branded vs generic performance comparison</li>
                <li>• Budget utilization and capping alerts</li>
                <li>• Keyword leaderboard (winners & losers)</li>
                <li>• N-gram analysis and duplicate keyword detection</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
