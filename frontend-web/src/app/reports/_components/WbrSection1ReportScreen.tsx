"use client";

import Link from "next/link";
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
  const normalizedMarketplace = marketplaceCode.toLowerCase();

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
  const qa = report?.qa;
  const activityPresent = hasAnyActivity(rows);

  return (
    <main className="space-y-4">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-2xl font-semibold text-[#0f172a]">
          {resolved.summary.client.name} {resolved.profile.marketplace_code} WBR
        </h1>
        <p className="mt-2 text-sm text-[#4c576f]">
          Section 1 business metrics roll up from Windsor daily ASIN data through your current leaf and parent row tree.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            onClick={() => {
              void resolved.loadRoute();
              void reportState.loadReport(true);
            }}
            disabled={reportState.refreshing}
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
          >
            {reportState.refreshing ? "Refreshing..." : "Refresh"}
          </button>
          <Link
            href={`/reports/${clientSlug}`}
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            Back to Marketplaces
          </Link>
          <Link
            href={`/reports/${clientSlug}/${normalizedMarketplace}/wbr/settings`}
            className="rounded-2xl bg-[#e8eefc] px-4 py-3 text-sm font-semibold text-[#0f172a] transition hover:bg-[#d7e1fb]"
          >
            Settings
          </Link>
          <Link
            href={`/reports/${clientSlug}/${normalizedMarketplace}/wbr/sync`}
            className="rounded-2xl bg-[#e8eefc] px-4 py-3 text-sm font-semibold text-[#0f172a] transition hover:bg-[#d7e1fb]"
          >
            Sync
          </Link>
        </div>

        <label className="mt-6 inline-flex items-center gap-3 rounded-2xl border border-[#c7d8f5] bg-[#f7faff] px-4 py-3 text-sm text-[#0f172a]">
          <input
            type="checkbox"
            checked={hideEmptyRows}
            onChange={(event) => setHideEmptyRows(event.target.checked)}
            className="h-4 w-4 rounded border-[#94a3b8] text-[#0a6fd6] focus:ring-[#0a6fd6]"
          />
          <span className="font-medium">Hide rows with no data</span>
        </label>

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

        {qa ? (
          <div className="mt-4 grid gap-3 md:grid-cols-4">
            <div className="rounded-2xl border border-[#c7d8f5] bg-[#f7faff] p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Active Rows</p>
              <p className="mt-2 text-2xl font-semibold text-[#0f172a]">{qa.active_row_count}</p>
            </div>
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-emerald-800">Mapped ASINs</p>
              <p className="mt-2 text-2xl font-semibold text-emerald-950">{qa.mapped_asin_count}</p>
            </div>
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-800">Unmapped ASINs With Activity</p>
              <p className="mt-2 text-2xl font-semibold text-amber-950">{qa.unmapped_asin_count}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Fact Rows In Window</p>
              <p className="mt-2 text-2xl font-semibold text-[#0f172a]">{qa.fact_row_count}</p>
            </div>
          </div>
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
          />
          <WbrSection1MetricTable
            title="Unit Sales"
            metricKey="unit_sales"
            weeks={weeks}
            rows={rows}
            hideEmptyRows={hideEmptyRows}
          />
          <WbrSection1MetricTable
            title="Sales"
            metricKey="sales"
            weeks={weeks}
            rows={rows}
            hideEmptyRows={hideEmptyRows}
          />
          <WbrSection1MetricTable
            title="Conversion Rate"
            metricKey="conversion_rate"
            weeks={weeks}
            rows={rows}
            hideEmptyRows={hideEmptyRows}
          />
        </>
      ) : null}
    </main>
  );
}
