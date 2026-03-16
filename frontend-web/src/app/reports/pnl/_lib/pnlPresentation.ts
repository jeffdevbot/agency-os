import type { PnlLineItem, PnlWarning } from "./pnlApi";
import type { PnlPresentedLineItem } from "./pnlDisplay";

type ProfitMode = "contribution" | "net";

type PresentedReport = {
  lineItems: PnlPresentedLineItem[];
  warnings: PnlWarning[];
  profitMode: ProfitMode;
};

const ZERO_TOLERANCE = 0.000001;

function parseAmount(value: string | undefined): number {
  const parsed = Number.parseFloat(value ?? "0");
  return Number.isFinite(parsed) ? parsed : 0;
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
      return [month, margin.toFixed(1)];
    }),
  );

  return {
    key,
    label,
    category: "summary",
    is_derived: true,
    months: monthValues,
    display_format: "percent",
  };
}

export function buildPresentedPnlReport(
  months: string[],
  lineItems: PnlLineItem[],
  warnings: PnlWarning[],
): PresentedReport {
  const visibleWarnings = warnings.filter((warning) => warning.type !== "missing_cogs");
  const cogsLine = lineItems.find((item) => item.key === "cogs");
  const revenueLine = lineItems.find((item) => item.key === "total_net_revenue");
  const profitLine = lineItems.find((item) => item.key === "net_earnings");
  const hasAnyCogs = months.some(
    (month) => Math.abs(parseAmount(cogsLine?.months[month])) > ZERO_TOLERANCE,
  );

  const presentedItems = lineItems.map<PnlPresentedLineItem>((item) =>
    !hasAnyCogs && item.key === "net_earnings"
      ? { ...item, label: "Contribution Profit" }
      : item,
  );

  if (!revenueLine || !profitLine) {
    return {
      lineItems: presentedItems,
      warnings: visibleWarnings,
      profitMode: hasAnyCogs ? "net" : "contribution",
    };
  }

  presentedItems.push(
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

  return {
    lineItems: presentedItems,
    warnings: visibleWarnings,
    profitMode: hasAnyCogs ? "net" : "contribution",
  };
}
