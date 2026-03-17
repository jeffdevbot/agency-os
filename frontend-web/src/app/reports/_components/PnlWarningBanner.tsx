"use client";

import type { PnlWarning } from "../pnl/_lib/pnlApi";
import { formatMonth } from "../pnl/_lib/pnlDisplay";

type Props = {
  warning: PnlWarning;
};

export default function PnlWarningBanner({ warning }: Props) {
  const colorMap: Record<string, { border: string; bg: string; text: string }> = {
    missing_cogs: { border: "border-[#fbbf24]/40", bg: "bg-[#fef3c7]", text: "text-[#92400e]" },
    unmapped_rows: { border: "border-[#fbbf24]/40", bg: "bg-[#fef3c7]", text: "text-[#92400e]" },
    missing_data: { border: "border-[#94a3b8]/40", bg: "bg-[#f1f5f9]", text: "text-[#475569]" },
  };
  const colors = colorMap[warning.type] ?? colorMap.missing_data;
  const skuPreview =
    warning.skus && warning.skus.length > 0
      ? warning.skus.length > 8
        ? `${warning.skus.slice(0, 8).join(", ")} +${warning.skus.length - 8} more`
        : warning.skus.join(", ")
      : null;

  return (
    <div
      className={`rounded-xl border ${colors.border} ${colors.bg} px-4 py-3 text-sm ${colors.text}`}
    >
      <span className="font-medium">{warning.message}</span>
      {warning.months.length > 0 ? (
        <span className="ml-2 text-xs opacity-75">
          ({warning.months.map(formatMonth).join(", ")})
        </span>
      ) : null}
      {skuPreview ? (
        <div className="mt-2 text-xs opacity-80">
          SKUs: {skuPreview}
        </div>
      ) : null}
    </div>
  );
}
