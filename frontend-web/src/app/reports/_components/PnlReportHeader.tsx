"use client";

import type { PnlFilterMode, PnlProfile } from "../pnl/_lib/pnlApi";
import { FILTER_OPTIONS } from "../pnl/_lib/pnlDisplay";

type Props = {
  clientName: string;
  marketplaceCode: string;
  profile: PnlProfile | null;
  filterMode: PnlFilterMode;
  rangeStart: string;
  rangeEnd: string;
  refreshing: boolean;
  onFilterModeChange: (value: PnlFilterMode) => void;
  onRangeStartChange: (value: string) => void;
  onRangeEndChange: (value: string) => void;
  onRefresh: () => void;
};

export default function PnlReportHeader({
  clientName,
  marketplaceCode,
  profile,
  filterMode,
  rangeStart,
  rangeEnd,
  refreshing,
  onFilterModeChange,
  onRangeStartChange,
  onRangeEndChange,
  onRefresh,
}: Props) {
  return (
    <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-[#0f172a] md:text-[2rem]">Monthly P&L</h1>
          <p className="mt-1 text-sm text-[#4c576f] md:text-base">
            {clientName} - {marketplaceCode.toUpperCase()}
          </p>
          <p className="mt-2 text-sm text-[#64748b]">
            Standalone finance reporting surface. This does not reuse WBR syncs, row trees, or
            WBR section tabs.
          </p>
        </div>

        {profile ? (
          <div className="flex flex-wrap items-center gap-2 lg:justify-end">
            <button
              onClick={onRefresh}
              disabled={refreshing}
              className="rounded-xl border border-[#e2e8f0] bg-white px-4 py-2 text-sm font-medium text-[#334155] transition hover:border-[#94a3b8] disabled:opacity-50"
            >
              {refreshing ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        ) : null}
      </div>

      {profile ? (
        <>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            {FILTER_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => onFilterModeChange(opt.value)}
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
              onClick={() => onFilterModeChange("range")}
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
                onChange={(e) => onRangeStartChange(`${e.target.value}-01`)}
                className="rounded-lg border border-[#e2e8f0] px-3 py-1.5 text-sm text-[#0f172a]"
              />
              <label className="text-sm text-[#475569]">To</label>
              <input
                type="month"
                value={rangeEnd.slice(0, 7)}
                onChange={(e) => onRangeEndChange(`${e.target.value}-01`)}
                className="rounded-lg border border-[#e2e8f0] px-3 py-1.5 text-sm text-[#0f172a]"
              />
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
