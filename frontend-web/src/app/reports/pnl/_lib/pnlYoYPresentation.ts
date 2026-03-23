import type { PnlValueFormat } from "./pnlDisplay";
import type { PnlYoYLineItem } from "./pnlApi";
import type { PnlDisplayMode } from "./pnlPresentation";

const CURRENCY_KEYS_IN_PERCENT_VIEW = new Set([
  "product_sales",
  "shipping_credits",
  "gift_wrap_credits",
  "promotional_rebate_refunds",
  "fba_liquidation_proceeds",
  "total_gross_revenue",
  "total_net_revenue",
  "payout_amount",
]);

const GROSS_REVENUE_PERCENT_KEYS = new Set([
  "refunds",
  "fba_inventory_credit",
  "shipping_credit_refunds",
  "gift_wrap_credit_refunds",
  "promotional_rebates",
  "a_to_z_guarantee_claims",
  "chargebacks",
  "total_refunds",
]);

export type PnlYoYSide = "current" | "prior";

export function parsePnlAmount(value: string | undefined): number {
  const parsed = Number.parseFloat(value ?? "0");
  return Number.isFinite(parsed) ? parsed : 0;
}

export function getPnlYoYDisplayFormat(
  item: Pick<PnlYoYLineItem, "key">,
  mode: PnlDisplayMode,
): PnlValueFormat {
  if (mode === "percent" && !CURRENCY_KEYS_IN_PERCENT_VIEW.has(item.key)) {
    return "percent";
  }
  return "currency";
}

function denominatorKeyForItem(item: Pick<PnlYoYLineItem, "key">): string {
  if (GROSS_REVENUE_PERCENT_KEYS.has(item.key)) {
    return "total_gross_revenue";
  }
  return "total_net_revenue";
}

export function getPnlYoYMonthDisplayValue(
  item: PnlYoYLineItem,
  monthKey: string,
  side: PnlYoYSide,
  mode: PnlDisplayMode,
  itemIndex: Record<string, PnlYoYLineItem>,
): number {
  const rawValue = parsePnlAmount((side === "current" ? item.current : item.prior)[monthKey]);
  if (getPnlYoYDisplayFormat(item, mode) === "currency") {
    return rawValue;
  }
  const denominatorRow = itemIndex[denominatorKeyForItem(item)];
  const denominatorValue = denominatorRow
    ? parsePnlAmount((side === "current" ? denominatorRow.current : denominatorRow.prior)[monthKey])
    : 0;
  return denominatorValue === 0 ? 0 : (rawValue / denominatorValue) * 100;
}

export function getPnlYoYTotalDisplayValue(
  item: PnlYoYLineItem,
  monthKeys: string[],
  side: PnlYoYSide,
  mode: PnlDisplayMode,
  itemIndex: Record<string, PnlYoYLineItem>,
): number {
  const rawTotal = monthKeys.reduce((sum, monthKey) => (
    sum + parsePnlAmount((side === "current" ? item.current : item.prior)[monthKey])
  ), 0);
  if (getPnlYoYDisplayFormat(item, mode) === "currency") {
    return rawTotal;
  }
  const denominatorRow = itemIndex[denominatorKeyForItem(item)];
  const denominatorTotal = monthKeys.reduce((sum, monthKey) => (
    sum + parsePnlAmount((side === "current" ? denominatorRow?.current : denominatorRow?.prior)?.[monthKey])
  ), 0);
  return denominatorTotal === 0 ? 0 : (rawTotal / denominatorTotal) * 100;
}
