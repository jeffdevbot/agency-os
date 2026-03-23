"use client";

import PnlMonthRangePicker from "./PnlMonthRangePicker";
import type { PnlFilterMode, PnlProfile } from "../pnl/_lib/pnlApi";
import type { PnlDisplayMode } from "../pnl/_lib/pnlPresentation";

type Props = {
  clientName: string;
  marketplaceCode: string;
  profile: PnlProfile | null;
  viewMode: "standard" | "yoy";
  filterMode: PnlFilterMode;
  rangeStart: string;
  rangeEnd: string;
  selectedYear: number;
  availableYears: number[];
  settingsOpen: boolean;
  displayMode: PnlDisplayMode;
  showTotals: boolean;
  exportPending: boolean;
  onViewModeChange: (value: "standard" | "yoy") => void;
  onFilterModeChange: (value: PnlFilterMode) => void;
  onRangeStartChange: (value: string) => void;
  onRangeEndChange: (value: string) => void;
  onYearChange: (value: number) => void;
  onToggleSettings: () => void;
  onDisplayModeChange: (value: PnlDisplayMode) => void;
  onToggleTotals: () => void;
  onExport: () => void;
};

export default function PnlReportHeader({
  clientName,
  marketplaceCode,
  profile,
  viewMode,
  filterMode,
  rangeStart,
  rangeEnd,
  selectedYear,
  availableYears,
  settingsOpen,
  displayMode,
  showTotals,
  exportPending,
  onViewModeChange,
  onFilterModeChange,
  onRangeStartChange,
  onRangeEndChange,
  onYearChange,
  onToggleSettings,
  onDisplayModeChange,
  onToggleTotals,
  onExport,
}: Props) {
  const currentYearIndex = availableYears.indexOf(selectedYear);
  const previousYear = currentYearIndex >= 0 ? availableYears[currentYearIndex + 1] : undefined;
  const nextYear = currentYearIndex > 0 ? availableYears[currentYearIndex - 1] : undefined;

  return (
    <div className="relative z-20 rounded-3xl bg-white/95 p-3.5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-4">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[#9a5b16]">
            Amazon Finance Reporting
          </p>
          <h1 className="mt-2 text-[2.5rem] font-semibold leading-none text-[#0f172a] md:text-[2.05rem]">
            Amazon P&amp;L
          </h1>
          <div className="mt-2.5 flex flex-wrap items-center gap-2">
            <div className="rounded-2xl border border-[#dbe4f0] bg-[#f8fafc] px-3 py-2">
              <p className="text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-[#64748b]">
                Account
              </p>
              <p className="mt-0.5 text-[0.95rem] font-semibold text-[#0f172a] md:text-base">{clientName}</p>
            </div>
            <div className="rounded-2xl border border-[#dbe4f0] bg-white px-3 py-2">
              <p className="text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-[#64748b]">
                Marketplace
              </p>
              <p className="mt-0.5 text-[0.95rem] font-semibold text-[#0a6fd6] md:text-base">
                {marketplaceCode.toUpperCase()}
              </p>
            </div>
          </div>
          <p className="mt-2.5 text-sm text-[#64748b] md:text-[0.92rem]">
            Monthly finance reporting from uploaded Amazon transaction data.
          </p>
        </div>

        {profile ? (
          <div className="flex shrink-0 flex-col items-start gap-2 xl:items-end">
            <div className="flex flex-wrap items-center gap-2 xl:justify-end">
              <div className="flex items-center rounded-full border border-[#dbe4f0] bg-[#f8fafc] p-1">
                <button
                  type="button"
                  onClick={() => onViewModeChange("standard")}
                  className={`rounded-full px-2.5 py-1.5 text-sm font-semibold transition ${
                    viewMode === "standard"
                      ? "bg-[#0f172a] text-white"
                      : "text-[#475569] hover:text-[#0f172a]"
                  }`}
                >
                  Standard
                </button>
                <button
                  type="button"
                  onClick={() => onViewModeChange("yoy")}
                  className={`rounded-full px-2.5 py-1.5 text-sm font-semibold transition ${
                    viewMode === "yoy"
                      ? "bg-[#0f172a] text-white"
                      : "text-[#475569] hover:text-[#0f172a]"
                  }`}
                >
                  YoY
                </button>
              </div>

              {viewMode === "standard" ? (
                <PnlMonthRangePicker
                  filterMode={filterMode}
                  rangeStart={rangeStart}
                  rangeEnd={rangeEnd}
                  onFilterModeChange={onFilterModeChange}
                  onRangeStartChange={onRangeStartChange}
                  onRangeEndChange={onRangeEndChange}
                />
              ) : (
                <div className="flex items-center gap-2 rounded-full border border-[#dbe4f0] bg-white px-2 py-1.5">
                  <button
                    type="button"
                    onClick={() => previousYear && onYearChange(previousYear)}
                    disabled={previousYear === undefined}
                    className="rounded-full px-2 py-1 text-sm font-semibold text-[#475569] transition hover:text-[#0f172a] disabled:cursor-not-allowed disabled:text-[#cbd5e1]"
                  >
                    ←
                  </button>
                  <span className="min-w-[4.5rem] text-center text-sm font-semibold text-[#0f172a]">
                    {selectedYear}
                  </span>
                  <button
                    type="button"
                    onClick={() => nextYear && onYearChange(nextYear)}
                    disabled={nextYear === undefined}
                    className="rounded-full px-2 py-1 text-sm font-semibold text-[#475569] transition hover:text-[#0f172a] disabled:cursor-not-allowed disabled:text-[#cbd5e1]"
                  >
                    →
                  </button>
                </div>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-1.5 xl:justify-end">
              {viewMode === "standard" ? (
                <>
                  <div className="flex items-center rounded-full border border-[#dbe4f0] bg-[#f8fafc] p-1">
                    <button
                      type="button"
                      onClick={() => onDisplayModeChange("dollars")}
                      className={`rounded-full px-2 py-1.5 text-sm font-semibold transition ${
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
                      className={`rounded-full px-2 py-1.5 text-sm font-semibold transition ${
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
                    className="rounded-full border border-[#dbe4f0] bg-white px-2 py-1.5 text-sm font-semibold text-[#0a6fd6] transition hover:border-[#94a3b8] hover:text-[#0f172a] disabled:cursor-not-allowed disabled:text-[#94a3b8]"
                  >
                    {exportPending ? "Exporting..." : "Export to Excel"}
                  </button>
                </>
              ) : null}
              <button
                type="button"
                onClick={onToggleTotals}
                className={`rounded-full border px-2 py-1.5 text-sm font-semibold transition ${
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
