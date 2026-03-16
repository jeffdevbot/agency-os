import type { PnlImport, PnlImportMonth } from "./pnlApi";

export type PnlActiveImportSummary = {
  import_id: string;
  source_type: string;
  source_filename: string | null;
  import_status: string;
  created_at: string | null;
  finished_at: string | null;
  months: string[];
};

export function buildActiveImportSummaries(
  imports: PnlImport[],
  importMonths: PnlImportMonth[],
  monthsInView: string[],
): PnlActiveImportSummary[] {
  const monthsInRange = new Set(monthsInView);
  const activeMonths = importMonths.filter(
    (month) => month.is_active && month.import_id && monthsInRange.has(month.entry_month),
  );

  if (activeMonths.length === 0) {
    return [];
  }

  const importById = new Map(imports.map((item) => [item.id, item]));
  const summaries = new Map<string, PnlActiveImportSummary>();

  for (const month of activeMonths) {
    const importId = month.import_id;
    if (!importId) {
      continue;
    }

    const matchedImport = importById.get(importId);
    const current = summaries.get(importId);

    if (current) {
      current.months.push(month.entry_month);
      continue;
    }

    summaries.set(importId, {
      import_id: importId,
      source_type: matchedImport?.source_type ?? "amazon_transaction_upload",
      source_filename: matchedImport?.source_filename ?? null,
      import_status: matchedImport?.import_status ?? month.import_status,
      created_at: matchedImport?.created_at ?? null,
      finished_at: matchedImport?.finished_at ?? null,
      months: [month.entry_month],
    });
  }

  return Array.from(summaries.values())
    .map((summary) => ({
      ...summary,
      months: summary.months.slice().sort(),
    }))
    .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));
}
