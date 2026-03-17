import { describe, expect, it } from "vitest";

import { amountClass, formatAmount } from "./pnlDisplay";

describe("formatAmount", () => {
  it("formats negative currency values as whole dollars with parentheses", () => {
    expect(formatAmount("-91.13", "currency")).toBe("($91)");
  });

  it("formats negative percentages as whole numbers with parentheses", () => {
    expect(formatAmount("-12.3", "percent")).toBe("(12%)");
  });
});

describe("amountClass", () => {
  it("uses neutral styling for non-zero P&L cells", () => {
    expect(amountClass("-91.13", { key: "refunds", label: "", category: "", is_derived: false, months: {} })).toBe(
      "text-[#0f172a]",
    );
  });
});
