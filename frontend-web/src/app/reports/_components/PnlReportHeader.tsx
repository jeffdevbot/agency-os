"use client";

import PnlMonthRangePicker from "./PnlMonthRangePicker";
import type { PnlFilterMode, PnlProfile } from "../pnl/_lib/pnlApi";

type Props = {
  clientName: string;
  marketplaceCode: string;
  profile: PnlProfile | null;
  filterMode: PnlFilterMode;
  rangeStart: string;
  rangeEnd: string;
  settingsOpen: boolean;
  onFilterModeChange: (value: PnlFilterMode) => void;
  onRangeStartChange: (value: string) => void;
  onRangeEndChange: (value: string) => void;
  onToggleSettings: () => void;
};

export default function PnlReportHeader({
  clientName,
  marketplaceCode,
  profile,
  filterMode,
  rangeStart,
  rangeEnd,
  settingsOpen,
  onFilterModeChange,
  onRangeStartChange,
  onRangeEndChange,
  onToggleSettings,
}: Props) {
  return (
    <div className="relative z-20 rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-[#0f172a] md:text-[2rem]">Monthly P&L</h1>
          <p className="mt-1 text-sm text-[#4c576f] md:text-base">
            {clientName} - {marketplaceCode.toUpperCase()}
          </p>
          <p className="mt-2 text-sm text-[#64748b]">
            Monthly finance reporting from uploaded Amazon transaction data.
          </p>
        </div>

        {profile ? (
          <div className="flex flex-wrap items-center gap-4 lg:justify-end">
            <PnlMonthRangePicker
              filterMode={filterMode}
              rangeStart={rangeStart}
              rangeEnd={rangeEnd}
              onFilterModeChange={onFilterModeChange}
              onRangeStartChange={onRangeStartChange}
              onRangeEndChange={onRangeEndChange}
            />
            <button
              onClick={onToggleSettings}
              className="text-sm font-semibold text-[#64748b] transition hover:text-[#0f172a] hover:underline"
            >
              {settingsOpen ? "Hide settings" : "Settings"}
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
