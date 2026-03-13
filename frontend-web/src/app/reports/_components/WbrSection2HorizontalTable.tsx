"use client";

import type { WbrSection1Week, WbrSection2Row, WbrSection2RowWeek } from "../wbr/_lib/wbrSection1Api";
import { buildSection2DisplayRows, buildSection2TotalValues } from "./wbrSection2RowDisplay";

type MetricKey =
  | "impressions"
  | "clicks"
  | "ctr_pct"
  | "ad_spend"
  | "cpc"
  | "ad_orders"
  | "ad_conversion_rate"
  | "ad_sales"
  | "acos_pct"
  | "tacos_pct";

type MetricDefinition = {
  key: MetricKey;
  title: string;
};

type Props = {
  weeks: WbrSection1Week[];
  rows: WbrSection2Row[];
  hideEmptyRows?: boolean;
  newestFirst?: boolean;
  referenceRowOrder?: string[];
};

const METRICS: MetricDefinition[] = [
  { key: "impressions", title: "Impressions" },
  { key: "clicks", title: "Clicks" },
  { key: "ctr_pct", title: "CTR" },
  { key: "ad_spend", title: "Ad Spend" },
  { key: "cpc", title: "CPC" },
  { key: "ad_orders", title: "Ad Orders" },
  { key: "ad_conversion_rate", title: "Ad CVR" },
  { key: "ad_sales", title: "Ad Sales" },
  { key: "acos_pct", title: "ACoS" },
  { key: "tacos_pct", title: "TACoS" },
];

const formatMetricValue = (metricKey: MetricKey, values: WbrSection2RowWeek): string => {
  if (metricKey === "ad_spend" || metricKey === "cpc" || metricKey === "ad_sales") {
    return new Intl.NumberFormat("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(Number(values[metricKey] || 0));
  }

  if (metricKey === "ctr_pct" || metricKey === "ad_conversion_rate" || metricKey === "acos_pct" || metricKey === "tacos_pct") {
    return `${(values[metricKey] * 100).toFixed(1)}%`;
  }

  return new Intl.NumberFormat("en-US").format(values[metricKey]);
};

export default function WbrSection2HorizontalTable({
  weeks,
  rows,
  hideEmptyRows = false,
  newestFirst = true,
  referenceRowOrder = [],
}: Props) {
  const displayRows = buildSection2DisplayRows(rows, hideEmptyRows, referenceRowOrder);
  const weekIndexes = weeks.map((_, index) => index);
  const displayWeekIndexes = newestFirst ? weekIndexes.reverse() : weekIndexes;
  const totalsByMetric = Object.fromEntries(
    METRICS.map((metric) => [metric.key, buildSection2TotalValues(rows, weeks, metric.key, hideEmptyRows)])
  ) as Record<MetricKey, string[]>;

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 md:px-4 md:py-3">
      <div className="overflow-x-auto">
        <table className="min-w-max border-separate border-spacing-0 text-left text-[13px] leading-tight md:text-sm">
          <thead>
            <tr className="text-sm font-semibold text-[#0f172a]">
              <th
                rowSpan={2}
                className="sticky left-0 z-20 min-w-[280px] border-b border-slate-200 bg-[#f7faff] px-4 py-3 text-left"
              >
                Row
              </th>
              {METRICS.map((metric) => (
                <th
                  key={metric.key}
                  colSpan={displayWeekIndexes.length}
                  className="border-b border-l border-slate-200 bg-white px-3 py-2 text-center"
                >
                  {metric.title}
                </th>
              ))}
            </tr>
            <tr className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">
              {METRICS.flatMap((metric) =>
                displayWeekIndexes.map((weekIndex, index) => (
                  <th
                    key={`${metric.key}-${weeks[weekIndex]?.start ?? weekIndex}`}
                    className={`whitespace-nowrap border-b border-slate-200 bg-[#f7faff] px-3 py-2 text-right ${
                      index === 0 ? "border-l border-slate-200" : ""
                    }`}
                  >
                    {weeks[weekIndex]?.label ?? ""}
                  </th>
                ))
              )}
            </tr>
          </thead>
          <tbody>
            {displayRows.map((row) => (
              <tr key={row.id} className="hover:bg-slate-50">
                <td
                  className={`sticky left-0 z-10 border-b border-slate-200 bg-white px-4 py-2 text-[#0f172a] ${
                    row.row_kind === "parent" ? "font-semibold" : row.parent_row_id ? "pl-7" : ""
                  }`}
                >
                  {row.row_label}
                </td>
                {METRICS.flatMap((metric) =>
                  displayWeekIndexes.map((weekIndex, index) => (
                    <td
                      key={`${row.id}-${metric.key}-${weekIndex}`}
                      className={`border-b border-slate-200 px-3 py-2 text-right text-[#0f172a] ${
                        index === 0 ? "border-l border-slate-200" : ""
                      }`}
                    >
                      {formatMetricValue(metric.key, row.weeks[weekIndex])}
                    </td>
                  ))
                )}
              </tr>
            ))}
            <tr className="font-semibold text-[#0f172a]">
              <td className="sticky left-0 z-10 border-t border-slate-200 bg-[#f8fafc] px-4 py-3">
                Total
              </td>
              {METRICS.flatMap((metric) =>
                displayWeekIndexes.map((weekIndex, index) => (
                  <td
                    key={`total-${metric.key}-${weekIndex}`}
                    className={`border-t border-slate-200 bg-[#f8fafc] px-3 py-3 text-right ${
                      index === 0 ? "border-l border-slate-200" : ""
                    }`}
                  >
                    {totalsByMetric[metric.key][weekIndex]}
                  </td>
                ))
              )}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
