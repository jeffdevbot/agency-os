import type { PnlImportMonth, PnlLineItem } from "./pnlApi";

export type PnlValueFormat = "currency" | "percent";

export type PnlPresentedLineItem = PnlLineItem & {
  display_format?: PnlValueFormat;
};

export const FILTER_OPTIONS = [
  { value: "ytd", label: "Year to Date" },
  { value: "last_3", label: "Last 3 Months" },
  { value: "last_6", label: "Last 6 Months" },
  { value: "last_12", label: "Last 12 Months" },
] as const;

export const SUMMARY_KEYS = new Set([
  "total_gross_revenue",
  "total_refunds",
  "total_net_revenue",
  "gross_profit",
  "total_expenses",
  "net_earnings",
  "cogs",
  "contribution_margin",
  "net_margin",
]);

export function formatMonth(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}

export function formatAmount(value: string, format: PnlValueFormat = "currency"): string {
  const n = parseFloat(value);
  if (Number.isNaN(n)) return value;
  if (format === "percent") {
    return `${n.toLocaleString("en-US", {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    })}%`;
  }
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
}

export function formatMonthList(months: PnlImportMonth[]): string {
  return months.map((month) => formatMonth(month.entry_month)).join(", ");
}

export function formatTimestamp(value: string | null): string {
  if (!value) return "Unknown";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function lineItemRowClass(item: PnlPresentedLineItem): string {
  if (item.key === "net_earnings") return "bg-[#0f172a] text-white font-semibold";
  if (SUMMARY_KEYS.has(item.key)) return "bg-[#f1f5f9] font-semibold";
  return "";
}

export function amountClass(value: string, item: PnlPresentedLineItem): string {
  const n = parseFloat(value);
  if (Number.isNaN(n) || n === 0) return "text-[#94a3b8]";
  if (item.key === "net_earnings") return n < 0 ? "text-[#fca5a5]" : "text-white";
  return n < 0 ? "text-[#ef4444]" : "text-[#0f172a]";
}

export function currentMonthISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

export function monthsAgoISO(monthsBack: number): string {
  const d = new Date();
  d.setMonth(d.getMonth() - monthsBack);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

export function formatMonthRangeLabel(startMonth: string, endMonth: string): string {
  return `${formatMonth(startMonth)} - ${formatMonth(endMonth)}`;
}
