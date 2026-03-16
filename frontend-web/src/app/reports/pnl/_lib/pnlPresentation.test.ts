import { describe, expect, it } from "vitest";
import { buildPresentedPnlReport } from "./pnlPresentation";

describe("buildPresentedPnlReport", () => {
  it("switches to contribution framing when no cogs exist in view", () => {
    const result = buildPresentedPnlReport(
      ["2026-01-01", "2026-02-01"],
      [
        {
          key: "total_net_revenue",
          label: "Total Net Revenue",
          category: "summary",
          is_derived: true,
          months: { "2026-01-01": "100.00", "2026-02-01": "200.00" },
        },
        {
          key: "cogs",
          label: "COGS",
          category: "costs",
          is_derived: false,
          months: { "2026-01-01": "0.00", "2026-02-01": "0.00" },
        },
        {
          key: "net_earnings",
          label: "Net Earnings",
          category: "summary",
          is_derived: true,
          months: { "2026-01-01": "25.00", "2026-02-01": "50.00" },
        },
      ],
      [
        {
          type: "missing_cogs",
          message: "COGS missing",
          months: ["2026-01-01", "2026-02-01"],
        },
      ],
    );

    expect(result.warnings).toEqual([]);
    expect(result.profitMode).toBe("contribution");
    expect(result.lineItems.find((item) => item.key === "net_earnings")?.label).toBe(
      "Contribution Profit",
    );
    expect(result.lineItems.find((item) => item.key === "contribution_margin")).toEqual(
      expect.objectContaining({
        label: "Contribution Margin (%)",
        display_format: "percent",
        months: { "2026-01-01": "25.0", "2026-02-01": "25.0" },
        total_value: "25.0",
      }),
    );
    expect(result.lineItems.find((item) => item.key === "total_net_revenue")?.total_value).toBe(
      "300.00",
    );
    expect(result.lineItems.find((item) => item.key === "net_earnings")?.total_value).toBe(
      "75.00",
    );
  });

  it("adds net margin when cogs are present", () => {
    const result = buildPresentedPnlReport(
      ["2026-01-01"],
      [
        {
          key: "total_net_revenue",
          label: "Total Net Revenue",
          category: "summary",
          is_derived: true,
          months: { "2026-01-01": "100.00" },
        },
        {
          key: "cogs",
          label: "COGS",
          category: "costs",
          is_derived: false,
          months: { "2026-01-01": "40.00" },
        },
        {
          key: "net_earnings",
          label: "Net Earnings",
          category: "summary",
          is_derived: true,
          months: { "2026-01-01": "15.00" },
        },
      ],
      [],
    );

    expect(result.profitMode).toBe("net");
    expect(result.lineItems.find((item) => item.key === "net_earnings")?.label).toBe(
      "Net Earnings",
    );
    expect(result.lineItems.find((item) => item.key === "net_margin")).toEqual(
      expect.objectContaining({
        label: "Net Margin (%)",
        display_format: "percent",
        months: { "2026-01-01": "15.0" },
        total_value: "15.0",
      }),
    );
  });

  it("preserves missing cogs warnings when cogs are only partially entered", () => {
    const result = buildPresentedPnlReport(
      ["2026-01-01", "2026-02-01"],
      [
        {
          key: "total_net_revenue",
          label: "Total Net Revenue",
          category: "summary",
          is_derived: true,
          months: { "2026-01-01": "100.00", "2026-02-01": "200.00" },
        },
        {
          key: "cogs",
          label: "COGS",
          category: "costs",
          is_derived: false,
          months: { "2026-01-01": "40.00", "2026-02-01": "0.00" },
        },
        {
          key: "net_earnings",
          label: "Net Earnings",
          category: "summary",
          is_derived: true,
          months: { "2026-01-01": "20.00", "2026-02-01": "50.00" },
        },
      ],
      [
        {
          type: "missing_cogs",
          message: "COGS missing for one month",
          months: ["2026-02-01"],
        },
      ],
    );

    expect(result.profitMode).toBe("net");
    expect(result.warnings).toEqual([
      {
        type: "missing_cogs",
        message: "COGS missing for one month",
        months: ["2026-02-01"],
      },
    ]);
  });

  it("converts eligible line items to percent of revenue while preserving revenue totals", () => {
    const result = buildPresentedPnlReport(
      ["2026-01-01", "2026-02-01"],
      [
        {
          key: "total_net_revenue",
          label: "Total Net Revenue",
          category: "summary",
          is_derived: true,
          months: { "2026-01-01": "100.00", "2026-02-01": "200.00" },
        },
        {
          key: "amazon_fees",
          label: "Amazon Fees",
          category: "costs",
          is_derived: false,
          months: { "2026-01-01": "20.00", "2026-02-01": "50.00" },
        },
        {
          key: "cogs",
          label: "COGS",
          category: "costs",
          is_derived: false,
          months: { "2026-01-01": "40.00", "2026-02-01": "80.00" },
        },
        {
          key: "net_earnings",
          label: "Net Earnings",
          category: "summary",
          is_derived: true,
          months: { "2026-01-01": "15.00", "2026-02-01": "30.00" },
        },
      ],
      [],
      "percent",
    );

    expect(result.lineItems.find((item) => item.key === "total_net_revenue")).toEqual(
      expect.objectContaining({
        months: { "2026-01-01": "100.00", "2026-02-01": "200.00" },
        total_value: "300.00",
      }),
    );
    expect(result.lineItems.find((item) => item.key === "amazon_fees")).toEqual(
      expect.objectContaining({
        display_format: "percent",
        months: { "2026-01-01": "20.0", "2026-02-01": "25.0" },
        total_value: "23.3",
      }),
    );
    expect(result.lineItems.find((item) => item.key === "cogs")).toEqual(
      expect.objectContaining({
        display_format: "percent",
        months: { "2026-01-01": "40.0", "2026-02-01": "40.0" },
        total_value: "40.0",
      }),
    );
    expect(result.lineItems.find((item) => item.key === "net_margin")).toEqual(
      expect.objectContaining({
        display_format: "percent",
        months: { "2026-01-01": "15.0", "2026-02-01": "15.0" },
        total_value: "15.0",
      }),
    );
  });
});
