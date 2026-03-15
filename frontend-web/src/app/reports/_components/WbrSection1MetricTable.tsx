"use client";

import type { WbrSection1Row, WbrSection1RowWeek, WbrSection1Week } from "../wbr/_lib/wbrSection1Api";
import { buildDisplayRows, buildTotalValues } from "./wbrSection1RowDisplay";

type MetricKey = "page_views" | "unit_sales" | "sales" | "conversion_rate";

type Props = {
  title: string;
  metricKey: MetricKey;
  weeks: WbrSection1Week[];
  rows: WbrSection1Row[];
  hideEmptyRows?: boolean;
  newestFirst?: boolean;
};

const formatMetricValue = (metricKey: MetricKey, values: WbrSection1RowWeek): string => {
  if (metricKey === "sales") {
    return new Intl.NumberFormat("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(Number(values.sales || 0));
  }

  if (metricKey === "conversion_rate") {
    return `${(values.conversion_rate * 100).toFixed(1)}%`;
  }

  return new Intl.NumberFormat("en-US").format(values[metricKey]);
};

export default function WbrSection1MetricTable({
  title,
  metricKey,
  weeks,
  rows,
  hideEmptyRows = false,
  newestFirst = true,
}: Props) {
  const displayRows = buildDisplayRows(rows, hideEmptyRows);
  const totals = buildTotalValues(rows, weeks, metricKey, hideEmptyRows);
  const weekIndexes = weeks.map((_, index) => index);
  const displayWeekIndexes = newestFirst ? weekIndexes.reverse() : weekIndexes;

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 md:px-4 md:py-3">
      <p className="text-sm font-semibold leading-none text-[#0f172a]">{title}</p>
      <div className="mt-3 overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-left text-[13px] leading-tight md:text-sm">
          <thead className="bg-[#f7faff]">
            <tr className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">
              <th className="w-[32%] px-3 py-2">Style</th>
              {displayWeekIndexes.map((weekIndex) => (
                <th
                  key={`${title}-${weeks[weekIndex]?.start ?? weekIndex}`}
                  className="whitespace-nowrap px-3 py-2 text-right"
                >
                  {weeks[weekIndex]?.label ?? ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 bg-white">
            {displayRows.map((row) => (
              <tr key={`${title}-${row.id}`} className="hover:bg-slate-50">
                <td
                  className={`px-3 py-2 text-[#0f172a] ${
                    row.row_kind === "parent" ? "font-semibold" : row.parent_row_id ? "pl-6" : "pl-3"
                  }`}
                >
                  {row.row_label}
                </td>
                {displayWeekIndexes.map((weekIndex) => (
                  <td key={`${row.id}-${weekIndex}`} className="px-3 py-2 text-right text-[#0f172a]">
                    {formatMetricValue(metricKey, row.weeks[weekIndex])}
                  </td>
                ))}
              </tr>
            ))}
            <tr className="bg-[#f8fafc] font-semibold text-[#0f172a]">
              <td className="px-3 py-2">Total</td>
              {displayWeekIndexes.map((weekIndex) => (
                <td key={`total-${metricKey}-${weekIndex}`} className="px-3 py-2 text-right">
                  {totals[weekIndex]}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
