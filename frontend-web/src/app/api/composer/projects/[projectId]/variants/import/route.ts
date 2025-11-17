import { NextResponse, type NextRequest } from "next/server";
import { cookies } from "next/headers";
import { createRouteHandlerClient } from "@supabase/auth-helpers-nextjs";

interface ImportPayload {
  source: "csv" | "paste";
  raw: string;
}

interface ParsedVariant {
  sku: string;
  asin: string | null;
  parentSku?: string | null;
  attributes: Record<string, string | null>;
  notes?: string | null;
}

const detectDelimiter = (lines: string[]): string => {
  if (lines.some((line) => line.includes("\t"))) return "\t";
  if (lines.some((line) => line.includes(";"))) return ";";
  return ",";
};

const normalizeHeader = (header: string) => header.trim().toLowerCase().replace(/[\s_-]+/g, "");

const parseTabularText = (raw: string): { variants: ParsedVariant[]; detectedAttributes: string[] } => {
  const trimmed = raw.trim();
  if (!trimmed) {
    return { variants: [], detectedAttributes: [] };
  }

  const lines = trimmed.split(/\r?\n/).filter((line) => line.trim().length > 0);
  if (lines.length < 2) {
    throw new Error("not_enough_rows");
  }

  const delimiter = detectDelimiter(lines);
  const headers = lines[0].split(delimiter).map((header) => header.trim());
  const normalizedHeaders = headers.map(normalizeHeader);
  const skuIndex = normalizedHeaders.indexOf("sku");
  const asinIndex = normalizedHeaders.indexOf("asin");
  if (skuIndex === -1) {
    throw new Error("missing_required_columns");
  }
  const parentIndex =
    normalizedHeaders.indexOf("parentsku") !== -1
      ? normalizedHeaders.indexOf("parentsku")
      : normalizedHeaders.indexOf("parent");
  const notesIndex = normalizedHeaders.indexOf("notes");

  const attributeColumns = headers
    .map((header, index) => ({ header, index, normalized: normalizedHeaders[index] }))
    .filter(
      ({ index, normalized }) =>
        index !== skuIndex &&
        index !== asinIndex &&
        index !== parentIndex &&
        index !== notesIndex &&
        normalized.length > 0,
    );

  const variants: ParsedVariant[] = [];

  for (let rowIndex = 1; rowIndex < lines.length; rowIndex += 1) {
    const rawLine = lines[rowIndex];
    const values = rawLine.split(delimiter).map((value) => value.trim());
    const sku = values[skuIndex] ?? "";
    const asin = asinIndex !== -1 ? values[asinIndex]?.trim() ?? "" : "";
    if (!sku && !asin) {
      continue;
    }
    if (!sku) {
      throw new Error(`missing_sku_row_${rowIndex + 1}`);
    }
    const parentSku =
      parentIndex !== -1 ? values[parentIndex]?.trim() || null : null;
    const notes = notesIndex !== -1 ? values[notesIndex]?.trim() || null : null;

    const attributes: Record<string, string | null> = {};
    attributeColumns.forEach(({ header, index }) => {
      const value = values[index]?.trim();
      if (value) {
        attributes[header] = value;
      }
    });

    variants.push({
      sku,
      asin: asin || null,
      parentSku,
      attributes,
      notes: notes || undefined,
    });
  }

  const detectedAttributes = attributeColumns.map((column) => column.header);
  return { variants, detectedAttributes };
};

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ projectId?: string }> },
) {
  await context.params;
  const cookieStore = await cookies();
  const supabase = createRouteHandlerClient({
    cookies: () => cookieStore,
  });
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const payload = (await request.json()) as ImportPayload;
  if (payload.source !== "csv" && payload.source !== "paste") {
    return NextResponse.json({ error: "Invalid source" }, { status: 400 });
  }
  if (typeof payload.raw !== "string" || payload.raw.trim().length === 0) {
    return NextResponse.json({ error: "raw input required" }, { status: 400 });
  }

  try {
    const result = parseTabularText(payload.raw);
    return NextResponse.json(result);
  } catch (error) {
    if (error instanceof Error) {
      if (error.message === "missing_required_columns") {
        return NextResponse.json(
          { error: "CSV must include a sku column" },
          { status: 400 },
        );
      }
      if (error.message === "not_enough_rows") {
        return NextResponse.json(
          { error: "Provide at least one row of SKU data" },
          { status: 400 },
        );
      }
      if (error.message.startsWith("missing_sku_row_")) {
        return NextResponse.json(
          { error: `Missing SKU on ${error.message.replace("missing_sku_row_", "row ")}` },
          { status: 400 },
        );
      }
    }
    return NextResponse.json(
      { error: "Unable to parse SKU data. Please check the file format." },
      { status: 400 },
    );
  }
}
