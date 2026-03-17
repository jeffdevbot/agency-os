import { describe, expect, it } from "vitest";

import { amountClass, formatAmount } from "./pnlDisplay";

describe("formatAmount", () => {
  it("formats negative currency values with parentheses", () => {
    expect(formatAmount("-91.13", "currency")).toBe("($91.13)");
  });

  it("formats negative percentages with parentheses", () => {
    expect(formatAmount("-12.3", "percent")).toBe("(12.3%)");
  });
});

describe("amountClass", () => {
  it("uses neutral styling for non-zero P&L cells", () => {
    expect(amountClass("-91.13", { key: "refunds", label: "", category: "", is_derived: false, months: {} })).toBe(
      "text-[#0f172a]",
    );
  });
});
