import { downloadCsv } from "@/lib/scribe/csvHelpers";
import type { PnlSkuCogs } from "./pnlApi";
import { formatMonth } from "./pnlDisplay";

export type PnlCogsCsvEntry = {
  sku: string;
  unit_cost: string | null;
};

const SKU_HEADER_ALIASES = ["sku", "sku_code"];
const UNIT_COST_HEADER_ALIASES = ["unit_cost", "unit cost", "cost", "cogs", "unit cogs"];

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

function resolveHeaderIndex(headers: string[], aliases: string[]): number {
  const normalizedAliases = new Set(aliases.map((alias) => alias.toLowerCase()));
  return headers.findIndex((header) => normalizedAliases.has(normalizeHeader(header)));
}

function normalizeUnitCost(value: string): string | null {
  const cleaned = value.replace(/[^0-9.\-]/g, "").trim();
  return cleaned || null;
}

export function buildPnlCogsCsv(rows: PnlSkuCogs[]): string {
  const header = ["sku", "unit_cost", "total_units", "months_in_range", "missing_cost"];
  const lines = rows.map((row) => {
    const monthsInRange = Object.entries(row.months)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([month, units]) => `${formatMonth(month)}: ${units}`)
      .join(" | ");

    return [
      escapeCsvField(row.sku),
      escapeCsvField(row.unit_cost ?? ""),
      escapeCsvField(String(row.total_units)),
      escapeCsvField(monthsInRange),
      escapeCsvField(row.missing_cost ? "yes" : "no"),
    ].join(",");
  });

  return `\uFEFF${[header.join(","), ...lines].join("\n")}`;
}

export async function parsePnlCogsCsv(file: File): Promise<PnlCogsCsvEntry[]> {
  if (!file.name.toLowerCase().endsWith(".csv")) {
    throw new Error("COGS import supports .csv files only.");
  }

  const text = await file.text();
  const lines = text
    .replace(/\r\n/g, "\n")
    .split("\n")
    .filter((line) => line.trim().length > 0);

  if (lines.length < 2) {
    throw new Error("COGS CSV must include a header row and at least one data row.");
  }

  const delimiter = detectDelimiter(lines[0]);
  const headers = parseCsvLine(lines[0], delimiter);
  const skuIndex = resolveHeaderIndex(headers, SKU_HEADER_ALIASES);
  const unitCostIndex = resolveHeaderIndex(headers, UNIT_COST_HEADER_ALIASES);

  if (skuIndex < 0) {
    throw new Error("COGS CSV must include a sku column.");
  }
  if (unitCostIndex < 0) {
    throw new Error("COGS CSV must include a unit_cost column.");
  }

  const entries: PnlCogsCsvEntry[] = [];
  const seenSkus = new Set<string>();

  for (let i = 1; i < lines.length; i += 1) {
    const values = parseCsvLine(lines[i], delimiter);
    const isEmptyRow = values.every((value) => value.trim().length === 0);
    if (isEmptyRow) {
      continue;
    }
    const sku = (values[skuIndex] || "").trim();
    const unitCostRaw = values[unitCostIndex] || "";

    if (!sku) {
      throw new Error(`COGS CSV row ${i + 1} is missing sku.`);
    }
    if (seenSkus.has(sku)) {
      throw new Error(`COGS CSV contains duplicate sku ${sku}.`);
    }
    seenSkus.add(sku);

    const normalizedCost = normalizeUnitCost(unitCostRaw);
    if (normalizedCost !== null && Number.isNaN(Number(normalizedCost))) {
      throw new Error(`COGS CSV row ${i + 1} has an invalid unit_cost for ${sku}.`);
    }

    entries.push({
      sku,
      unit_cost: normalizedCost,
    });
  }

  return entries;
}

export function downloadPnlCogsCsv(filename: string, rows: PnlSkuCogs[]): void {
  downloadCsv(filename, buildPnlCogsCsv(rows));
}
