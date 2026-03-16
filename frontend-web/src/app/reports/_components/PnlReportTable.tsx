"use client";

import {
  amountClass,
  formatAmount,
  formatMonth,
  lineItemRowClass,
  type PnlPresentedLineItem,
  SUMMARY_KEYS,
} from "../pnl/_lib/pnlDisplay";

type Props = {
  months: string[];
  lineItems: PnlPresentedLineItem[];
  showTotals: boolean;
};

export default function PnlReportTable({ months, lineItems, showTotals }: Props) {
  return (
    <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
      <div className="overflow-x-auto">
        <table className="min-w-max border-separate border-spacing-0 text-sm">
          <thead>
            <tr className="border-b border-[#e2e8f0]">
              <th className="sticky left-0 z-20 min-w-[280px] border-b border-[#e2e8f0] bg-[#f7faff] px-4 py-3 text-left font-semibold text-[#334155]">
                Line Item
              </th>
              {months.map((month) => (
                <th
                  key={month}
                  className="whitespace-nowrap border-b border-[#e2e8f0] bg-white px-3 py-3 text-right font-semibold text-[#334155]"
                >
                  {formatMonth(month)}
                </th>
              ))}
              {showTotals ? (
                <th className="whitespace-nowrap border-b border-[#e2e8f0] bg-[#f7faff] px-3 py-3 text-right font-semibold text-[#334155]">
                  Total
                </th>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {lineItems.map((item) => {
              const stickyCellClass =
                item.key === "net_earnings"
                  ? "bg-[#0f172a] text-white"
                  : SUMMARY_KEYS.has(item.key)
                    ? "bg-[#f1f5f9]"
                    : "bg-white";

              return (
                <tr
                  key={item.key}
                  className={`border-b border-[#f1f5f9] ${lineItemRowClass(item)}`}
                >
                  <td
                    className={`sticky left-0 z-10 min-w-[280px] border-b border-[#f1f5f9] px-4 py-2.5 text-left shadow-[8px_0_14px_-10px_rgba(15,23,42,0.24)] ${stickyCellClass}`}
                  >
                  <span
                    className={
                      item.key === "net_earnings"
                        ? ""
                        : SUMMARY_KEYS.has(item.key)
                          ? "text-[#0f172a]"
                          : "text-[#475569]"
                    }
                  >
                    {item.label}
                  </span>
                  </td>
                  {months.map((month) => {
                    const value = item.months[month] ?? "0.00";
                    return (
                      <td
                        key={month}
                        className={`whitespace-nowrap border-b border-[#f1f5f9] px-3 py-2.5 text-right tabular-nums ${amountClass(value, item)}`}
                      >
                        {formatAmount(value, item.display_format)}
                      </td>
                    );
                  })}
                  {showTotals ? (
                    <td
                      className={`whitespace-nowrap border-b border-[#f1f5f9] bg-[#f8fafc] px-3 py-2.5 text-right font-semibold tabular-nums ${amountClass(item.total_value ?? "0.00", item)}`}
                    >
                      {formatAmount(item.total_value ?? "0.00", item.display_format)}
                    </td>
                  ) : null}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
