import { describe, expect, it } from "vitest";
import { buildPnlCogsCsv, parsePnlCogsCsv } from "./pnlCogsCsv";

describe("pnlCogsCsv", () => {
  it("builds a CSV template from loaded sku rows", () => {
    const csv = buildPnlCogsCsv([
      {
        sku: "SKU-1",
        unit_cost: "12.3400",
        months: { "2025-12-01": 4, "2026-01-01": 8 },
        total_units: 12,
        missing_cost: false,
      },
      {
        sku: "SKU-2",
        unit_cost: null,
        months: { "2026-01-01": 2 },
        total_units: 2,
        missing_cost: true,
      },
    ]);

    expect(csv).toContain("sku,unit_cost,total_units,months_in_range,missing_cost");
    expect(csv).toContain("SKU-1,12.3400,12");
    expect(csv).toContain("SKU-2,,2");
  });

  it("parses a valid cogs csv file", async () => {
    const file = new File(
      [
        "sku,unit_cost\nSKU-1,12.3400\nSKU-2,\n",
      ],
      "pnl-cogs.csv",
      { type: "text/csv" },
    );

    await expect(parsePnlCogsCsv(file)).resolves.toEqual([
      { sku: "SKU-1", unit_cost: "12.3400" },
      { sku: "SKU-2", unit_cost: null },
    ]);
  });

  it("ignores fully empty rows emitted by spreadsheet csv exports", async () => {
    const file = new File(
      [
        "sku,unit_cost,total_units,months_in_range,missing_cost\nSKU-1,12.3400,4,\"Jan 2026: 4\",no\nSKU-2,,2,\"Jan 2026: 2\",yes\n,,,,\n",
      ],
      "pnl-cogs.csv",
      { type: "text/csv" },
    );

    await expect(parsePnlCogsCsv(file)).resolves.toEqual([
      { sku: "SKU-1", unit_cost: "12.3400" },
      { sku: "SKU-2", unit_cost: null },
    ]);
  });

  it("accepts common unit cost header variants", async () => {
    const file = new File(
      [
        "SKU,Unit Cost\nSKU-1,$12.34\n",
      ],
      "pnl-cogs.csv",
      { type: "text/csv" },
    );

    await expect(parsePnlCogsCsv(file)).resolves.toEqual([
      { sku: "SKU-1", unit_cost: "12.34" },
    ]);
  });

  it("rejects duplicate skus", async () => {
    const file = new File(
      [
        "sku,unit_cost\nSKU-1,1.00\nSKU-1,2.00\n",
      ],
      "pnl-cogs.csv",
      { type: "text/csv" },
    );

    await expect(parsePnlCogsCsv(file)).rejects.toThrow("duplicate sku");
  });
});
