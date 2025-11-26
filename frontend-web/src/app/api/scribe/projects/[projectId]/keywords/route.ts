import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";

const isUuid = (value: unknown): value is string =>
  typeof value === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);

interface KeywordRow {
  id: string;
  project_id: string;
  sku_id: string;
  keyword: string;
  source: string | null;
  priority: number | null;
  created_at: string;
}

const mapKeyword = (row: KeywordRow) => ({
  id: row.id,
  projectId: row.project_id,
  skuId: row.sku_id,
  keyword: row.keyword,
  source: row.source,
  priority: row.priority,
  createdAt: row.created_at,
});

export async function GET(
  request: NextRequest,
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

  const skuId = new URL(request.url).searchParams.get("skuId");
  let query = supabase
    .from("scribe_keywords")
    .select("id, project_id, sku_id, keyword, source, priority, created_at")
    .eq("project_id", projectId);

  // If valid skuId param is provided, filter by it; otherwise return all keywords for project
  if (skuId && isUuid(skuId)) {
    query = query.eq("sku_id", skuId);
  }

  const { data, error } = await query;

  if (error) {
    return NextResponse.json({ error: { code: "server_error", message: error.message } }, { status: 500 });
  }

  return NextResponse.json((data ?? []).map(mapKeyword));
}

interface CreateKeywordPayload {
  keyword?: string;
  source?: string | null;
  priority?: number | null;
  skuId?: string;
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ projectId?: string }> },
) {
  const { projectId } = await context.params;
  if (!isUuid(projectId)) {
    return NextResponse.json({ error: { code: "validation_error", message: "invalid project id" } }, { status: 400 });
  }

  const payload = (await request.json()) as CreateKeywordPayload;
  const keyword = payload.keyword?.trim();
  const skuId = payload.skuId?.trim();

  if (!keyword) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "keyword is required" } },
      { status: 400 },
    );
  }

  if (!skuId) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "skuId is required" } },
      { status: 400 },
    );
  }

  if (!isUuid(skuId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "invalid skuId" } },
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

  // limit 10 per SKU
  const { count, error: countError } = await supabase
    .from("scribe_keywords")
    .select("*", { count: "exact", head: true })
    .eq("project_id", projectId)
    .eq("sku_id", skuId);

  if (countError) {
    return NextResponse.json({ error: { code: "server_error", message: countError.message } }, { status: 500 });
  }

  if ((count ?? 0) >= 10) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "Maximum of 10 keywords per scope" } },
      { status: 400 },
    );
  }

  const { data, error } = await supabase
    .from("scribe_keywords")
    .insert({
      project_id: projectId,
      sku_id: skuId,
      keyword,
      source: payload.source ?? null,
      priority: payload.priority ?? null,
    })
    .select("id, project_id, sku_id, keyword, source, priority, created_at")
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: { code: "server_error", message: error?.message ?? "Unable to add keyword" } },
      { status: 500 },
    );
  }

  return NextResponse.json(mapKeyword(data));
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ projectId?: string }> },
) {
  const { projectId } = await context.params;
  if (!isUuid(projectId)) {
    return NextResponse.json({ error: { code: "validation_error", message: "invalid project id" } }, { status: 400 });
  }
  const id = new URL(request.url).searchParams.get("id");
  if (!isUuid(id)) {
    return NextResponse.json({ error: { code: "validation_error", message: "invalid keyword id" } }, { status: 400 });
  }

  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Unauthorized" } }, { status: 401 });
  }

  const { error } = await supabase
    .from("scribe_keywords")
    .delete()
    .eq("id", id)
    .eq("project_id", projectId);

  if (error) {
    const status = error.code === "PGRST116" ? 404 : 500;
    return NextResponse.json(
      { error: { code: status === 404 ? "not_found" : "server_error", message: error.message } },
      { status },
    );
  }

  return NextResponse.json({ ok: true });
}
