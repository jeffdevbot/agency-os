import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";

const isUuid = (value: unknown): value is string =>
  typeof value === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);

interface SkuRow {
  id: string;
  project_id: string;
  sku_code: string;
  asin: string | null;
  product_name: string | null;
  brand_tone: string | null;
  target_audience: string | null;
  words_to_avoid: string[] | null;
  supplied_content: string | null;
  sort_order: number | null;
  created_at: string;
  updated_at: string;
}

const mapSku = (row: SkuRow) => ({
  id: row.id,
  projectId: row.project_id,
  skuCode: row.sku_code,
  asin: row.asin,
  productName: row.product_name,
  brandTone: row.brand_tone,
  targetAudience: row.target_audience,
  wordsToAvoid: row.words_to_avoid ?? [],
  suppliedContent: row.supplied_content,
  sortOrder: row.sort_order,
  createdAt: row.created_at,
  updatedAt: row.updated_at,
});

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ projectId?: string }> },
) {
  const { projectId } = await context.params;
  if (!isUuid(projectId)) {
    return NextResponse.json({ error: { code: "validation_error", message: "invalid project id" } }, { status: 400 });
  }

  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Unauthorized" } }, { status: 401 });
  }

  const { data, error } = await supabase
    .from("scribe_skus")
    .select(
      "id, project_id, sku_code, asin, product_name, brand_tone, target_audience, words_to_avoid, supplied_content, sort_order, created_at, updated_at",
    )
    .eq("project_id", projectId)
    .order("sort_order", { ascending: true, nullsFirst: true });

  if (error) {
    return NextResponse.json({ error: { code: "server_error", message: error.message } }, { status: 500 });
  }

  return NextResponse.json((data ?? []).map(mapSku));
}

interface CreateSkuPayload {
  skuCode?: string;
  asin?: string | null;
  productName?: string | null;
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ projectId?: string }> },
) {
  const { projectId } = await context.params;
  if (!isUuid(projectId)) {
    return NextResponse.json({ error: { code: "validation_error", message: "invalid project id" } }, { status: 400 });
  }

  const payload = (await request.json()) as CreateSkuPayload;
  const skuCode = payload.skuCode?.trim() ?? "";

  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Unauthorized" } }, { status: 401 });
  }

  // enforce max 50 SKUs per project
  const { count, error: countError } = await supabase
    .from("scribe_skus")
    .select("*", { count: "exact", head: true })
    .eq("project_id", projectId);

  if (countError) {
    return NextResponse.json({ error: { code: "server_error", message: countError.message } }, { status: 500 });
  }

  if ((count ?? 0) >= 50) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "Maximum of 50 SKUs per project" } },
      { status: 400 },
    );
  }

  const now = new Date().toISOString();

  const { data, error } = await supabase
    .from("scribe_skus")
    .insert({
      project_id: projectId,
      sku_code: skuCode,
      asin: payload.asin?.trim() || null,
      product_name: payload.productName?.trim() || null,
      sort_order: (count ?? 0) + 1,
      created_at: now,
      updated_at: now,
    })
    .select(
      "id, project_id, sku_code, asin, product_name, brand_tone, target_audience, words_to_avoid, supplied_content, sort_order, created_at, updated_at",
    )
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: { code: "server_error", message: error?.message ?? "Unable to create SKU" } },
      { status: 500 },
    );
  }

  return NextResponse.json(mapSku(data));
}
