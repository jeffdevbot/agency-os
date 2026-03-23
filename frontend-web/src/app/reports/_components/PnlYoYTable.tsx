"use client";

import { Fragment } from "react";

import {
  amountClass,
  formatAmount,
  lineItemRowClass,
  SUMMARY_KEYS,
} from "../pnl/_lib/pnlDisplay";
import type { PnlYoYLineItem } from "../pnl/_lib/pnlApi";

type Props = {
  months: string[];
  currentMonthKeys: string[];
  priorMonthKeys: string[];
  currentYear: number;
  priorYear: number;
  lineItems: PnlYoYLineItem[];
  currencyCode?: string | null;
  showTotals: boolean;
  selectedRowKeys?: Set<string>;
  onRowToggle?: (key: string) => void;
};

function deltaPercent(currentVal: string, priorVal: string): string {
  const current = parseFloat(currentVal);
  const prior = parseFloat(priorVal);
  if (!Number.isFinite(current) || !Number.isFinite(prior) || prior === 0) return "—";
  const pct = ((current - prior) / Math.abs(prior)) * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`;
}

function deltaValue(currentVal: string, priorVal: string): string {
  const current = parseFloat(currentVal);
  const prior = parseFloat(priorVal);
  if (!Number.isFinite(current) || !Number.isFinite(prior)) return "0";
  return String(current - prior);
}

function deltaClass(item: PnlYoYLineItem, currentVal: string, priorVal: string): string {
  const current = parseFloat(currentVal);
  const prior = parseFloat(priorVal);
  if (!Number.isFinite(current) || !Number.isFinite(prior)) return "text-[#94a3b8]";

  const lowerIsBetter = item.category === "expenses" || item.category === "refunds" || item.key === "total_refunds";
  const improved = lowerIsBetter ? current < prior : current > prior;
  return improved ? "text-[#16a34a] font-semibold" : "text-[#dc2626] font-semibold";
}

export default function PnlYoYTable({
  months,
  currentMonthKeys,
  priorMonthKeys,
  currentYear,
  priorYear,
  lineItems,
  currencyCode,
  showTotals,
  selectedRowKeys,
  onRowToggle,
}: Props) {
  const safeCurrencyCode = currencyCode || "USD";

  return (
    <div className="rounded-3xl bg-white/95 p-3 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-3.5">
      <div className="overflow-x-auto">
        <table className="min-w-max border-separate border-spacing-0 text-[12px] leading-tight md:text-[13px]">
          <thead>
            <tr className="border-b border-[#e2e8f0]">
              <th className="sticky left-0 z-20 min-w-[196px] border-b border-[#e2e8f0] bg-[#f7faff] px-2.5 py-2 text-left font-semibold text-[#334155] md:min-w-[208px]">
                Line Item
              </th>
              {months.map((label) => (
                <th
                  key={label}
                  className="whitespace-nowrap border-b border-[#e2e8f0] bg-white px-1.5 py-2 text-right font-semibold text-[#334155] md:px-2"
                >
                  {label}
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
              const currentTotal = currentMonthKeys.reduce(
                (sum, month) => sum + (parseFloat(item.current[month] ?? "0") || 0),
                0,
              );
              const priorTotal = priorMonthKeys.reduce(
                (sum, month) => sum + (parseFloat(item.prior[month] ?? "0") || 0),
                0,
              );

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

                  <tr className={`border-b border-[#f1f5f9] ${lineItemRowClass(item as any)}`}>
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
                        <span className="ml-2 text-[10px] font-normal text-[#94a3b8]">{currentYear}</span>
                      </button>
                    </td>
                    {currentMonthKeys.map((month) => {
                      const value = item.current[month] ?? "0.00";
                      return (
                        <td
                          key={month}
                          className={`whitespace-nowrap border-b border-[#f1f5f9] px-1.5 py-1.5 text-right tabular-nums md:px-2 ${amountClass(value, item as any)}`}
                        >
                          {formatAmount(value, "currency", safeCurrencyCode)}
                        </td>
                      );
                    })}
                    {showTotals ? (
                      <td className={`whitespace-nowrap border-b border-[#f1f5f9] bg-[#f8fafc] px-1.5 py-1.5 text-right font-semibold tabular-nums md:px-2 ${amountClass(String(currentTotal), item as any)}`}>
                        {formatAmount(String(currentTotal), "currency", safeCurrencyCode)}
                      </td>
                    ) : null}
                  </tr>

                  <tr className="border-b border-[#f8fafc]">
                    <td className="sticky left-0 z-10 min-w-[196px] border-b border-[#f8fafc] bg-[#fcfdff] px-2.5 py-1 text-left text-[#64748b] shadow-[8px_0_14px_-10px_rgba(15,23,42,0.12)] md:min-w-[208px]">
                      <span className="pl-4">{priorYear}</span>
                    </td>
                    {priorMonthKeys.map((month) => {
                      const value = item.prior[month] ?? "0.00";
                      return (
                        <td
                          key={month}
                          className={`whitespace-nowrap border-b border-[#f8fafc] bg-[#fcfdff] px-1.5 py-1 text-right tabular-nums md:px-2 ${amountClass(value, item as any)}`}
                        >
                          {formatAmount(value, "currency", safeCurrencyCode)}
                        </td>
                      );
                    })}
                    {showTotals ? (
                      <td className={`whitespace-nowrap border-b border-[#f8fafc] bg-[#fcfdff] px-1.5 py-1 text-right font-semibold tabular-nums md:px-2 ${amountClass(String(priorTotal), item as any)}`}>
                        {formatAmount(String(priorTotal), "currency", safeCurrencyCode)}
                      </td>
                    ) : null}
                  </tr>

                  <tr className="border-b border-[#e2e8f0]">
                    <td className="sticky left-0 z-10 min-w-[196px] border-b border-[#e2e8f0] bg-[#f8fafc] px-2.5 py-1 text-left text-[#64748b] shadow-[8px_0_14px_-10px_rgba(15,23,42,0.12)] md:min-w-[208px]">
                      <span className="pl-4">Delta</span>
                    </td>
                    {currentMonthKeys.map((currentMonth, index) => {
                      const priorMonth = priorMonthKeys[index];
                      const currentValue = item.current[currentMonth] ?? "0.00";
                      const priorValue = priorMonth ? (item.prior[priorMonth] ?? "0.00") : "0.00";
                      return (
                        <td
                          key={`${currentMonth}-delta`}
                          className={`whitespace-nowrap border-b border-[#e2e8f0] bg-[#f8fafc] px-1.5 py-1 text-right tabular-nums md:px-2 ${deltaClass(item, currentValue, priorValue)}`}
                          title={`Value delta: ${formatAmount(deltaValue(currentValue, priorValue), "currency", safeCurrencyCode)}`}
                        >
                          {deltaPercent(currentValue, priorValue)}
                        </td>
                      );
                    })}
                    {showTotals ? (
                      <td className={`whitespace-nowrap border-b border-[#e2e8f0] bg-[#f8fafc] px-1.5 py-1 text-right font-semibold tabular-nums md:px-2 ${deltaClass(item, String(currentTotal), String(priorTotal))}`}>
                        {deltaPercent(String(currentTotal), String(priorTotal))}
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
