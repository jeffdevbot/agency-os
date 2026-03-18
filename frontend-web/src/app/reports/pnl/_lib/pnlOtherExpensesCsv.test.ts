import { describe, expect, it } from "vitest";
import {
  buildPnlOtherExpensesCsv,
  parsePnlOtherExpensesCsv,
} from "./pnlOtherExpensesCsv";

const EXPENSE_TYPES = [
  { key: "fbm_fulfillment_fees", label: "FBM Fulfillment Fees", enabled: true },
  { key: "agency_fees", label: "Agency Fees", enabled: false },
  { key: "freight", label: "Freight", enabled: false },
];

describe("pnlOtherExpensesCsv", () => {
  it("builds a CSV template from loaded month rows", () => {
    const csv = buildPnlOtherExpensesCsv(
      [
        {
          entry_month: "2026-01-01",
          values: {
            fbm_fulfillment_fees: "12.00",
            agency_fees: null,
            freight: null,
          },
        },
        {
          entry_month: "2026-02-01",
          values: {
            fbm_fulfillment_fees: "",
            agency_fees: "250.00",
            freight: "75.00",
          },
        },
      ],
      EXPENSE_TYPES,
    );

    expect(csv).toContain("entry_month,fbm_fulfillment_fees,agency_fees,freight");
    expect(csv).toContain("2026-01-01,12.00,,");
    expect(csv).toContain("2026-02-01,,250.00,75.00");
  });

  it("parses a valid other expenses csv file", async () => {
    const file = new File(
      [
        "entry_month,fbm_fulfillment_fees,agency_fees,freight\n2026-01-01,12.00,,\n2026-02-01,,250.00,75.00\n",
      ],
      "other-expenses.csv",
      { type: "text/csv" },
    );

    await expect(parsePnlOtherExpensesCsv(file, EXPENSE_TYPES)).resolves.toEqual([
      {
        entry_month: "2026-01-01",
        values: {
          fbm_fulfillment_fees: "12.00",
          agency_fees: null,
          freight: null,
        },
      },
      {
        entry_month: "2026-02-01",
        values: {
          fbm_fulfillment_fees: null,
          agency_fees: "250.00",
          freight: "75.00",
        },
      },
    ]);
  });

  it("ignores fully empty rows emitted by spreadsheet csv exports", async () => {
    const file = new File(
      [
        "entry_month,fbm_fulfillment_fees,agency_fees,freight\n2026-01-01,12.00,,\n2026-02-01,,250.00,75.00\n,,,\n",
      ],
      "other-expenses.csv",
      { type: "text/csv" },
    );

    await expect(parsePnlOtherExpensesCsv(file, EXPENSE_TYPES)).resolves.toEqual([
      {
        entry_month: "2026-01-01",
        values: {
          fbm_fulfillment_fees: "12.00",
          agency_fees: null,
          freight: null,
        },
      },
      {
        entry_month: "2026-02-01",
        values: {
          fbm_fulfillment_fees: null,
          agency_fees: "250.00",
          freight: "75.00",
        },
      },
    ]);
  });

  it("rejects duplicate months", async () => {
    const file = new File(
      [
        "entry_month,fbm_fulfillment_fees,agency_fees,freight\n2026-01-01,12.00,,\n2026-01-01,5.00,,\n",
      ],
      "other-expenses.csv",
      { type: "text/csv" },
    );

    await expect(parsePnlOtherExpensesCsv(file, EXPENSE_TYPES)).rejects.toThrow("duplicate month");
  });
});
