"use client";

import { useMemo, useState } from "react";
import type { WbrPacvueImportBatch, WbrPacvueImportResult } from "../../_lib/wbrApi";

type Props = {
  loadingBatches: boolean;
  refreshingBatches: boolean;
  uploading: boolean;
  creatingSnapshot: boolean;
  batches: WbrPacvueImportBatch[];
  errorMessage: string | null;
  successMessage: string | null;
  latestImport: WbrPacvueImportResult | null;
  onRefresh: () => void;
  onUpload: (file: File) => void;
  onCreateFreshSnapshot: () => void;
};

const formatTimestamp = (value: string | null): string => {
  if (!value) return "—";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
};

const statusClasses: Record<WbrPacvueImportBatch["import_status"], string> = {
  running: "border-sky-200 bg-sky-50 text-sky-800",
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  error: "border-rose-200 bg-rose-50 text-rose-800",
};

const formatFileSize = (bytes: number): string => {
  if (bytes <= 0) return "0 B";
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

export default function PacvueImportCard({
  loadingBatches,
  refreshingBatches,
  uploading,
  creatingSnapshot,
  batches,
  errorMessage,
  successMessage,
  latestImport,
  onRefresh,
  onUpload,
  onCreateFreshSnapshot,
}: Props) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const latestSummaryRows = useMemo(() => {
    if (!latestImport) return [];

    return [
      { label: "Header Row", value: String(latestImport.summary.header_row_index) },
      { label: "Rows Read", value: String(latestImport.summary.rows_read) },
      { label: "Rows Loaded", value: String(latestImport.summary.rows_loaded) },
      { label: "Duplicates Skipped", value: String(latestImport.summary.duplicate_rows_skipped) },
      { label: "Invalid Tags Skipped", value: String(latestImport.summary.invalid_rows_skipped) },
      { label: "Leaf Rows Created", value: String(latestImport.summary.created_leaf_rows) },
      { label: "Leaf Rows Reactivated", value: String(latestImport.summary.reactivated_leaf_rows) },
    ];
  }, [latestImport]);

  return (
    <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[#0f172a]">Pacvue Import</p>
          <p className="mt-1 text-sm text-[#4c576f]">
            Upload the Pacvue campaign export. The importer auto-detects the header row and reads
            the <span className="font-semibold text-[#0f172a]">Name</span> and{" "}
            <span className="font-semibold text-[#0f172a]">CampaignTagNames</span> columns.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={onCreateFreshSnapshot}
            disabled={loadingBatches || refreshingBatches || uploading || creatingSnapshot}
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
          >
            {creatingSnapshot ? "Creating Snapshot..." : "Create Fresh Snapshot"}
          </button>
          <button
            onClick={onRefresh}
            disabled={loadingBatches || refreshingBatches || uploading || creatingSnapshot}
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
          >
            {refreshingBatches ? "Refreshing..." : "Refresh Imports"}
          </button>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border border-[#c7d8f5] bg-[#f7faff] p-4">
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_280px] md:items-start">
          <label className="text-sm">
            <span className="mb-1 block font-semibold text-[#0f172a]">Pacvue Workbook</span>
            <input
              type="file"
              accept=".xlsx,.xlsm"
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              className="block w-full rounded-xl border border-[#c7d8f5] bg-white px-3 py-2 text-sm text-[#0f172a] file:mr-4 file:rounded-lg file:border-0 file:bg-[#0a6fd6] file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white"
            />
          </label>
          <div className="md:pt-6">
            <button
              onClick={() => {
                if (selectedFile) {
                  onUpload(selectedFile);
                }
              }}
              disabled={!selectedFile || uploading}
              className="w-full rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-[#b7cbea]"
            >
              {uploading ? "Importing..." : "Import Pacvue File"}
            </button>
          </div>
        </div>
        <div className="mt-3 space-y-1 text-xs text-[#64748b]">
          <p>
            Metadata rows above the real header are fine. Only `.xlsx` and `.xlsm` are supported,
            up to 40MB.
          </p>
          <p>Create Fresh Snapshot rebuilds the WBR digest from current database state only.</p>
          {selectedFile ? (
            <p>
              Selected: {selectedFile.name} ({formatFileSize(selectedFile.size)})
            </p>
          ) : null}
        </div>
      </div>

      {errorMessage ? (
        <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
          {errorMessage}
        </p>
      ) : null}

      {successMessage ? (
        <p className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {successMessage}
        </p>
      ) : null}

      {latestImport && latestImport.summary.warnings.length > 0 ? (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <p className="font-semibold">Upstream Pacvue tags need cleanup</p>
          <p className="mt-1">
            Invalid tag rows were skipped. Those campaigns will remain in
            {" "}
            <span className="font-semibold">Unmapped / Legacy Campaigns</span>
            {" "}
            until fixed upstream.
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {latestImport.summary.warnings.slice(0, 5).map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {latestSummaryRows.length > 0 ? (
        <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50/60 p-4">
          <p className="text-sm font-semibold text-emerald-900">Latest Import Summary</p>
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            {latestSummaryRows.map((item) => (
              <div key={item.label}>
                <p className="text-xs font-semibold uppercase tracking-wide text-emerald-800/80">
                  {item.label}
                </p>
                <p className="text-sm font-semibold text-emerald-950">{item.value}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
          <thead className="bg-[#f7faff]">
            <tr className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">
              <th className="px-3 py-2">Started</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">File</th>
              <th className="px-3 py-2">Rows Read</th>
              <th className="px-3 py-2">Rows Loaded</th>
              <th className="px-3 py-2">Notes</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 bg-white">
            {loadingBatches ? (
              <tr>
                <td colSpan={6} className="px-3 py-4 text-[#64748b]">
                  Loading Pacvue imports...
                </td>
              </tr>
            ) : batches.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-4 text-[#64748b]">
                  No Pacvue imports yet.
                </td>
              </tr>
            ) : (
              batches.map((batch) => (
                <tr key={batch.id} className="hover:bg-slate-50">
                  <td className="px-3 py-2 text-[#0f172a]">{formatTimestamp(batch.started_at)}</td>
                  <td className="px-3 py-2">
                    <span
                      className={`inline-flex rounded-full border px-2 py-1 text-xs font-semibold ${statusClasses[batch.import_status]}`}
                    >
                      {batch.import_status}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-[#0f172a]">{batch.source_filename ?? "—"}</td>
                  <td className="px-3 py-2 text-[#0f172a]">{batch.rows_read}</td>
                  <td className="px-3 py-2 text-[#0f172a]">{batch.rows_loaded}</td>
                  <td className="px-3 py-2 text-[#64748b]">{batch.error_message ?? "—"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
