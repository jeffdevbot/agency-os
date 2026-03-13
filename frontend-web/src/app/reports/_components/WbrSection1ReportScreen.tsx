"use client";

import { useState } from "react";
import { useResolvedWbrProfile } from "../_lib/useResolvedWbrProfile";
import { useWbrSection1Report } from "../_lib/useWbrSection1Report";
import WbrSection1MetricTable from "./WbrSection1MetricTable";
import { hasAnyActivity } from "./wbrSection1RowDisplay";

type Props = {
  clientSlug: string;
  marketplaceCode: string;
};

export default function WbrSection1ReportScreen({ clientSlug, marketplaceCode }: Props) {
  const resolved = useResolvedWbrProfile(clientSlug, marketplaceCode);
  const reportState = useWbrSection1Report(resolved.profile?.id ?? null, 4);
  const [hideEmptyRows, setHideEmptyRows] = useState(true);
  const [newestFirst, setNewestFirst] = useState(true);

  if (resolved.loading || reportState.loading) {
    return (
      <main className="space-y-4">
        <div className="rounded-3xl bg-white/95 p-8 text-sm text-[#64748b] shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          Loading WBR report...
        </div>
      </main>
    );
  }

  if (!resolved.profile || !resolved.summary) {
    return (
      <main className="space-y-4">
        <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          <h1 className="text-2xl font-semibold text-[#0f172a]">WBR</h1>
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {resolved.errorMessage ?? "Unable to resolve WBR profile"}
          </p>
        </div>
      </main>
    );
  }

  const report = reportState.report;
  const rows = report?.rows ?? [];
  const weeks = report?.weeks ?? [];
  const activityPresent = hasAnyActivity(rows);

  return (
    <main className="space-y-4">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h1 className="text-3xl font-semibold text-[#0f172a]">Weekly Business Review</h1>
            <p className="mt-2 text-base text-[#4c576f]">
              {resolved.summary.client.name} - {resolved.profile.marketplace_code}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3 lg:justify-end">
            <button
              onClick={() => {
                void resolved.loadRoute();
                void reportState.loadReport(true);
              }}
              disabled={reportState.refreshing}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-[#0a6fd6] shadow-sm transition hover:-translate-y-0.5 hover:shadow disabled:cursor-not-allowed disabled:text-slate-400"
              title="Reload the current profile and report data"
            >
              {reportState.refreshing ? "Refreshing..." : "Refresh"}
            </button>

            <label className="inline-flex items-center gap-2 rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a]">
              <input
                type="checkbox"
                checked={hideEmptyRows}
                onChange={(event) => setHideEmptyRows(event.target.checked)}
                className="h-4 w-4 rounded border-[#94a3b8] text-[#0a6fd6] focus:ring-[#0a6fd6]"
              />
              <span className="font-medium">Hide empty rows</span>
            </label>

            <label className="inline-flex items-center gap-2 rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a]">
              <input
                type="checkbox"
                checked={newestFirst}
                onChange={(event) => setNewestFirst(event.target.checked)}
                className="h-4 w-4 rounded border-[#94a3b8] text-[#0a6fd6] focus:ring-[#0a6fd6]"
              />
              <span className="font-medium">Newest first</span>
            </label>
          </div>
        </div>

        {resolved.errorMessage ? (
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {resolved.errorMessage}
          </p>
        ) : null}

        {reportState.errorMessage ? (
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {reportState.errorMessage}
          </p>
        ) : null}

        {rows.length === 0 ? (
          <p className="mt-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            No active WBR rows are configured for this profile. Create or import leaf rows in Settings first.
          </p>
        ) : !activityPresent ? (
          <p className="mt-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            No synced Section 1 business data is showing for the current 4-week window. Run a Windsor sync from the Sync page.
          </p>
        ) : null}
      </div>

      {rows.length > 0 ? (
        <>
          <WbrSection1MetricTable
            title="Page Views"
            metricKey="page_views"
            weeks={weeks}
            rows={rows}
            hideEmptyRows={hideEmptyRows}
            newestFirst={newestFirst}
          />
          <WbrSection1MetricTable
            title="Unit Sales"
            metricKey="unit_sales"
            weeks={weeks}
            rows={rows}
            hideEmptyRows={hideEmptyRows}
            newestFirst={newestFirst}
          />
          <WbrSection1MetricTable
            title="Sales"
            metricKey="sales"
            weeks={weeks}
            rows={rows}
            hideEmptyRows={hideEmptyRows}
            newestFirst={newestFirst}
          />
          <WbrSection1MetricTable
            title="Conversion Rate"
            metricKey="conversion_rate"
            weeks={weeks}
            rows={rows}
            hideEmptyRows={hideEmptyRows}
            newestFirst={newestFirst}
          />
        </>
      ) : null}
    </main>
  );
}
