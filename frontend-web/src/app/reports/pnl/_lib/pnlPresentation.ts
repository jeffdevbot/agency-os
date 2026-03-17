import type { PnlLineItem, PnlWarning } from "./pnlApi";
import type { PnlPresentedLineItem } from "./pnlDisplay";

type ProfitMode = "contribution" | "net";
export type PnlDisplayMode = "dollars" | "percent";

type PresentedReport = {
  lineItems: PnlPresentedLineItem[];
  warnings: PnlWarning[];
  profitMode: ProfitMode;
};

const ZERO_TOLERANCE = 0.000001;
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

function parseAmount(value: string | undefined): number {
  const parsed = Number.parseFloat(value ?? "0");
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatValue(value: number, decimals: number): string {
  return value.toFixed(decimals);
}

function sumMonths(item: PnlLineItem | PnlPresentedLineItem, months: string[]): number {
  return months.reduce((total, month) => total + parseAmount(item.months[month]), 0);
}

function negateLineItem(item: PnlPresentedLineItem): PnlPresentedLineItem {
  return {
    ...item,
    months: Object.fromEntries(
      Object.entries(item.months).map(([month, value]) => [
        month,
        formatValue(-parseAmount(value), 2),
      ]),
    ),
  };
}

function buildMarginRow(
  key: "contribution_margin" | "net_margin",
  label: string,
  months: string[],
  profitLine: PnlLineItem,
  revenueLine: PnlLineItem,
): PnlPresentedLineItem {
  const monthValues = Object.fromEntries(
    months.map((month) => {
      const revenue = parseAmount(revenueLine.months[month]);
      const profit = parseAmount(profitLine.months[month]);
      const margin = revenue === 0 ? 0 : (profit / revenue) * 100;
      return [month, formatValue(margin, 1)];
    }),
  );
  const totalRevenue = sumMonths(revenueLine, months);
  const totalProfit = sumMonths(profitLine, months);
  const totalMargin = totalRevenue === 0 ? 0 : (totalProfit / totalRevenue) * 100;

  return {
    key,
    label,
    category: "summary",
    is_derived: true,
    months: monthValues,
    display_format: "percent",
    total_value: formatValue(totalMargin, 1),
  };
}

function buildPayoutPercentRow(
  months: string[],
  payoutLine: PnlPresentedLineItem,
  revenueLine: PnlLineItem,
): PnlPresentedLineItem {
  const monthValues = Object.fromEntries(
    months.map((month) => {
      const revenue = parseAmount(revenueLine.months[month]);
      const payout = parseAmount(payoutLine.months[month]);
      const percent = revenue === 0 ? 0 : (payout / revenue) * 100;
      return [month, formatValue(percent, 1)];
    }),
  );
  const totalRevenue = sumMonths(revenueLine, months);
  const totalPayout = sumMonths(payoutLine, months);
  const totalPercent = totalRevenue === 0 ? 0 : (totalPayout / totalRevenue) * 100;

  return {
    key: "payout_percent",
    label: "Payout (%)",
    category: "summary",
    is_derived: true,
    months: monthValues,
    display_format: "percent",
    total_value: formatValue(totalPercent, 1),
  };
}

function withCurrencyTotal(item: PnlPresentedLineItem, months: string[]): PnlPresentedLineItem {
  return {
    ...item,
    total_value: formatValue(sumMonths(item, months), 2),
  };
}

function toPercentOfRevenue(
  item: PnlPresentedLineItem,
  months: string[],
  revenueLine: PnlLineItem,
): PnlPresentedLineItem {
  const monthValues = Object.fromEntries(
    months.map((month) => {
      const revenue = parseAmount(revenueLine.months[month]);
      const amount = parseAmount(item.months[month]);
      const percent = revenue === 0 ? 0 : (amount / revenue) * 100;
      return [month, formatValue(percent, 1)];
    }),
  );
  const totalRevenue = sumMonths(revenueLine, months);
  const totalAmount = sumMonths(item, months);
  const totalPercent = totalRevenue === 0 ? 0 : (totalAmount / totalRevenue) * 100;

  return {
    ...item,
    months: monthValues,
    display_format: "percent",
    total_value: formatValue(totalPercent, 1),
  };
}

function buildViewItems(
  mode: PnlDisplayMode,
  months: string[],
  lineItems: PnlPresentedLineItem[],
  revenueLine: PnlLineItem | undefined,
  grossRevenueLine: PnlLineItem | undefined,
): PnlPresentedLineItem[] {
  if (mode === "dollars" || !revenueLine) {
    return lineItems.map((item) =>
      item.display_format === "percent" && item.total_value
        ? item
        : withCurrencyTotal(item, months),
    );
  }

  return lineItems.map((item) => {
    if (item.display_format === "percent" && item.total_value) {
      return item;
    }
    if (CURRENCY_KEYS_IN_PERCENT_VIEW.has(item.key)) {
      return withCurrencyTotal(item, months);
    }
    const denominatorLine =
      GROSS_REVENUE_PERCENT_KEYS.has(item.key) && grossRevenueLine
        ? grossRevenueLine
        : revenueLine;
    return toPercentOfRevenue(item, months, denominatorLine);
  });
}

export function buildPresentedPnlReport(
  months: string[],
  lineItems: PnlLineItem[],
  warnings: PnlWarning[],
  mode: PnlDisplayMode = "dollars",
): PresentedReport {
  const cogsLine = lineItems.find((item) => item.key === "cogs");
  const revenueLine = lineItems.find((item) => item.key === "total_net_revenue");
  const grossRevenueLine = lineItems.find((item) => item.key === "total_gross_revenue");
  const profitLine = lineItems.find((item) => item.key === "net_earnings");
  const hasAnyCogs = months.some(
    (month) => Math.abs(parseAmount(cogsLine?.months[month])) > ZERO_TOLERANCE,
  );

  const visibleWarnings =
    hasAnyCogs
      ? warnings
      : warnings.filter((warning) => warning.type !== "missing_cogs");

  const renamedItems = lineItems.map<PnlPresentedLineItem>((item) =>
    item.key === "cogs"
      ? negateLineItem(item)
      : !hasAnyCogs && item.key === "net_earnings"
        ? { ...item, label: "Contribution Profit" }
        : item,
  );
  const baseItems = renamedItems.filter((item) => item.key !== "payout_amount");
  const presentedPayoutLine = renamedItems.find((item) => item.key === "payout_amount");

  if (!revenueLine || !profitLine) {
    const itemsWithPayout = presentedPayoutLine
      ? [...baseItems, presentedPayoutLine]
      : baseItems;
    return {
      lineItems: buildViewItems(mode, months, itemsWithPayout, revenueLine, grossRevenueLine),
      warnings: visibleWarnings,
      profitMode: hasAnyCogs ? "net" : "contribution",
    };
  }

  const itemsWithMargin = baseItems.slice();
  itemsWithMargin.push(
    hasAnyCogs
      ? buildMarginRow("net_margin", "Net Margin (%)", months, profitLine, revenueLine)
      : buildMarginRow(
          "contribution_margin",
          "Contribution Margin (%)",
          months,
          profitLine,
          revenueLine,
        ),
  );
  if (presentedPayoutLine) {
    itemsWithMargin.push(presentedPayoutLine);
    itemsWithMargin.push(buildPayoutPercentRow(months, presentedPayoutLine, revenueLine));
  }

  return {
    lineItems: buildViewItems(mode, months, itemsWithMargin, revenueLine, grossRevenueLine),
    warnings: visibleWarnings,
    profitMode: hasAnyCogs ? "net" : "contribution",
  };
}
