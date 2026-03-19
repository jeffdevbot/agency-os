"use client";

import { useState } from "react";
import type {
  ImportWbrCampaignExclusionSummary,
  WbrCampaignExclusionItem,
} from "../../_lib/campaignExclusionApi";

type Props = {
  loading: boolean;
  refreshing: boolean;
  exportingCsv: boolean;
  importingCsv: boolean;
  items: WbrCampaignExclusionItem[];
  errorMessage: string | null;
  successMessage: string | null;
  latestImportSummary: ImportWbrCampaignExclusionSummary | null;
  onRefresh: () => void;
  onDownloadCsv: () => void;
  onUploadCsv: (file: File) => void;
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

export default function CampaignExclusionCard({
  loading,
  refreshing,
  exportingCsv,
  importingCsv,
  items,
  errorMessage,
  successMessage,
  latestImportSummary,
  onRefresh,
  onDownloadCsv,
  onUploadCsv,
}: Props) {
  const [selectedCsvFile, setSelectedCsvFile] = useState<File | null>(null);

  return (
    <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[#0f172a]">Campaign Exclusions</p>
          <p className="mt-1 text-sm text-[#4c576f]">
            Upload a CSV of out-of-scope campaign names to keep them out of Section 2 totals and
            the <span className="font-semibold text-[#0f172a]">Unmapped / Legacy Campaigns</span>{" "}
            bucket.
          </p>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading || refreshing || importingCsv || exportingCsv}
          className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
        >
          {refreshing ? "Refreshing..." : "Refresh Exclusions"}
        </button>
      </div>

      <div className="mt-4 rounded-2xl border border-[#c7d8f5] bg-[#f7faff] p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-[#0f172a]">Bulk CSV Setup</p>
            <p className="mt-1 text-sm text-[#4c576f]">
              Download all known campaigns for this profile, then set `scope_status` to `excluded`
              for any out-of-scope campaigns. Leave it blank to keep a campaign included.
            </p>
          </div>
          <button
            onClick={onDownloadCsv}
            disabled={loading || refreshing || exportingCsv || importingCsv}
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
          >
            {exportingCsv ? "Downloading..." : "Download Exclusion CSV"}
          </button>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_280px] md:items-start">
          <label className="text-sm">
            <span className="mb-1 block font-semibold text-[#0f172a]">Upload Completed CSV</span>
            <input
              type="file"
              accept=".csv"
              onChange={(event) => setSelectedCsvFile(event.target.files?.[0] ?? null)}
              className="block w-full rounded-xl border border-[#c7d8f5] bg-white px-3 py-2 text-sm text-[#0f172a] file:mr-4 file:rounded-lg file:border-0 file:bg-[#0a6fd6] file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white"
            />
          </label>
          <div className="md:pt-6">
            <button
              onClick={() => {
                if (selectedCsvFile) {
                  onUploadCsv(selectedCsvFile);
                }
              }}
              disabled={!selectedCsvFile || importingCsv || exportingCsv}
              className="w-full rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-[#b7cbea]"
            >
              {importingCsv ? "Importing..." : "Import Exclusions CSV"}
            </button>
          </div>
        </div>

        <div className="mt-3 space-y-1 text-xs text-[#64748b]">
          <p>
            CSV only. The export includes all known campaigns for this profile. Change only the
            rows you want to exclude.
          </p>
          {selectedCsvFile ? <p>Selected: {selectedCsvFile.name}</p> : null}
        </div>

        {latestImportSummary ? (
          <div className="mt-4 grid gap-3 md:grid-cols-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Rows Read</p>
              <p className="text-sm font-semibold text-[#0f172a]">{latestImportSummary.rows_read}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Excluded</p>
              <p className="text-sm font-semibold text-[#0f172a]">{latestImportSummary.rows_excluded}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Cleared</p>
              <p className="text-sm font-semibold text-[#0f172a]">{latestImportSummary.rows_cleared}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Unchanged</p>
              <p className="text-sm font-semibold text-[#0f172a]">{latestImportSummary.rows_unchanged}</p>
            </div>
          </div>
        ) : null}
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

      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
          <thead className="bg-[#f7faff]">
            <tr className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">
              <th className="px-3 py-2">Campaign</th>
              <th className="px-3 py-2">Source</th>
              <th className="px-3 py-2">Updated</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 bg-white">
            {loading ? (
              <tr>
                <td colSpan={3} className="px-3 py-4 text-[#64748b]">
                  Loading campaign exclusions...
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={3} className="px-3 py-4 text-[#64748b]">
                  No campaign exclusions yet.
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr key={item.id} className="hover:bg-slate-50">
                  <td className="px-3 py-2 font-semibold text-[#0f172a]">{item.campaign_name}</td>
                  <td className="px-3 py-2 text-[#4c576f]">{item.exclusion_source ?? "manual"}</td>
                  <td className="px-3 py-2 text-[#4c576f]">
                    {formatTimestamp(item.updated_at ?? item.created_at)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
