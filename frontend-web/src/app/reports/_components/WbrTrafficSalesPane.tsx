"use client";

import type { WbrSection1Row, WbrSection1Week } from "../wbr/_lib/wbrSection1Api";
import WbrTrendChart from "./WbrTrendChart";
import WbrSection1HorizontalTable from "./WbrSection1HorizontalTable";
import WbrSection1MetricTable from "./WbrSection1MetricTable";
import { buildDisplayRows, hasAnyActivity } from "./wbrSection1RowDisplay";
import { useWbrChartState, type WbrChartMetricKey } from "./useWbrChartState";

type Props = {
  weeks: WbrSection1Week[];
  rows: WbrSection1Row[];
  hideEmptyRows: boolean;
  newestFirst: boolean;
  horizontalLayout: boolean;
};

const SERIES_COLORS = ["#0a6fd6", "#f97316", "#14b8a6", "#6366f1", "#f43f5e", "#65a30d"];

const METRIC_LABELS: Record<WbrChartMetricKey, string> = {
  page_views: "Page Views",
  unit_sales: "Unit Sales",
  sales: "Sales",
  conversion_rate: "Conversion Rate",
};

const formatChartValue = (metricKey: WbrChartMetricKey, value: number): string => {
  if (metricKey === "sales") {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  }

  if (metricKey === "conversion_rate") {
    return `${(value * 100).toFixed(1)}%`;
  }

  return new Intl.NumberFormat("en-US").format(value);
};

const getMetricValue = (row: WbrSection1Row, metricKey: WbrChartMetricKey, weekIndex: number): number => {
  const week = row.weeks[weekIndex];
  if (!week) return 0;
  if (metricKey === "sales") return Number(week.sales || 0);
  return Number(week[metricKey] || 0);
};

export default function WbrTrafficSalesPane({
  weeks,
  rows,
  hideEmptyRows,
  newestFirst,
  horizontalLayout,
}: Props) {
  const chartState = useWbrChartState();
  const activityPresent = hasAnyActivity(rows);
  const displayRows = buildDisplayRows(rows, hideEmptyRows);
  const chronologicalWeeks = weeks;
  const topLevelRows = displayRows.filter((row) => !row.parent_row_id);

  const chartSeries =
    chartState.expandedMetric == null
      ? []
      : [
          {
            key: "total",
            label: "Total",
            data: chronologicalWeeks.map((_, weekIndex) =>
              topLevelRows.reduce((sum, row) => sum + getMetricValue(row, chartState.expandedMetric!, weekIndex), 0)
            ),
            color: SERIES_COLORS[0],
          },
          ...displayRows
            .filter((row) => chartState.selectedRowIds.has(row.id))
            .slice(0, SERIES_COLORS.length - 1)
            .map((row, index) => ({
              key: row.id,
              label: row.row_label,
              data: chronologicalWeeks.map((_, weekIndex) => getMetricValue(row, chartState.expandedMetric!, weekIndex)),
              color: SERIES_COLORS[index + 1],
            })),
        ];

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
      <>
        {chartState.expandedMetric ? (
          <WbrTrendChart
            title={METRIC_LABELS[chartState.expandedMetric]}
            weeks={chronologicalWeeks.map((week) => ({ label: week.label }))}
            series={chartSeries}
            formatValue={(value) => formatChartValue(chartState.expandedMetric!, value)}
          />
        ) : null}
        <WbrSection1HorizontalTable
          weeks={weeks}
          rows={rows}
          hideEmptyRows={hideEmptyRows}
          newestFirst={newestFirst}
          onMetricClick={chartState.toggleMetric}
          expandedMetric={chartState.expandedMetric}
          selectedRowIds={chartState.selectedRowIds}
          onRowToggle={chartState.toggleRow}
        />
      </>
    );
  }

  return (
    <>
      {chartState.expandedMetric ? (
        <WbrTrendChart
          title={METRIC_LABELS[chartState.expandedMetric]}
          weeks={chronologicalWeeks.map((week) => ({ label: week.label }))}
          series={chartSeries}
          formatValue={(value) => formatChartValue(chartState.expandedMetric!, value)}
        />
      ) : null}
      <WbrSection1MetricTable
        title="Page Views"
        metricKey="page_views"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        onMetricClick={chartState.toggleMetric}
        expandedMetric={chartState.expandedMetric}
        selectedRowIds={chartState.selectedRowIds}
        onRowToggle={chartState.toggleRow}
      />
      <WbrSection1MetricTable
        title="Unit Sales"
        metricKey="unit_sales"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        onMetricClick={chartState.toggleMetric}
        expandedMetric={chartState.expandedMetric}
        selectedRowIds={chartState.selectedRowIds}
        onRowToggle={chartState.toggleRow}
      />
      <WbrSection1MetricTable
        title="Conversion Rate"
        metricKey="conversion_rate"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        onMetricClick={chartState.toggleMetric}
        expandedMetric={chartState.expandedMetric}
        selectedRowIds={chartState.selectedRowIds}
        onRowToggle={chartState.toggleRow}
      />
      <WbrSection1MetricTable
        title="Sales"
        metricKey="sales"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        onMetricClick={chartState.toggleMetric}
        expandedMetric={chartState.expandedMetric}
        selectedRowIds={chartState.selectedRowIds}
        onRowToggle={chartState.toggleRow}
      />
    </>
  );
}
