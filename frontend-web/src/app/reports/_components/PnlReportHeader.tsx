"use client";

import PnlMonthRangePicker from "./PnlMonthRangePicker";
import type { PnlFilterMode, PnlProfile } from "../pnl/_lib/pnlApi";
import type { PnlDisplayMode } from "../pnl/_lib/pnlPresentation";

type Props = {
  clientName: string;
  marketplaceCode: string;
  profile: PnlProfile | null;
  filterMode: PnlFilterMode;
  rangeStart: string;
  rangeEnd: string;
  settingsOpen: boolean;
  displayMode: PnlDisplayMode;
  showTotals: boolean;
  exportPending: boolean;
  onFilterModeChange: (value: PnlFilterMode) => void;
  onRangeStartChange: (value: string) => void;
  onRangeEndChange: (value: string) => void;
  onToggleSettings: () => void;
  onDisplayModeChange: (value: PnlDisplayMode) => void;
  onToggleTotals: () => void;
  onExport: () => void;
};

export default function PnlReportHeader({
  clientName,
  marketplaceCode,
  profile,
  filterMode,
  rangeStart,
  rangeEnd,
  settingsOpen,
  displayMode,
  showTotals,
  exportPending,
  onFilterModeChange,
  onRangeStartChange,
  onRangeEndChange,
  onToggleSettings,
  onDisplayModeChange,
  onToggleTotals,
  onExport,
}: Props) {
  return (
    <div className="relative z-20 rounded-3xl bg-white/95 p-4 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-5">
      <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[#9a5b16]">
            Amazon Finance Reporting
          </p>
          <h1 className="mt-2 text-3xl font-semibold text-[#0f172a] md:text-[2.15rem]">
            Amazon P&amp;L
          </h1>
          <div className="mt-3 flex flex-wrap items-center gap-2.5">
            <div className="rounded-2xl border border-[#dbe4f0] bg-[#f8fafc] px-3.5 py-2.5">
              <p className="text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-[#64748b]">
                Account
              </p>
              <p className="mt-1 text-base font-semibold text-[#0f172a] md:text-lg">{clientName}</p>
            </div>
            <div className="rounded-2xl border border-[#dbe4f0] bg-white px-3.5 py-2.5">
              <p className="text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-[#64748b]">
                Marketplace
              </p>
              <p className="mt-1 text-base font-semibold text-[#0a6fd6] md:text-lg">
                {marketplaceCode.toUpperCase()}
              </p>
            </div>
          </div>
          <p className="mt-3 text-sm text-[#64748b] md:text-[0.95rem]">
            Monthly finance reporting from uploaded Amazon transaction data.
          </p>
        </div>

        {profile ? (
          <div className="flex shrink-0 flex-col items-start gap-2.5 xl:items-end">
            <PnlMonthRangePicker
              filterMode={filterMode}
              rangeStart={rangeStart}
              rangeEnd={rangeEnd}
              onFilterModeChange={onFilterModeChange}
              onRangeStartChange={onRangeStartChange}
              onRangeEndChange={onRangeEndChange}
            />
            <div className="flex flex-wrap items-center gap-2 xl:justify-end">
              <div className="flex items-center rounded-full border border-[#dbe4f0] bg-[#f8fafc] p-1">
                <button
                  type="button"
                  onClick={() => onDisplayModeChange("dollars")}
                  className={`rounded-full px-2.5 py-1.5 text-sm font-semibold transition ${
                    displayMode === "dollars"
                      ? "bg-[#0f172a] text-white"
                      : "text-[#475569] hover:text-[#0f172a]"
                  }`}
                >
                  Dollars
                </button>
                <button
                  type="button"
                  onClick={() => onDisplayModeChange("percent")}
                  className={`rounded-full px-2.5 py-1.5 text-sm font-semibold transition ${
                    displayMode === "percent"
                      ? "bg-[#0f172a] text-white"
                      : "text-[#475569] hover:text-[#0f172a]"
                  }`}
                >
                  % of Revenue
                </button>
              </div>
              <button
                type="button"
                onClick={onExport}
                disabled={exportPending}
                className="rounded-full border border-[#dbe4f0] bg-white px-2.5 py-1.5 text-sm font-semibold text-[#0a6fd6] transition hover:border-[#94a3b8] hover:text-[#0f172a] disabled:cursor-not-allowed disabled:text-[#94a3b8]"
              >
                {exportPending ? "Exporting..." : "Export to Excel"}
              </button>
              <button
                type="button"
                onClick={onToggleTotals}
                className={`rounded-full border px-2.5 py-1.5 text-sm font-semibold transition ${
                  showTotals
                    ? "border-[#0f172a] bg-[#0f172a] text-white"
                    : "border-[#dbe4f0] bg-white text-[#475569] hover:border-[#94a3b8] hover:text-[#0f172a]"
                }`}
              >
                {showTotals ? "Hide totals" : "Show totals"}
              </button>
            </div>
            <button
              onClick={onToggleSettings}
              className="pr-1 text-sm font-semibold text-[#64748b] transition hover:text-[#0f172a] hover:underline"
            >
              {settingsOpen ? "Hide settings" : "Open settings"}
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
