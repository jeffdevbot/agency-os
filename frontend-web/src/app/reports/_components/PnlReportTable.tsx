"use client";

import { Fragment } from "react";

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
  selectedRowKeys?: Set<string>;
  onRowToggle?: (key: string) => void;
};

export default function PnlReportTable({ months, lineItems, showTotals, selectedRowKeys, onRowToggle }: Props) {
  return (
    <div className="rounded-3xl bg-white/95 p-3 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-3.5">
      <div className="overflow-x-auto">
        <table className="min-w-max border-separate border-spacing-0 text-[12px] leading-tight md:text-[13px]">
          <thead>
            <tr className="border-b border-[#e2e8f0]">
              <th className="sticky left-0 z-20 min-w-[196px] border-b border-[#e2e8f0] bg-[#f7faff] px-2.5 py-2 text-left font-semibold text-[#334155] md:min-w-[208px]">
                Line Item
              </th>
              {months.map((month) => (
                <th
                  key={month}
                  className="whitespace-nowrap border-b border-[#e2e8f0] bg-white px-1.5 py-2 text-right font-semibold text-[#334155] md:px-2"
                >
                  {formatMonth(month)}
                </th>
              ))}
              {showTotals ? (
                <th className="whitespace-nowrap border-b border-[#e2e8f0] bg-[#f7faff] px-1.5 py-2 text-right font-semibold text-[#334155] md:px-2">
                  Total
                </th>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {lineItems.map((item) => {
              const isSelected = selectedRowKeys?.has(item.key) ?? false;
              const stickyCellBase =
                item.key === "net_earnings"
                  ? "bg-[#0f172a] text-white"
                  : SUMMARY_KEYS.has(item.key)
                    ? "bg-[#f1f5f9]"
                    : "bg-white";
              const stickyCellClass = isSelected && item.key !== "net_earnings"
                ? "bg-[#eff6ff]"
                : stickyCellBase;
              const totalCellClass =
                item.key === "net_earnings"
                  ? "bg-[#0f172a]"
                  : SUMMARY_KEYS.has(item.key)
                    ? "bg-[#f1f5f9]"
                    : "bg-[#f8fafc]";

              return (
                <Fragment key={item.key}>
                  {item.key === "payout_amount" ? (
                    <tr aria-hidden="true">
                      <td
                        colSpan={1 + months.length + (showTotals ? 1 : 0)}
                        className="h-3 border-0 bg-transparent p-0"
                      />
                    </tr>
                  ) : null}
                  <tr className={`border-b border-[#f1f5f9] ${lineItemRowClass(item)}`}>
                    <td
                      className={`sticky left-0 z-10 min-w-[196px] border-b border-[#f1f5f9] px-2.5 py-1.5 text-left shadow-[8px_0_14px_-10px_rgba(15,23,42,0.24)] md:min-w-[208px] ${stickyCellClass}`}
                    >
                      <button
                        type="button"
                        onClick={() => onRowToggle?.(item.key)}
                        className={`w-full text-left ${
                          onRowToggle ? "cursor-pointer" : "cursor-default"
                        } ${
                          isSelected && item.key !== "net_earnings"
                            ? "text-[#0a6fd6] font-semibold"
                            : item.key === "net_earnings"
                              ? ""
                              : SUMMARY_KEYS.has(item.key)
                                ? "text-[#0f172a]"
                                : "text-[#475569]"
                        }`}
                      >
                        {item.label}
                      </button>
                    </td>
                    {months.map((month) => {
                      const value = item.months[month] ?? "0.00";
                      return (
                        <td
                          key={month}
                          className={`whitespace-nowrap border-b border-[#f1f5f9] px-1.5 py-1.5 text-right tabular-nums md:px-2 ${amountClass(value, item)}`}
                        >
                          {formatAmount(value, item.display_format)}
                        </td>
                      );
                    })}
                    {showTotals ? (
                      <td
                        className={`whitespace-nowrap border-b border-[#f1f5f9] px-1.5 py-1.5 text-right font-semibold tabular-nums md:px-2 ${totalCellClass} ${amountClass(item.total_value ?? "0.00", item)}`}
                      >
                        {formatAmount(item.total_value ?? "0.00", item.display_format)}
                      </td>
                    ) : null}
                  </tr>
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
