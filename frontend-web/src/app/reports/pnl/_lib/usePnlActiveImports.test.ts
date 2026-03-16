import { describe, expect, it } from "vitest";
import { buildActiveImportSummaries } from "./pnlActiveImportSummary";

describe("buildActiveImportSummaries", () => {
  it("groups active import months by import and filters to visible months", () => {
    const result = buildActiveImportSummaries(
      [
        {
          id: "imp-2",
          profile_id: "profile-1",
          source_filename: "feb.csv",
          import_status: "success",
          row_count: 120,
          error_message: null,
          started_at: null,
          finished_at: "2026-03-16T15:35:41+00:00",
          created_at: "2026-03-16T15:34:59+00:00",
          updated_at: null,
        },
        {
          id: "imp-1",
          profile_id: "profile-1",
          source_filename: "jan.csv",
          import_status: "success",
          row_count: 90,
          error_message: null,
          started_at: null,
          finished_at: "2026-02-16T15:35:41+00:00",
          created_at: "2026-02-16T15:34:59+00:00",
          updated_at: null,
        },
      ],
      [
        {
          id: "im-jan",
          import_id: "imp-1",
          entry_month: "2026-01-01",
          import_status: "success",
          is_active: true,
          raw_row_count: 10,
          ledger_row_count: 10,
          mapped_amount: "100.00",
          unmapped_amount: "0.00",
        },
        {
          id: "im-feb",
          import_id: "imp-2",
          entry_month: "2026-02-01",
          import_status: "success",
          is_active: true,
          raw_row_count: 10,
          ledger_row_count: 10,
          mapped_amount: "100.00",
          unmapped_amount: "0.00",
        },
        {
          id: "im-mar-inactive",
          import_id: "imp-3",
          entry_month: "2026-03-01",
          import_status: "success",
          is_active: false,
          raw_row_count: 10,
          ledger_row_count: 10,
          mapped_amount: "100.00",
          unmapped_amount: "0.00",
        },
      ],
      ["2026-01-01", "2026-02-01"],
    );

    expect(result).toEqual([
      {
        import_id: "imp-2",
        source_filename: "feb.csv",
        import_status: "success",
        created_at: "2026-03-16T15:34:59+00:00",
        finished_at: "2026-03-16T15:35:41+00:00",
        months: ["2026-02-01"],
      },
      {
        import_id: "imp-1",
        source_filename: "jan.csv",
        import_status: "success",
        created_at: "2026-02-16T15:34:59+00:00",
        finished_at: "2026-02-16T15:35:41+00:00",
        months: ["2026-01-01"],
      },
    ]);
  });
});
