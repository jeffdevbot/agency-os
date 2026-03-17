"use client";

import { useState } from "react";

import type { WbrSection1Week, WbrSection2Row } from "../wbr/_lib/wbrSection1Api";
import WbrTrendChart from "./WbrTrendChart";
import WbrSection2HorizontalTable from "./WbrSection2HorizontalTable";
import WbrSection2MetricTable from "./WbrSection2MetricTable";
import {
  buildSection2DisplayRows,
  getSection2TotalValue,
  hasAnySection2Activity,
  isSection2BreakdownRow,
  type WbrSection2MetricKey,
} from "./wbrSection2RowDisplay";
import { useWbrChartState } from "./useWbrChartState";

type Props = {
  weeks: WbrSection1Week[];
  rows: WbrSection2Row[];
  hideEmptyRows: boolean;
  newestFirst: boolean;
  horizontalLayout: boolean;
  referenceRowOrder: string[];
};

const SERIES_COLORS = ["#0a6fd6", "#f97316", "#14b8a6", "#6366f1", "#f43f5e", "#65a30d"];

const METRIC_LABELS: Record<WbrSection2MetricKey, string> = {
  impressions: "Impressions",
  clicks: "Clicks",
  ctr_pct: "CTR",
  ad_spend: "Ad Spend",
  cpc: "CPC",
  ad_orders: "Ad Orders",
  ad_conversion_rate: "Ad Conversion Rate",
  ad_sales: "Ad Sales",
  acos_pct: "ACoS",
  tacos_pct: "TACoS",
};

const formatChartValue = (metricKey: WbrSection2MetricKey, value: number): string => {
  if (metricKey === "ad_spend" || metricKey === "cpc" || metricKey === "ad_sales") {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  }

  if (metricKey === "ctr_pct" || metricKey === "ad_conversion_rate" || metricKey === "acos_pct" || metricKey === "tacos_pct") {
    return `${(value * 100).toFixed(1)}%`;
  }

  return new Intl.NumberFormat("en-US").format(value);
};

const getMetricValue = (row: WbrSection2Row, metricKey: WbrSection2MetricKey, weekIndex: number): number => {
  const week = row.weeks[weekIndex];
  if (!week) return 0;
  return Number(week[metricKey] || 0);
};

