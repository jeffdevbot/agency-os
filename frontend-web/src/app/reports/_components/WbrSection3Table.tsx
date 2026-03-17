"use client";

import type { WbrSection1Week, WbrSection3Row } from "../wbr/_lib/wbrSection1Api";

type Props = {
  returnsWeeks: WbrSection1Week[];
  rows: WbrSection3Row[];
  weekCount: number;
  hideEmptyRows?: boolean;
  referenceRowOrder?: string[];
};

const hasActivity = (row: WbrSection3Row): boolean =>
  row.instock > 0 ||
  row.working > 0 ||
  row.reserved_plus_fc_transfer > 0 ||
  row.receiving_plus_intransit > 0 ||
  row.returns_week_1 > 0 ||
  row.returns_week_2 > 0;

const fmt = (value: number): string =>
  new Intl.NumberFormat("en-US").format(value);

const fmtPct = (value: number | null): string => {
  if (value == null) return "";
  return `${(value * 100).toFixed(1)}%`;
};

const fmtWos = (value: number | null): string => {
  if (value == null) return "";
  return String(Math.round(value));
};

export default function WbrSection3Table({
  returnsWeeks,
  rows,
  weekCount,
  hideEmptyRows = false,
  referenceRowOrder = [],
}: Props) {
  const rowOrderMap = new Map(referenceRowOrder.map((id, i) => [id, i]));

  const compareRows = (a: WbrSection3Row, b: WbrSection3Row): number => {
    const ai = rowOrderMap.get(a.id);
    const bi = rowOrderMap.get(b.id);
    if (ai !== undefined || bi !== undefined) {
      if (ai === undefined) return 1;
      if (bi === undefined) return -1;
      if (ai !== bi) return ai - bi;
    }
    const sortDelta = (a.sort_order || 0) - (b.sort_order || 0);
    if (sortDelta !== 0) return sortDelta;
    return a.row_label.localeCompare(b.row_label);
  };

  const filtered = hideEmptyRows ? rows.filter(hasActivity) : rows;

  // Group into parent/children tree
  const childrenByParent = new Map<string, WbrSection3Row[]>();
  const roots: WbrSection3Row[] = [];
  filtered.forEach((row) => {
    if (row.parent_row_id) {
      const arr = childrenByParent.get(row.parent_row_id) ?? [];
      arr.push(row);
      childrenByParent.set(row.parent_row_id, arr);
    } else {
      roots.push(row);
    }
  });
  roots.sort(compareRows);
  childrenByParent.forEach((children) => children.sort(compareRows));

  const ordered: WbrSection3Row[] = [];
  roots.forEach((root) => {
    ordered.push(root);
    (childrenByParent.get(root.id) ?? []).forEach((child) => ordered.push(child));
  });

  // Compute totals from visible top-level rows only — keeps WOS / return %
  // consistent with the displayed inventory and returns numeric totals.
  const topLevel = ordered.filter((r) => !r.parent_row_id);
  const totalInstock = topLevel.reduce((s, r) => s + r.instock, 0);
  const totalWorking = topLevel.reduce((s, r) => s + r.working, 0);
  const totalReservedFc = topLevel.reduce((s, r) => s + r.reserved_plus_fc_transfer, 0);
  const totalReceivingIntransit = topLevel.reduce((s, r) => s + r.receiving_plus_intransit, 0);
  const totalSupply = totalInstock + totalReservedFc + totalReceivingIntransit;
  const totalRetW1 = topLevel.reduce((s, r) => s + r.returns_week_1, 0);
  const totalRetW2 = topLevel.reduce((s, r) => s + r.returns_week_2, 0);

  // WOS: total supply / avg weekly unit sales (visible rows only)
  const totalUnitSales4w = topLevel.reduce((s, r) => s + r._unit_sales_4w, 0);
  const avgWeeklySales = weekCount > 0 ? totalUnitSales4w / weekCount : 0;
  const totalWos = avgWeeklySales === 0 ? null : Math.round(totalSupply / avgWeeklySales);

  // Return %: avg returns / avg unit sales over returns window (visible rows only)
  const numReturnWeeks = returnsWeeks.length || 1;
  const totalUnitSales2w = topLevel.reduce((s, r) => s + r._unit_sales_2w, 0);
  const totalReturns2w = totalRetW1 + totalRetW2;
  const avgReturns = totalReturns2w / numReturnWeeks;
  const avgSales2w = totalUnitSales2w / numReturnWeeks;
  const totalReturnRate = avgSales2w === 0 ? null : avgReturns / avgSales2w;

  // Returns week labels (newest first within section 3: week -1, week -2)
  const retWeekLabel1 = returnsWeeks.length >= 1 ? returnsWeeks[returnsWeeks.length - 1]?.label : "";
  const retWeekLabel2 = returnsWeeks.length >= 2 ? returnsWeeks[returnsWeeks.length - 2]?.label : "";

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-2 py-2.5 md:px-3 md:py-3">
      <div className="overflow-x-auto">
        <table className="min-w-max border-separate border-spacing-0 text-left text-[12px] leading-tight md:text-[13px]">
          <thead>
            <tr className="text-sm font-semibold text-[#0f172a]">
              <th
                rowSpan={2}
                className="min-w-[220px] border-b border-slate-200 bg-[#f7faff] px-3 py-2.5 text-left md:min-w-[240px]"
              >
                Style
              </th>
              <th rowSpan={2} className="border-b border-l border-slate-200 bg-white px-2 py-2 text-right">
                Instock
              </th>
              <th rowSpan={2} className="border-b border-l border-slate-200 bg-white px-2 py-2 text-right">
                Working
              </th>
              <th
                rowSpan={2}
                className="whitespace-nowrap border-b border-l border-slate-200 bg-white px-2 py-2 text-right"
              >
                Reserved / FC Transfer
              </th>
              <th
                rowSpan={2}
                className="whitespace-nowrap border-b border-l border-slate-200 bg-white px-2 py-2 text-right"
              >
                Receiving / Intransit
              </th>
              <th
                rowSpan={2}
                className="whitespace-nowrap border-b border-l border-slate-200 bg-white px-2 py-2 text-right"
              >
                Weeks of Stock
              </th>
              <th colSpan={3} className="border-b border-l border-slate-200 bg-white px-2 py-2 text-center">
                Returns
              </th>
            </tr>
            <tr className="text-[11px] font-semibold uppercase tracking-wide text-[#4c576f] md:text-xs">
              <th className="whitespace-nowrap border-b border-l border-slate-200 bg-[#f7faff] px-2 py-2 text-right">
                {retWeekLabel1}
              </th>
              <th className="whitespace-nowrap border-b border-slate-200 bg-[#f7faff] px-2 py-2 text-right">
                {retWeekLabel2}
              </th>
              <th className="border-b border-slate-200 bg-[#f7faff] px-2 py-2 text-right">%</th>
            </tr>
          </thead>
          <tbody>
            {ordered.map((row) => (
              <tr key={row.id} className="hover:bg-slate-50">
                <td
                  className={`border-b border-slate-200 bg-white px-3 py-2 text-[#0f172a] ${
                    row.row_kind === "parent" ? "font-semibold" : row.parent_row_id ? "pl-6" : "pl-3"
                  }`}
                >
                  {row.row_label}
                </td>
                <td className="border-b border-l border-slate-200 px-2 py-2 text-right text-[#0f172a]">{fmt(row.instock)}</td>
                <td className="border-b border-l border-slate-200 px-2 py-2 text-right text-[#0f172a]">{fmt(row.working)}</td>
                <td className="border-b border-l border-slate-200 px-2 py-2 text-right text-[#0f172a]">
                  {fmt(row.reserved_plus_fc_transfer)}
                </td>
                <td className="border-b border-l border-slate-200 px-2 py-2 text-right text-[#0f172a]">
                  {fmt(row.receiving_plus_intransit)}
                </td>
                <td className="border-b border-l border-slate-200 px-2 py-2 text-right text-[#0f172a]">
                  {fmtWos(row.weeks_of_stock)}
                </td>
                <td className="border-b border-l border-slate-200 px-2 py-2 text-right text-[#0f172a]">
                  {fmt(row.returns_week_1)}
                </td>
                <td className="border-b border-slate-200 px-2 py-2 text-right text-[#0f172a]">{fmt(row.returns_week_2)}</td>
                <td className="border-b border-slate-200 px-2 py-2 text-right text-[#0f172a]">{fmtPct(row.return_rate)}</td>
              </tr>
            ))}
            <tr className="bg-[#f8fafc] font-semibold text-[#0f172a]">
              <td className="border-t border-slate-200 bg-[#f8fafc] px-3 py-2.5">Total</td>
              <td className="border-t border-l border-slate-200 bg-[#f8fafc] px-2 py-2.5 text-right">{fmt(totalInstock)}</td>
              <td className="border-t border-l border-slate-200 bg-[#f8fafc] px-2 py-2.5 text-right">{fmt(totalWorking)}</td>
              <td className="border-t border-l border-slate-200 bg-[#f8fafc] px-2 py-2.5 text-right">{fmt(totalReservedFc)}</td>
              <td className="border-t border-l border-slate-200 bg-[#f8fafc] px-2 py-2.5 text-right">
                {fmt(totalReceivingIntransit)}
              </td>
              <td className="border-t border-l border-slate-200 bg-[#f8fafc] px-2 py-2.5 text-right">{fmtWos(totalWos)}</td>
              <td className="border-t border-l border-slate-200 bg-[#f8fafc] px-2 py-2.5 text-right">{fmt(totalRetW1)}</td>
              <td className="border-t border-slate-200 bg-[#f8fafc] px-2 py-2.5 text-right">{fmt(totalRetW2)}</td>
              <td className="border-t border-slate-200 bg-[#f8fafc] px-2 py-2.5 text-right">{fmtPct(totalReturnRate)}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
