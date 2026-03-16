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

  return (
    <div
      className={`rounded-xl border ${colors.border} ${colors.bg} px-4 py-3 text-sm ${colors.text}`}
    >
      <span className="font-medium">{warning.message}</span>
      <span className="ml-2 text-xs opacity-75">
        ({warning.months.map(formatMonth).join(", ")})
      </span>
    </div>
  );
}
