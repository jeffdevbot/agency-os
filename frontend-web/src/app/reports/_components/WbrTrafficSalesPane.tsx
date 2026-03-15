"use client";

import type { WbrSection1Row, WbrSection1Week } from "../wbr/_lib/wbrSection1Api";
import WbrSection1HorizontalTable from "./WbrSection1HorizontalTable";
import WbrSection1MetricTable from "./WbrSection1MetricTable";
import { hasAnyActivity } from "./wbrSection1RowDisplay";

type Props = {
  weeks: WbrSection1Week[];
  rows: WbrSection1Row[];
  hideEmptyRows: boolean;
  newestFirst: boolean;
  horizontalLayout: boolean;
};

export default function WbrTrafficSalesPane({
  weeks,
  rows,
  hideEmptyRows,
  newestFirst,
  horizontalLayout,
}: Props) {
  const activityPresent = hasAnyActivity(rows);

  if (rows.length === 0) {
    return (
      <div className="rounded-3xl bg-white/95 p-6 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          No active WBR rows are configured for this profile. Create or import leaf rows in Settings first.
        </p>
      </div>
    );
  }

  if (!activityPresent) {
    return (
      <div className="rounded-3xl bg-white/95 p-6 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          No synced Section 1 business data is showing for the current 4-week window. Run a Windsor sync from the Sync page.
        </p>
      </div>
    );
  }

  if (horizontalLayout) {
    return (
      <WbrSection1HorizontalTable
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
      />
    );
  }

  return (
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
        title="Conversion Rate"
        metricKey="conversion_rate"
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
    </>
  );
}
