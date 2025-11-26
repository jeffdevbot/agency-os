import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";

const isUuid = (value: unknown): value is string =>
  typeof value === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);

interface ValueRow {
  id: string;
  sku_id: string;
  attribute_id: string;
  value: string;
  created_at: string;
  updated_at: string;
}

const mapValue = (row: ValueRow) => ({
  id: row.id,
  skuId: row.sku_id,
  attributeId: row.attribute_id,
  value: row.value,
  createdAt: row.created_at,
  updatedAt: row.updated_at,
});

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ projectId?: string; attributeId?: string }> },
) {
  const { projectId, attributeId } = await context.params;
  if (!isUuid(projectId) || !isUuid(attributeId)) {
    return NextResponse.json({ error: { code: "validation_error", message: "invalid ids" } }, { status: 400 });
  }

  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Unauthorized" } }, { status: 401 });
  }

  const { data, error } = await supabase
    .from("scribe_sku_variant_values")
    .select("id, sku_id, attribute_id, value, created_at, updated_at")
    .eq("attribute_id", attributeId);

  if (error) {
    return NextResponse.json({ error: { code: "server_error", message: error.message } }, { status: 500 });
  }

  return NextResponse.json((data ?? []).map(mapValue));
}

interface UpsertValuePayload {
  skuId?: string;
  value?: string;
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ projectId?: string; attributeId?: string }> },
) {
  const { projectId, attributeId } = await context.params;
  if (!isUuid(projectId) || !isUuid(attributeId)) {
    return NextResponse.json({ error: { code: "validation_error", message: "invalid ids" } }, { status: 400 });
  }

  const payload = (await request.json()) as UpsertValuePayload;
  const skuId = payload.skuId?.trim();
  const value = payload.value?.trim();

  if (!skuId || !isUuid(skuId) || !value) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "skuId and value are required" } },
      { status: 400 },
    );
  }

  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Unauthorized" } }, { status: 401 });
  }

  const { data, error } = await supabase
    .from("scribe_sku_variant_values")
    .upsert(
      {
        sku_id: skuId,
        attribute_id: attributeId,
        value,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "sku_id,attribute_id" },
    )
    .select("id, sku_id, attribute_id, value, created_at, updated_at")
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: { code: "server_error", message: error?.message ?? "Unable to save attribute value" } },
      { status: 500 },
    );
  }

  return NextResponse.json(mapValue(data));
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ projectId?: string; attributeId?: string }> },
) {
  const { projectId, attributeId } = await context.params;
  if (!isUuid(projectId) || !isUuid(attributeId)) {
    return NextResponse.json({ error: { code: "validation_error", message: "invalid ids" } }, { status: 400 });
  }
  const valueId = new URL(request.url).searchParams.get("id");
  if (!isUuid(valueId)) {
    return NextResponse.json({ error: { code: "validation_error", message: "invalid value id" } }, { status: 400 });
  }

  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Unauthorized" } }, { status: 401 });
  }

  const { error } = await supabase
    .from("scribe_sku_variant_values")
    .delete()
    .eq("id", valueId);

  if (error) {
    const status = error.code === "PGRST116" ? 404 : 500;
    return NextResponse.json(
      { error: { code: status === 404 ? "not_found" : "server_error", message: error.message } },
      { status },
    );
  }

  return NextResponse.json({ ok: true });
}
