"use client";

import type { PnlActiveImportSummary } from "../pnl/_lib/pnlActiveImportSummary";
import { formatMonth, formatTimestamp } from "../pnl/_lib/pnlDisplay";

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
  return (
    <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[#0f172a]">Active import provenance</h2>
          <p className="mt-1 text-sm text-[#475569]">
            Shows which uploaded Amazon transaction export is currently driving the visible
            Monthly P&amp;L months.
          </p>
        </div>
        {loading ? <p className="text-sm text-[#64748b]">Loading provenance...</p> : null}
      </div>

      {errorMessage ? (
        <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
          {errorMessage}
        </p>
      ) : null}

      {monthsInView.length === 0 ? (
        <p className="mt-4 text-sm text-[#64748b]">
          Provenance will appear once the selected date range includes active Monthly P&amp;L data.
        </p>
      ) : activeImports.length === 0 && !loading ? (
        <p className="mt-4 text-sm text-[#64748b]">
          No active import metadata was found for the months currently in view.
        </p>
      ) : (
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          {activeImports.map((activeImport) => (
            <div
              key={activeImport.import_id}
              className="rounded-2xl border border-[#e2e8f0] bg-[#f8fafc] p-4"
            >
              <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[#9a5b16]">
                Active source
              </p>
              <p className="mt-2 text-base font-semibold text-[#0f172a]">
                {activeImport.source_filename ?? "Unnamed upload"}
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
      )}
    </div>
  );
}
