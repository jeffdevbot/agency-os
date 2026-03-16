"use client";

import { useEffect, useState } from "react";
import type { PnlActiveImportSummary } from "../pnl/_lib/pnlActiveImportSummary";
import {
  describeImportSource,
  formatImportSourceType,
  formatMonth,
  formatTimestamp,
} from "../pnl/_lib/pnlDisplay";

type Props = {
  monthsInView: string[];
  activeImports: PnlActiveImportSummary[];
  loading: boolean;
  errorMessage: string | null;
};

export default function PnlProvenanceCard({
  monthsInView,
  activeImports,
  loading,
  errorMessage,
}: Props) {
  const [visibleCount, setVisibleCount] = useState(6);

  useEffect(() => {
    setVisibleCount(6);
  }, [activeImports.length]);

  const visibleImports = activeImports.slice(0, visibleCount);
  const remainingCount = Math.max(activeImports.length - visibleCount, 0);

  return (
    <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[#0f172a]">Import history</h2>
          <p className="mt-1 text-sm text-[#475569]">
            Shows which import records are currently driving the visible Amazon P&amp;L months.
            Only the newest six cards are expanded by default.
          </p>
        </div>
        {loading ? <p className="text-sm text-[#64748b]">Loading import history...</p> : null}
      </div>

      {errorMessage ? (
        <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
          {errorMessage}
        </p>
      ) : null}

      {monthsInView.length === 0 ? (
        <p className="mt-4 text-sm text-[#64748b]">
          Import history will appear once the selected date range includes active Amazon P&amp;L data.
        </p>
      ) : activeImports.length === 0 && !loading ? (
        <p className="mt-4 text-sm text-[#64748b]">
          No active import metadata was found for the months currently in view.
        </p>
      ) : (
        <>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            {visibleImports.map((activeImport) => (
            <div
              key={activeImport.import_id}
              className="rounded-2xl border border-[#dbe4f0] bg-[#f8fafc] p-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span className="rounded-full border border-[#cbd5e1] bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-[#334155]">
                  {formatImportSourceType(activeImport.source_type)}
                </span>
                <span className="rounded-full bg-[#e2e8f0] px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-[#475569]">
                  {activeImport.import_status}
                </span>
              </div>
              <p className="mt-3 text-base font-semibold text-[#0f172a]">
                {describeImportSource(activeImport.source_type, activeImport.source_filename)}
              </p>
              <dl className="mt-3 space-y-2 text-sm text-[#475569]">
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                  <dt className="font-medium text-[#334155]">Import ID</dt>
                  <dd className="break-all font-mono text-xs text-[#0f172a]">
                    {activeImport.import_id}
                  </dd>
                </div>
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                  <dt className="font-medium text-[#334155]">Created</dt>
                  <dd>{formatTimestamp(activeImport.created_at)}</dd>
                </div>
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                  <dt className="font-medium text-[#334155]">Finished</dt>
                  <dd>{formatTimestamp(activeImport.finished_at)}</dd>
                </div>
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                  <dt className="font-medium text-[#334155]">Status</dt>
                  <dd className="capitalize">{activeImport.import_status}</dd>
                </div>
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                  <dt className="font-medium text-[#334155]">Active months</dt>
                  <dd>{activeImport.months.map(formatMonth).join(", ")}</dd>
                </div>
              </dl>
            </div>
            ))}
          </div>

          {activeImports.length > 6 ? (
            <div className="mt-4 flex flex-wrap items-center gap-3">
              {remainingCount > 0 ? (
                <button
                  type="button"
                  onClick={() => setVisibleCount((count) => count + 6)}
                  className="rounded-full border border-[#cbd5e1] bg-white px-4 py-2 text-sm font-semibold text-[#334155] transition hover:border-[#94a3b8] hover:text-[#0f172a]"
                >
                  See {Math.min(remainingCount, 6)} more
                </button>
              ) : null}
              {visibleCount > 6 ? (
                <button
                  type="button"
                  onClick={() => setVisibleCount(6)}
                  className="rounded-full px-4 py-2 text-sm font-semibold text-[#64748b] transition hover:text-[#0f172a]"
                >
                  Show fewer
                </button>
              ) : null}
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
