"use client";

import { useState } from "react";
import { useResolvedWbrProfile } from "../_lib/useResolvedWbrProfile";
import { useWbrSection1Report } from "../_lib/useWbrSection1Report";
import { useWbrSection2Report } from "../_lib/useWbrSection2Report";
import { useWbrSection3Report } from "../_lib/useWbrSection3Report";
import { useWbrWorkbookExport } from "../_lib/useWbrWorkbookExport";
import WbrAdvertisingPane from "./WbrAdvertisingPane";
import WbrInventoryReturnsPane from "./WbrInventoryReturnsPane";
import WbrReportSectionTabs, { type WbrReportSection } from "./WbrReportSectionTabs";
import WbrTrafficSalesPane from "./WbrTrafficSalesPane";
import { buildDisplayRows } from "./wbrSection1RowDisplay";

type Props = {
  clientSlug: string;
  marketplaceCode: string;
};

export default function WbrSection1ReportScreen({ clientSlug, marketplaceCode }: Props) {
  const resolved = useResolvedWbrProfile(clientSlug, marketplaceCode);
  const reportState = useWbrSection1Report(resolved.profile?.id ?? null, 4);
  const section2ReportState = useWbrSection2Report(resolved.profile?.id ?? null, 4);
  const section3ReportState = useWbrSection3Report(resolved.profile?.id ?? null, 4);
  const workbookExport = useWbrWorkbookExport(resolved.profile?.id ?? null);
  const [hideEmptyRows, setHideEmptyRows] = useState(true);
  const [newestFirst, setNewestFirst] = useState(true);
  const [horizontalLayout, setHorizontalLayout] = useState(true);
  const [activeSection, setActiveSection] = useState<WbrReportSection>("traffic_sales");

  if (resolved.loading || reportState.loading || section2ReportState.loading) {
    return (
      <main className="space-y-3">
        <div className="rounded-3xl bg-white/95 p-6 text-sm text-[#64748b] shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          Loading WBR report...
        </div>
      </main>
    );
  }

  if (!resolved.profile || !resolved.summary) {
    return (
      <main className="space-y-3">
        <div className="rounded-3xl bg-white/95 p-6 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
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
  const section2Report = section2ReportState.report;
  const section2Rows = section2Report?.rows ?? [];
  const section2Weeks = section2Report?.weeks ?? weeks;
  const section3Report = section3ReportState.report;
  const section3Rows = section3Report?.rows ?? [];
  const section3ReturnsWeeks = section3Report?.returns_weeks ?? [];

  const referenceRowOrder = buildDisplayRows(rows, false).map((row) => row.id);

  return (
    <main className="space-y-3">
      <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-[#0f172a] md:text-[2rem]">Weekly Business Review</h1>
            <p className="mt-1 text-sm text-[#4c576f] md:text-base">
              {resolved.summary.client.name} - {resolved.profile.marketplace_code}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 lg:justify-end">
            <button
              onClick={() =>
                void workbookExport.downloadWorkbook({
                  weeks: 4,
                  hideEmptyRows,
                  newestFirst,
                })
              }
              disabled={workbookExport.exporting}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-[#0a6fd6] shadow-sm transition hover:-translate-y-0.5 hover:shadow disabled:cursor-not-allowed disabled:text-slate-400 md:text-sm"
              title="Download the current WBR as an Excel workbook"
            >
              {workbookExport.exporting ? "Exporting..." : "Export to Excel"}
            </button>

            <button
              onClick={() => {
                void resolved.loadRoute();
                void reportState.loadReport(true);
                void section2ReportState.loadReport(true);
                void section3ReportState.loadReport(true);
              }}
              disabled={reportState.refreshing}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-[#0a6fd6] shadow-sm transition hover:-translate-y-0.5 hover:shadow disabled:cursor-not-allowed disabled:text-slate-400 md:text-sm"
              title="Reload the current profile and report data"
            >
              {reportState.refreshing ? "Refreshing..." : "Refresh"}
            </button>

            <label className="inline-flex items-center gap-2 rounded-lg border border-[#c7d8f5] bg-[#f7faff] px-3 py-1.5 text-xs text-[#0f172a] md:text-sm">
              <input
                type="checkbox"
                checked={hideEmptyRows}
                onChange={(event) => setHideEmptyRows(event.target.checked)}
                className="h-4 w-4 rounded border-[#94a3b8] text-[#0a6fd6] focus:ring-[#0a6fd6]"
              />
              <span className="font-medium">Hide empty rows</span>
            </label>

            <label className="inline-flex items-center gap-2 rounded-lg border border-[#c7d8f5] bg-[#f7faff] px-3 py-1.5 text-xs text-[#0f172a] md:text-sm">
              <input
                type="checkbox"
                checked={newestFirst}
                onChange={(event) => setNewestFirst(event.target.checked)}
                className="h-4 w-4 rounded border-[#94a3b8] text-[#0a6fd6] focus:ring-[#0a6fd6]"
              />
              <span className="font-medium">Newest first</span>
            </label>

            <label className="inline-flex items-center gap-2 rounded-lg border border-[#c7d8f5] bg-[#f7faff] px-3 py-1.5 text-xs text-[#0f172a] md:text-sm">
              <input
                type="checkbox"
                checked={horizontalLayout}
                onChange={(event) => setHorizontalLayout(event.target.checked)}
                className="h-4 w-4 rounded border-[#94a3b8] text-[#0a6fd6] focus:ring-[#0a6fd6]"
              />
              <span className="font-medium">Horizontal</span>
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

        {section2ReportState.errorMessage ? (
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {section2ReportState.errorMessage}
          </p>
        ) : null}

        {section3ReportState.errorMessage ? (
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {section3ReportState.errorMessage}
          </p>
        ) : null}

        {workbookExport.errorMessage ? (
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {workbookExport.errorMessage}
          </p>
        ) : null}
      </div>

      <WbrReportSectionTabs activeSection={activeSection} onChange={setActiveSection} />

      {activeSection === "traffic_sales" ? (
        <WbrTrafficSalesPane
          weeks={weeks}
          rows={rows}
          hideEmptyRows={hideEmptyRows}
          newestFirst={newestFirst}
          horizontalLayout={horizontalLayout}
        />
      ) : null}

      {activeSection === "advertising" ? (
        <WbrAdvertisingPane
          weeks={section2Weeks}
          rows={section2Rows}
          hideEmptyRows={hideEmptyRows}
          newestFirst={newestFirst}
          horizontalLayout={horizontalLayout}
          referenceRowOrder={referenceRowOrder}
        />
      ) : null}

      {activeSection === "inventory_returns" ? (
        <WbrInventoryReturnsPane
          loading={section3ReportState.loading}
          rows={section3Rows}
          returnsWeeks={section3ReturnsWeeks}
          weekCount={section3ReportState.report?.weeks?.length ?? 4}
          hideEmptyRows={hideEmptyRows}
          referenceRowOrder={referenceRowOrder}
        />
      ) : null}
    </main>
  );
}
