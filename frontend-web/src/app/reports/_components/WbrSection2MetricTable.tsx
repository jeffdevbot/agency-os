"use client";

import type { WbrSection1Week, WbrSection2Row, WbrSection2RowWeek } from "../wbr/_lib/wbrSection1Api";
import {
  buildSection2DisplayRows,
  buildSection2TotalValues,
  formatSection2MetricValue,
  isSection2BreakdownRow,
  isSection2ExpandableRow,
  type WbrSection2MetricKey,
} from "./wbrSection2RowDisplay";

type MetricKey = WbrSection2MetricKey;

type Props = {
  title: string;
  metricKey: MetricKey;
  weeks: WbrSection1Week[];
  rows: WbrSection2Row[];
  hideEmptyRows?: boolean;
  newestFirst?: boolean;
  referenceRowOrder?: string[];
  onMetricClick?: (metricKey: MetricKey) => void;
  expandedMetric?: MetricKey | null;
  selectedRowIds?: Set<string>;
  onRowToggle?: (rowId: string) => void;
  expandedBreakdownRowId?: string | null;
  onBreakdownToggle?: (rowId: string) => void;
};

export default function WbrSection2MetricTable({
  title,
  metricKey,
  weeks,
  rows,
  hideEmptyRows = false,
  newestFirst = true,
  referenceRowOrder = [],
  onMetricClick,
  expandedMetric = null,
  selectedRowIds = new Set<string>(),
  onRowToggle,
  expandedBreakdownRowId = null,
  onBreakdownToggle,
}: Props) {
  const displayRows = buildSection2DisplayRows(
    rows,
    hideEmptyRows,
    referenceRowOrder,
    expandedBreakdownRowId ? new Set([expandedBreakdownRowId]) : new Set()
  );
  const totals = buildSection2TotalValues(rows, weeks, metricKey, hideEmptyRows);
  const weekIndexes = weeks.map((_, index) => index);
  const displayWeekIndexes = newestFirst ? weekIndexes.reverse() : weekIndexes;

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 md:px-4 md:py-3">
      <button
        type="button"
        onClick={onMetricClick ? () => onMetricClick(metricKey) : undefined}
        className={`inline-flex items-center gap-2 text-sm font-semibold leading-none text-[#0f172a] ${
          onMetricClick ? "cursor-pointer transition hover:text-[#0a6fd6]" : ""
        }`}
      >
        <span>{title}</span>
        {onMetricClick ? <span className="text-[#4c576f]">{expandedMetric === metricKey ? "▾" : "▸"}</span> : null}
      </button>
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
                    row.row_kind === "parent"
                      ? "font-semibold"
                      : row.row_kind === "breakdown"
                        ? "pl-10 text-[#4c576f]"
                        : row.parent_row_id
                          ? "pl-6"
                          : "pl-3"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {isSection2ExpandableRow(row) ? (
                      <button
                        type="button"
                        onClick={() => onBreakdownToggle?.(row.id)}
                        className="inline-flex h-6 w-6 items-center justify-center rounded-full border border-[#d5e2f7] bg-[#f7faff] text-[11px] text-[#4c576f] transition hover:border-[#0a6fd6] hover:text-[#0a6fd6]"
                        aria-label={`${expandedBreakdownRowId === row.id ? "Collapse" : "Expand"} ${row.row_label} ad type breakdown`}
                      >
                        {expandedBreakdownRowId === row.id ? "▾" : "▸"}
                      </button>
                    ) : null}
                    {expandedMetric && !isSection2BreakdownRow(row) ? (
                      <button
                        type="button"
                        onClick={() => onRowToggle?.(row.id)}
                        className={`inline-flex h-6 w-6 items-center justify-center rounded-full border text-[11px] transition ${
                          selectedRowIds.has(row.id)
                            ? "border-[#0a6fd6] bg-[#0a6fd6] text-white shadow-[0_8px_20px_rgba(10,111,214,0.25)]"
                            : "border-[#d5e2f7] bg-[#f7faff] text-[#4c576f] hover:border-[#0a6fd6] hover:text-[#0a6fd6]"
                        }`}
                        aria-label={`Toggle ${row.row_label} on chart`}
                      >
                        ↗
                      </button>
                    ) : null}
                    <span>{row.row_label}</span>
                  </div>
                </td>
                {displayWeekIndexes.map((weekIndex) => (
                  <td key={`${row.id}-${weekIndex}`} className="px-3 py-2 text-right text-[#0f172a]">
                    {formatSection2MetricValue(metricKey, row, row.weeks[weekIndex] as WbrSection2RowWeek)}
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
