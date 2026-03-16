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
};

export default function PnlReportTable({ months, lineItems }: Props) {
  return (
    <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#e2e8f0]">
              <th className="sticky left-0 z-10 bg-white py-3 pr-4 text-left font-semibold text-[#334155]">
                Line Item
              </th>
              {months.map((month) => (
                <th
                  key={month}
                  className="whitespace-nowrap px-3 py-3 text-right font-semibold text-[#334155]"
                >
                  {formatMonth(month)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {lineItems.map((item) => (
              <tr key={item.key} className={`border-b border-[#f1f5f9] ${lineItemRowClass(item)}`}>
                <td className="sticky left-0 z-10 whitespace-nowrap py-2.5 pr-4 text-left">
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
                      className={`whitespace-nowrap px-3 py-2.5 text-right tabular-nums ${amountClass(value, item)}`}
                    >
                      {formatAmount(value, item.display_format)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
