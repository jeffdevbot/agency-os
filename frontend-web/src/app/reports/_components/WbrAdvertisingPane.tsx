"use client";

import type { WbrSection1Week, WbrSection2Row } from "../wbr/_lib/wbrSection1Api";
import WbrSection2HorizontalTable from "./WbrSection2HorizontalTable";
import WbrSection2MetricTable from "./WbrSection2MetricTable";
import { hasAnySection2Activity } from "./wbrSection2RowDisplay";

type Props = {
  weeks: WbrSection1Week[];
  rows: WbrSection2Row[];
  hideEmptyRows: boolean;
  newestFirst: boolean;
  horizontalLayout: boolean;
  referenceRowOrder: string[];
};

export default function WbrAdvertisingPane({
  weeks,
  rows,
  hideEmptyRows,
  newestFirst,
  horizontalLayout,
  referenceRowOrder,
}: Props) {
  const activityPresent = hasAnySection2Activity(rows);

  if (rows.length === 0 || !activityPresent) {
    return (
      <div className="rounded-3xl bg-white/95 p-6 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          No mapped Section 2 ads data is showing for the current 4-week window. Run an Ads API sync, and confirm Pacvue campaign mapping is active for this profile.
        </p>
      </div>
    );
  }

  if (horizontalLayout) {
    return (
      <WbrSection2HorizontalTable
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        referenceRowOrder={referenceRowOrder}
      />
    );
  }

  return (
    <>
      <WbrSection2MetricTable
        title="Impressions"
        metricKey="impressions"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        referenceRowOrder={referenceRowOrder}
      />
      <WbrSection2MetricTable
        title="Clicks"
        metricKey="clicks"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        referenceRowOrder={referenceRowOrder}
      />
      <WbrSection2MetricTable
        title="CTR"
        metricKey="ctr_pct"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        referenceRowOrder={referenceRowOrder}
      />
      <WbrSection2MetricTable
        title="Ad Spend"
        metricKey="ad_spend"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        referenceRowOrder={referenceRowOrder}
      />
      <WbrSection2MetricTable
        title="CPC"
        metricKey="cpc"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        referenceRowOrder={referenceRowOrder}
      />
      <WbrSection2MetricTable
        title="Ad Orders"
        metricKey="ad_orders"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        referenceRowOrder={referenceRowOrder}
      />
      <WbrSection2MetricTable
        title="Ad Conversion Rate"
        metricKey="ad_conversion_rate"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        referenceRowOrder={referenceRowOrder}
      />
      <WbrSection2MetricTable
        title="Ad Sales"
        metricKey="ad_sales"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        referenceRowOrder={referenceRowOrder}
      />
      <WbrSection2MetricTable
        title="ACoS"
        metricKey="acos_pct"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        referenceRowOrder={referenceRowOrder}
      />
      <WbrSection2MetricTable
        title="TACoS"
        metricKey="tacos_pct"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        referenceRowOrder={referenceRowOrder}
      />
    </>
  );
}
