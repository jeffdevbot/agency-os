import { downloadCsv } from "@/lib/scribe/csvHelpers";
import type { PnlOtherExpenseMonth, PnlOtherExpenseType } from "./pnlApi";

export type PnlOtherExpensesCsvMonth = {
  entry_month: string;
  values: Record<string, string | null>;
};

function escapeCsvField(value: string | null | undefined): string {
  if (!value) {
    return "";
  }
  const normalized = String(value).replace(/\r?\n/g, " ").trim();
  if (/[",\n]/.test(normalized)) {
    return `"${normalized.replace(/"/g, '""')}"`;
  }
  return normalized;
}

function parseCsvLine(line: string, delimiter: string): string[] {
  const values: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];

    if (char === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (char === delimiter && !inQuotes) {
      values.push(current.trim());
      current = "";
      continue;
    }

    current += char;
  }

  values.push(current.trim());
  return values;
}

function detectDelimiter(headerLine: string): string {
  if (headerLine.includes("\t")) {
    return "\t";
  }
  if (headerLine.includes(";")) {
    return ";";
  }
  return ",";
}

function normalizeHeader(value: string): string {
  return value.trim().replace(/^\uFEFF/, "").toLowerCase();
}

function normalizeAmount(value: string): string | null {
  const cleaned = value.replace(/[^0-9.\-]/g, "").trim();
  return cleaned || null;
}

export function buildPnlOtherExpensesCsv(
  months: PnlOtherExpenseMonth[],
  expenseTypes: PnlOtherExpenseType[],
): string {
  const headers = ["entry_month", ...expenseTypes.map((expenseType) => expenseType.key)];
  const lines = months.map((month) =>
    [
      escapeCsvField(month.entry_month),
      ...expenseTypes.map((expenseType) => escapeCsvField(month.values[expenseType.key] ?? "")),
    ].join(","),
  );

  return `\uFEFF${[headers.join(","), ...lines].join("\n")}`;
}

export async function parsePnlOtherExpensesCsv(
  file: File,
  expenseTypes: PnlOtherExpenseType[],
): Promise<PnlOtherExpensesCsvMonth[]> {
  if (!file.name.toLowerCase().endsWith(".csv")) {
    throw new Error("Other expenses import supports .csv files only.");
  }

  const text = await file.text();
  const lines = text
    .replace(/\r\n/g, "\n")
    .split("\n")
    .filter((line) => line.trim().length > 0);

  if (lines.length < 2) {
    throw new Error("Other expenses CSV must include a header row and at least one data row.");
  }

  const delimiter = detectDelimiter(lines[0]);
  const headers = parseCsvLine(lines[0], delimiter);
  const headerIndexByKey = new Map(
    headers.map((header, index) => [normalizeHeader(header), index]),
  );
  const entryMonthIndex = headerIndexByKey.get("entry_month");
  if (entryMonthIndex == null || entryMonthIndex < 0) {
    throw new Error("Other expenses CSV must include an entry_month column.");
  }

  for (const expenseType of expenseTypes) {
    if (!headerIndexByKey.has(expenseType.key.toLowerCase())) {
      throw new Error(`Other expenses CSV must include a ${expenseType.key} column.`);
    }
  }

  const rows: PnlOtherExpensesCsvMonth[] = [];
  const seenMonths = new Set<string>();

  for (let i = 1; i < lines.length; i += 1) {
    const values = parseCsvLine(lines[i], delimiter);
    const entryMonth = (values[entryMonthIndex] || "").trim();
    if (!/^\d{4}-\d{2}-01$/.test(entryMonth)) {
      throw new Error(`Other expenses CSV row ${i + 1} has an invalid entry_month.`);
    }
    if (seenMonths.has(entryMonth)) {
      throw new Error(`Other expenses CSV contains duplicate month ${entryMonth}.`);
    }
    seenMonths.add(entryMonth);

    const monthValues: Record<string, string | null> = {};
    for (const expenseType of expenseTypes) {
      const index = headerIndexByKey.get(expenseType.key.toLowerCase());
      const rawValue = index == null ? "" : values[index] || "";
      const normalized = normalizeAmount(rawValue);
      if (normalized !== null && Number.isNaN(Number(normalized))) {
        throw new Error(
          `Other expenses CSV row ${i + 1} has an invalid amount for ${expenseType.key}.`,
        );
      }
      monthValues[expenseType.key] = normalized;
    }

    rows.push({
      entry_month: entryMonth,
      values: monthValues,
    });
  }

  return rows;
}

export function downloadPnlOtherExpensesCsv(
  filename: string,
  months: PnlOtherExpenseMonth[],
  expenseTypes: PnlOtherExpenseType[],
): void {
  downloadCsv(filename, buildPnlOtherExpensesCsv(months, expenseTypes));
}
