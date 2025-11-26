import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";

const isUuid = (value: unknown): value is string =>
  typeof value === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);

interface AttributeRow {
  id: string;
  project_id: string;
  name: string;
  slug: string;
  sort_order: number | null;
  created_at: string;
  updated_at: string;
}

const mapAttribute = (row: AttributeRow) => ({
  id: row.id,
  projectId: row.project_id,
  name: row.name,
  slug: row.slug,
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
    .from("scribe_variant_attributes")
    .select("id, project_id, name, slug, sort_order, created_at, updated_at")
    .eq("project_id", projectId)
    .order("sort_order", { ascending: true, nullsFirst: true });

  if (error) {
    return NextResponse.json({ error: { code: "server_error", message: error.message } }, { status: 500 });
  }

  return NextResponse.json((data ?? []).map(mapAttribute));
}

interface CreateAttributePayload {
  name?: string;
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ projectId?: string }> },
) {
  const { projectId } = await context.params;
  if (!isUuid(projectId)) {
    return NextResponse.json({ error: { code: "validation_error", message: "invalid project id" } }, { status: 400 });
  }

  const payload = (await request.json()) as CreateAttributePayload;
  const name = payload.name?.trim();

  if (!name) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "name is required" } },
      { status: 400 },
    );
  }

  const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");

  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Unauthorized" } }, { status: 401 });
  }

  const { count, error: countError } = await supabase
    .from("scribe_variant_attributes")
    .select("*", { count: "exact", head: true })
    .eq("project_id", projectId);

  if (countError) {
    return NextResponse.json({ error: { code: "server_error", message: countError.message } }, { status: 500 });
  }

  if ((count ?? 0) >= 10) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "Maximum of 10 variant attributes" } },
      { status: 400 },
    );
  }

  const { data, error } = await supabase
    .from("scribe_variant_attributes")
    .insert({
      project_id: projectId,
      name,
      slug,
      sort_order: (count ?? 0) + 1,
    })
    .select("id, project_id, name, slug, sort_order, created_at, updated_at")
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: { code: "server_error", message: error?.message ?? "Unable to add attribute" } },
      { status: 500 },
    );
  }

  return NextResponse.json(mapAttribute(data));
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
    return NextResponse.json({ error: { code: "validation_error", message: "invalid attribute id" } }, { status: 400 });
  }

  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Unauthorized" } }, { status: 401 });
  }

  const { error } = await supabase
    .from("scribe_variant_attributes")
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
