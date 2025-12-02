import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";

const isUuid = (value: unknown): value is string =>
  typeof value === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);

export async function POST(
  _request: NextRequest,
  context: { params: Promise<{ projectId?: string }> },
) {
  const { projectId } = await context.params;
  if (!projectId || !isUuid(projectId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "invalid project id" } },
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

  const { data: existing, error: fetchError } = await supabase
    .from("scribe_projects")
    .select("id, status")
    .eq("id", projectId)
    .eq("created_by", session.user.id)
    .single();

  if (fetchError || !existing) {
    const status = fetchError?.code === "PGRST116" ? 404 : 500;
    return NextResponse.json(
      { error: { code: "not_found", message: fetchError?.message ?? "Project not found" } },
      { status },
    );
  }

  if (existing.status === "archived") {
    return NextResponse.json(
      { error: { code: "conflict", message: "Project already archived" } },
      { status: 409 },
    );
  }

  const now = new Date().toISOString();

  const { data, error } = await supabase
    .from("scribe_projects")
    .update({ status: "archived", updated_at: now })
    .eq("id", projectId)
    .eq("created_by", session.user.id)
    .select("id, name, locale, category, sub_category, status, created_at, updated_at")
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: { code: "server_error", message: error?.message ?? "Unable to archive project" } },
      { status: 500 },
    );
  }

  return NextResponse.json({
    id: data.id,
    name: data.name,
    locale: data.locale,
    category: data.category,
    subCategory: data.sub_category,
    status: data.status,
    createdAt: data.created_at,
    updatedAt: data.updated_at,
  });
}
