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
}: Props) {
  const displayRows = buildDisplayRows(rows, hideEmptyRows);
  const totals = buildTotalValues(rows, weeks, metricKey, hideEmptyRows);

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <p className="text-sm font-semibold text-[#0f172a]">{title}</p>
      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
          <thead className="bg-[#f7faff]">
            <tr className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">
              <th className="px-3 py-2">Row</th>
              {weeks.map((week) => (
                <th key={`${title}-${week.start}`} className="px-3 py-2 text-right">
                  {week.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 bg-white">
            {displayRows.map((row) => (
              <tr key={`${title}-${row.id}`} className="hover:bg-slate-50">
                <td
                  className={`px-3 py-2 text-[#0f172a] ${
                    row.row_kind === "parent" ? "font-semibold" : row.parent_row_id ? "pl-8" : "pl-3"
                  }`}
                >
                  {row.row_label}
                </td>
                {row.weeks.map((values, index) => (
                  <td key={`${row.id}-${index}`} className="px-3 py-2 text-right text-[#0f172a]">
                    {formatMetricValue(metricKey, values)}
                  </td>
                ))}
              </tr>
            ))}
            <tr className="bg-[#f8fafc] font-semibold text-[#0f172a]">
              <td className="px-3 py-2">Total</td>
              {totals.map((value, index) => (
                <td key={`total-${metricKey}-${index}`} className="px-3 py-2 text-right">
                  {value}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
