"use client";

import { useState } from "react";
import { useResolvedPnlProfile } from "../pnl/_lib/useResolvedPnlProfile";
import { usePnlReport } from "../pnl/_lib/usePnlReport";
import type { PnlFilterMode, PnlLineItem, PnlWarning } from "../pnl/_lib/pnlApi";

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

// Summary/derived rows get bold styling
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

// ── Component ────────────────────────────────────────────────────────

export default function PnlReportScreen({ clientSlug, marketplaceCode }: Props) {
  const resolved = useResolvedPnlProfile(clientSlug, marketplaceCode);
  const [filterMode, setFilterMode] = useState<PnlFilterMode>("ytd");
  const reportState = usePnlReport(
    resolved.resolved?.profile.id ?? null,
    filterMode,
  );

  // Loading state
  if (resolved.loading || reportState.loading) {
    return (
      <main className="space-y-3">
        <div className="rounded-3xl bg-white/95 p-6 text-sm text-[#64748b] shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          Loading P&L report...
        </div>
      </main>
    );
  }

  // Error state
  if (!resolved.resolved) {
    return (
      <main className="space-y-3">
        <div className="rounded-3xl bg-white/95 p-6 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          <h1 className="text-2xl font-semibold text-[#0f172a]">Monthly P&L</h1>
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {resolved.errorMessage ?? "Unable to resolve P&L profile"}
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
      {/* Header */}
      <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-[#0f172a] md:text-[2rem]">
              Monthly P&L
            </h1>
            <p className="mt-1 text-sm text-[#4c576f] md:text-base">
              {client.name} - {profile.marketplace_code}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 lg:justify-end">
            <button
              onClick={() => void reportState.loadReport(true)}
              disabled={reportState.refreshing}
              className="rounded-xl border border-[#e2e8f0] bg-white px-4 py-2 text-sm font-medium text-[#334155] transition hover:border-[#94a3b8] disabled:opacity-50"
            >
              {reportState.refreshing ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </div>

        {/* Filter bar */}
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
        </div>
      </div>

      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
          <div className="space-y-2">
            {warnings.map((w, i) => (
              <WarningBanner key={i} warning={w} />
            ))}
          </div>
        </div>
      )}

      {/* Report error */}
      {reportState.errorMessage && (
        <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          <p className="rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {reportState.errorMessage}
          </p>
        </div>
      )}

      {/* P&L Table */}
      {months.length > 0 && lineItems.length > 0 && (
        <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#e2e8f0]">
                  <th className="sticky left-0 z-10 bg-white py-3 pr-4 text-left font-semibold text-[#334155]">
                    Line Item
                  </th>
                  {months.map((m) => (
                    <th
                      key={m}
                      className="whitespace-nowrap px-3 py-3 text-right font-semibold text-[#334155]"
                    >
                      {formatMonth(m)}
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
                    {months.map((m) => {
                      const val = item.months[m] ?? "0.00";
                      return (
                        <td
                          key={m}
                          className={`whitespace-nowrap px-3 py-2.5 text-right tabular-nums ${amountClass(val, item)}`}
                        >
                          {formatAmount(val)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* No data state */}
      {months.length === 0 && !reportState.errorMessage && (
        <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
          <p className="text-sm text-[#64748b]">
            No P&L data available for the selected period. Upload transaction reports to get started.
          </p>
        </div>
      )}
    </main>
  );
}

// ── Warning sub-component ────────────────────────────────────────────

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