export default function WbrAdvertisingPane({
  weeks,
  rows,
  hideEmptyRows,
  newestFirst,
  horizontalLayout,
  referenceRowOrder,
}: Props) {
  const chartState = useWbrChartState<WbrSection2MetricKey>();
  const [expandedBreakdownRowId, setExpandedBreakdownRowId] = useState<string | null>(null);
  const activityPresent = hasAnySection2Activity(rows);
  const displayRows = buildSection2DisplayRows(
    rows,
    hideEmptyRows,
    referenceRowOrder,
    expandedBreakdownRowId ? new Set([expandedBreakdownRowId]) : new Set()
  );
  const expandedMetric = chartState.expandedMetric;

  const chartSeries =
    expandedMetric == null
      ? []
      : [
          ...(chartState.showTotal
            ? [
                {
                  key: "total",
                  label: "Total",
                  data: weeks.map((_, weekIndex) =>
                    getSection2TotalValue(rows, weekIndex, expandedMetric, hideEmptyRows)
                  ),
                  color: SERIES_COLORS[0],
                },
              ]
            : []),
          ...displayRows
            .filter((row) => !isSection2BreakdownRow(row))
            .filter((row) => chartState.selectedRowIds.has(row.id))
            .slice(0, SERIES_COLORS.length - 1)
            .map((row, index) => ({
              key: row.id,
              label: row.row_label,
              data: weeks.map((_, weekIndex) => getMetricValue(row, expandedMetric, weekIndex)),
              color: SERIES_COLORS[index + 1],
            })),
        ];

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
      <>
        {expandedMetric ? (
          <WbrTrendChart
            title={METRIC_LABELS[expandedMetric]}
            weeks={weeks.map((week) => ({ label: week.label }))}
            series={chartSeries}
            formatValue={(value) => formatChartValue(expandedMetric, value)}
            showTotal={chartState.showTotal}
            onToggleTotal={chartState.toggleTotal}
          />
        ) : null}
        <WbrSection2HorizontalTable
          weeks={weeks}
          rows={rows}
          hideEmptyRows={hideEmptyRows}
          newestFirst={newestFirst}
          referenceRowOrder={referenceRowOrder}
          onMetricClick={chartState.toggleMetric}
          expandedMetric={expandedMetric}
          selectedRowIds={chartState.selectedRowIds}
          onRowToggle={chartState.toggleRow}
          expandedBreakdownRowId={expandedBreakdownRowId}
          onBreakdownToggle={(rowId) =>
            setExpandedBreakdownRowId((current) => (current === rowId ? null : rowId))
          }
        />
      </>
    );
  }

  return (
    <>
      {expandedMetric ? (
        <WbrTrendChart
          title={METRIC_LABELS[expandedMetric]}
          weeks={weeks.map((week) => ({ label: week.label }))}
          series={chartSeries}
          formatValue={(value) => formatChartValue(expandedMetric, value)}
          showTotal={chartState.showTotal}
          onToggleTotal={chartState.toggleTotal}
        />
      ) : null}
      <WbrSection2MetricTable
        title="Impressions"
        metricKey="impressions"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        referenceRowOrder={referenceRowOrder}
        onMetricClick={chartState.toggleMetric}
        expandedMetric={expandedMetric}
        selectedRowIds={chartState.selectedRowIds}
        onRowToggle={chartState.toggleRow}
        expandedBreakdownRowId={expandedBreakdownRowId}
        onBreakdownToggle={(rowId) =>
          setExpandedBreakdownRowId((current) => (current === rowId ? null : rowId))
        }
      />
      <WbrSection2MetricTable
        title="Clicks"
        metricKey="clicks"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        referenceRowOrder={referenceRowOrder}
        onMetricClick={chartState.toggleMetric}
        expandedMetric={expandedMetric}
        selectedRowIds={chartState.selectedRowIds}
        onRowToggle={chartState.toggleRow}
        expandedBreakdownRowId={expandedBreakdownRowId}
        onBreakdownToggle={(rowId) =>
          setExpandedBreakdownRowId((current) => (current === rowId ? null : rowId))
        }
      />
      <WbrSection2MetricTable
        title="CTR"
        metricKey="ctr_pct"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        referenceRowOrder={referenceRowOrder}
        onMetricClick={chartState.toggleMetric}
        expandedMetric={expandedMetric}
        selectedRowIds={chartState.selectedRowIds}
        onRowToggle={chartState.toggleRow}
        expandedBreakdownRowId={expandedBreakdownRowId}
        onBreakdownToggle={(rowId) =>
          setExpandedBreakdownRowId((current) => (current === rowId ? null : rowId))
        }
      />
      <WbrSection2MetricTable
        title="Ad Spend"
        metricKey="ad_spend"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        referenceRowOrder={referenceRowOrder}
        onMetricClick={chartState.toggleMetric}
        expandedMetric={expandedMetric}
        selectedRowIds={chartState.selectedRowIds}
        onRowToggle={chartState.toggleRow}
        expandedBreakdownRowId={expandedBreakdownRowId}
        onBreakdownToggle={(rowId) =>
          setExpandedBreakdownRowId((current) => (current === rowId ? null : rowId))
        }
      />
      <WbrSection2MetricTable
        title="CPC"
        metricKey="cpc"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        referenceRowOrder={referenceRowOrder}
        onMetricClick={chartState.toggleMetric}
        expandedMetric={expandedMetric}
        selectedRowIds={chartState.selectedRowIds}
        onRowToggle={chartState.toggleRow}
        expandedBreakdownRowId={expandedBreakdownRowId}
        onBreakdownToggle={(rowId) =>
          setExpandedBreakdownRowId((current) => (current === rowId ? null : rowId))
        }
      />
      <WbrSection2MetricTable
        title="Ad Orders"
        metricKey="ad_orders"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        referenceRowOrder={referenceRowOrder}
        onMetricClick={chartState.toggleMetric}
        expandedMetric={expandedMetric}
        selectedRowIds={chartState.selectedRowIds}
        onRowToggle={chartState.toggleRow}
        expandedBreakdownRowId={expandedBreakdownRowId}
        onBreakdownToggle={(rowId) =>
          setExpandedBreakdownRowId((current) => (current === rowId ? null : rowId))
        }
      />
      <WbrSection2MetricTable
        title="Ad Conversion Rate"
        metricKey="ad_conversion_rate"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        referenceRowOrder={referenceRowOrder}
        onMetricClick={chartState.toggleMetric}
        expandedMetric={expandedMetric}
        selectedRowIds={chartState.selectedRowIds}
        onRowToggle={chartState.toggleRow}
        expandedBreakdownRowId={expandedBreakdownRowId}
        onBreakdownToggle={(rowId) =>
          setExpandedBreakdownRowId((current) => (current === rowId ? null : rowId))
        }
      />
      <WbrSection2MetricTable
        title="Ad Sales"
        metricKey="ad_sales"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        referenceRowOrder={referenceRowOrder}
        onMetricClick={chartState.toggleMetric}
        expandedMetric={expandedMetric}
        selectedRowIds={chartState.selectedRowIds}
        onRowToggle={chartState.toggleRow}
        expandedBreakdownRowId={expandedBreakdownRowId}
        onBreakdownToggle={(rowId) =>
          setExpandedBreakdownRowId((current) => (current === rowId ? null : rowId))
        }
      />
      <WbrSection2MetricTable
        title="ACoS"
        metricKey="acos_pct"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        referenceRowOrder={referenceRowOrder}
        onMetricClick={chartState.toggleMetric}
        expandedMetric={expandedMetric}
        selectedRowIds={chartState.selectedRowIds}
        onRowToggle={chartState.toggleRow}
        expandedBreakdownRowId={expandedBreakdownRowId}
        onBreakdownToggle={(rowId) =>
          setExpandedBreakdownRowId((current) => (current === rowId ? null : rowId))
        }
      />
      <WbrSection2MetricTable
        title="TACoS"
        metricKey="tacos_pct"
        weeks={weeks}
        rows={rows}
        hideEmptyRows={hideEmptyRows}
        newestFirst={newestFirst}
        referenceRowOrder={referenceRowOrder}
        onMetricClick={chartState.toggleMetric}
        expandedMetric={expandedMetric}
        selectedRowIds={chartState.selectedRowIds}
        onRowToggle={chartState.toggleRow}
        expandedBreakdownRowId={expandedBreakdownRowId}
        onBreakdownToggle={(rowId) =>
          setExpandedBreakdownRowId((current) => (current === rowId ? null : rowId))
        }
      />
    </>
  );
}
