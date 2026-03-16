"use client";

import { useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import { useResolvedPnlProfile } from "../pnl/_lib/useResolvedPnlProfile";
import { usePnlReport } from "../pnl/_lib/usePnlReport";
import {
  createPnlProfile,
  uploadPnlTransactionReport,
  type PnlFilterMode,
  type PnlImportMonth,
  type PnlLineItem,
  type PnlWarning,
} from "../pnl/_lib/pnlApi";

type Props = {
  clientSlug: string;
  marketplaceCode: string;
};

const FILTER_OPTIONS: { value: PnlFilterMode; label: string }[] = [
  { value: "ytd", label: "Year to Date" },
  { value: "last_3", label: "Last 3 Months" },
  { value: "last_6", label: "Last 6 Months" },
  { value: "last_12", label: "Last 12 Months" },
];

function formatMonth(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}

function formatAmount(value: string): string {
  const n = parseFloat(value);
  if (isNaN(n)) return value;
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
}

function formatMonthList(months: PnlImportMonth[]): string {
  return months.map((month) => formatMonth(month.entry_month)).join(", ");
}

const SUMMARY_KEYS = new Set([
  "total_gross_revenue",
  "total_refunds",
  "total_net_revenue",
  "gross_profit",
  "total_expenses",
  "net_earnings",
  "cogs",
]);

function lineItemRowClass(item: PnlLineItem): string {
  if (item.key === "net_earnings") return "bg-[#0f172a] text-white font-semibold";
  if (SUMMARY_KEYS.has(item.key)) return "bg-[#f1f5f9] font-semibold";
  return "";
}

function amountClass(value: string, item: PnlLineItem): string {
  const n = parseFloat(value);
  if (isNaN(n) || n === 0) return "text-[#94a3b8]";
  if (item.key === "net_earnings") return n < 0 ? "text-[#fca5a5]" : "text-white";
  return n < 0 ? "text-[#ef4444]" : "text-[#0f172a]";
}

function currentMonthISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

function sixMonthsAgoISO(): string {
  const d = new Date();
  d.setMonth(d.getMonth() - 5);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

export default function PnlReportScreen({ clientSlug, marketplaceCode }: Props) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const resolved = useResolvedPnlProfile(clientSlug, marketplaceCode);
  const [filterMode, setFilterMode] = useState<PnlFilterMode>("ytd");
  const [rangeStart, setRangeStart] = useState<string>(sixMonthsAgoISO());
  const [rangeEnd, setRangeEnd] = useState<string>(currentMonthISO());
  const [createError, setCreateError] = useState<string | null>(null);
  const [createPending, setCreatePending] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [uploadPending, setUploadPending] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const profileId = resolved.resolved?.profile?.id ?? null;
  const reportState = usePnlReport(
    profileId,
    filterMode,
    filterMode === "range" ? rangeStart : undefined,
    filterMode === "range" ? rangeEnd : undefined,
  );

  const handleCreateProfile = async () => {
    const resolvedSummary = resolved.resolved;
    if (!resolvedSummary) return;

    setCreatePending(true);
    setCreateError(null);

    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session?.access_token) throw new Error("Please sign in again.");

      await createPnlProfile(session.access_token, {
        clientId: resolvedSummary.client.id,
        marketplaceCode: marketplaceCode.toUpperCase(),
        currencyCode: "USD",
      });

      await resolved.loadRoute();
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : "Unable to create P&L profile");
    } finally {
      setCreatePending(false);
    }
  };

  const handleUpload = async () => {
    if (!profileId || !selectedFile) return;

    setUploadPending(true);
    setUploadError(null);
    setUploadSuccess(null);

    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session?.access_token) throw new Error("Please sign in again.");

      const result = await uploadPnlTransactionReport(session.access_token, profileId, selectedFile);
      setUploadSuccess(
        `Imported ${selectedFile.name} for ${formatMonthList(result.months)}.`,
      );
      setSelectedFile(null);
      await reportState.loadReport(true);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Unable to upload transaction report");
    } finally {
      setUploadPending(false);
    }
  };

  if (resolved.loading || (profileId !== null && reportState.loading)) {
    return (
      <main className="space-y-3">
        <div className="rounded-3xl bg-white/95 p-6 text-sm text-[#64748b] shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          Loading P&L report...
        </div>
      </main>
    );
  }

  if (!resolved.resolved) {
    return (
      <main className="space-y-3">
        <div className="rounded-3xl bg-white/95 p-6 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          <h1 className="text-2xl font-semibold text-[#0f172a]">Monthly P&L</h1>
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {resolved.errorMessage ?? "Unable to resolve P&L route"}
          </p>
        </div>
      </main>
    );
  }

  const { client, profile } = resolved.resolved;
  const report = reportState.report;
  const months = report?.months ?? [];
  const lineItems = report?.line_items ?? [];
  const warnings = report?.warnings ?? [];

  return (
    <main className="space-y-3">
      <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-[#0f172a] md:text-[2rem]">
              Monthly P&L
            </h1>
            <p className="mt-1 text-sm text-[#4c576f] md:text-base">
              {client.name} - {marketplaceCode.toUpperCase()}
            </p>
          </div>

          {profile ? (
            <div className="flex flex-wrap items-center gap-2 lg:justify-end">
              <button
                onClick={() => void reportState.loadReport(true)}
                disabled={reportState.refreshing}
                className="rounded-xl border border-[#e2e8f0] bg-white px-4 py-2 text-sm font-medium text-[#334155] transition hover:border-[#94a3b8] disabled:opacity-50"
              >
                {reportState.refreshing ? "Refreshing..." : "Refresh"}
              </button>
            </div>
          ) : null}
        </div>

        {!profile ? (
          <div className="mt-5 rounded-2xl border border-[#c7d2fe] bg-[#eef4ff] p-5">
            <h2 className="text-lg font-semibold text-[#0f172a]">Create P&amp;L profile</h2>
            <p className="mt-2 text-sm text-[#475569]">
              This marketplace does not have a P&amp;L profile yet. Create it here, then upload a
              monthly Amazon transaction report to backfill the report.
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <button
                onClick={() => void handleCreateProfile()}
                disabled={createPending}
                className="rounded-xl bg-[#0a6fd6] px-4 py-2 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.2)] transition hover:bg-[#0959ab] disabled:opacity-50"
              >
                {createPending ? "Creating..." : `Create ${marketplaceCode.toUpperCase()} P&L`}
              </button>
            </div>
            {createError ? (
              <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
                {createError}
              </p>
            ) : null}
          </div>
        ) : (
          <>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              {FILTER_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setFilterMode(opt.value)}
                  className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                    filterMode === opt.value
                      ? "bg-[#0f172a] text-white"
                      : "bg-[#f1f5f9] text-[#475569] hover:bg-[#e2e8f0]"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
              <button
                onClick={() => setFilterMode("range")}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                  filterMode === "range"
                    ? "bg-[#0f172a] text-white"
                    : "bg-[#f1f5f9] text-[#475569] hover:bg-[#e2e8f0]"
                }`}
              >
                Custom Range
              </button>
            </div>

            {filterMode === "range" ? (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <label className="text-sm text-[#475569]">From</label>
                <input
                  type="month"
                  value={rangeStart.slice(0, 7)}
                  onChange={(e) => setRangeStart(e.target.value + "-01")}
                  className="rounded-lg border border-[#e2e8f0] px-3 py-1.5 text-sm text-[#0f172a]"
                />
                <label className="text-sm text-[#475569]">To</label>
                <input
                  type="month"
                  value={rangeEnd.slice(0, 7)}
                  onChange={(e) => setRangeEnd(e.target.value + "-01")}
                  className="rounded-lg border border-[#e2e8f0] px-3 py-1.5 text-sm text-[#0f172a]"
                />
              </div>
            ) : null}
          </>
        )}
      </div>

      {profile ? (
        <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-[#0f172a]">Backfill transaction report</h2>
              <p className="mt-1 text-sm text-[#475569]">
                Upload the Amazon Monthly Unified Transaction Report CSV for this marketplace.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <label className="rounded-xl border border-[#dbe4f0] bg-white px-4 py-2 text-sm font-medium text-[#334155] transition hover:border-[#94a3b8]">
                <input
                  type="file"
                  accept=".csv,.txt,.tsv"
                  className="hidden"
                  onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
                />
                {selectedFile ? selectedFile.name : "Choose file"}
              </label>
              <button
                onClick={() => void handleUpload()}
                disabled={!selectedFile || uploadPending}
                className="rounded-xl bg-[#0a6fd6] px-4 py-2 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.2)] transition hover:bg-[#0959ab] disabled:opacity-50"
              >
                {uploadPending ? "Uploading..." : "Upload report"}
              </button>
            </div>
          </div>

          {uploadSuccess ? (
            <p className="mt-4 rounded-xl border border-[#86efac]/40 bg-[#dcfce7] px-4 py-3 text-sm text-[#166534]">
              {uploadSuccess}
            </p>
          ) : null}
          {uploadError ? (
            <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
              {uploadError}
            </p>
          ) : null}
        </div>
      ) : null}

      {warnings.length > 0 ? (
        <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
          <div className="space-y-2">
            {warnings.map((warning, index) => (
              <WarningBanner key={index} warning={warning} />
            ))}
          </div>
        </div>
      ) : null}

      {reportState.errorMessage ? (
        <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          <p className="rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {reportState.errorMessage}
          </p>
        </div>
      ) : null}

      {months.length > 0 && lineItems.length > 0 ? (
        <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#e2e8f0]">
                  <th className="sticky left-0 z-10 bg-white py-3 pr-4 text-left font-semibold text-[#334155]">
                    Line Item
                  </th>
                  {months.map((month) => (
                    <th
                      key={month}
                      className="whitespace-nowrap px-3 py-3 text-right font-semibold text-[#334155]"
                    >
                      {formatMonth(month)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {lineItems.map((item) => (
                  <tr
                    key={item.key}
                    className={`border-b border-[#f1f5f9] ${lineItemRowClass(item)}`}
                  >
                    <td className="sticky left-0 z-10 whitespace-nowrap py-2.5 pr-4 text-left">
                      <span
                        className={
                          item.key === "net_earnings"
                            ? ""
                            : SUMMARY_KEYS.has(item.key)
                              ? "text-[#0f172a]"
                              : "text-[#475569]"
                        }
                      >
                        {item.label}
                      </span>
                    </td>
                    {months.map((month) => {
                      const value = item.months[month] ?? "0.00";
                      return (
                        <td
                          key={month}
                          className={`whitespace-nowrap px-3 py-2.5 text-right tabular-nums ${amountClass(value, item)}`}
                        >
                          {formatAmount(value)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {profile && months.length === 0 && !reportState.errorMessage ? (
        <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
          <p className="text-sm text-[#64748b]">
            No P&amp;L data available for the selected period yet. Upload a transaction report to
            backfill this marketplace.
          </p>
        </div>
      ) : null}
    </main>
  );
}

function WarningBanner({ warning }: { warning: PnlWarning }) {
  const colorMap: Record<string, { border: string; bg: string; text: string }> = {
    missing_cogs: { border: "border-[#fbbf24]/40", bg: "bg-[#fef3c7]", text: "text-[#92400e]" },
    unmapped_rows: { border: "border-[#fbbf24]/40", bg: "bg-[#fef3c7]", text: "text-[#92400e]" },
    missing_data: { border: "border-[#94a3b8]/40", bg: "bg-[#f1f5f9]", text: "text-[#475569]" },
  };
  const colors = colorMap[warning.type] ?? colorMap.missing_data;

  return (
    <div
      className={`rounded-xl border ${colors.border} ${colors.bg} px-4 py-3 text-sm ${colors.text}`}
    >
      <span className="font-medium">{warning.message}</span>
      <span className="ml-2 text-xs opacity-75">
        ({warning.months.map(formatMonth).join(", ")})
      </span>
    </div>
  );
}
