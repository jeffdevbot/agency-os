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
  if (!isUuid(projectId)) {
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

  const { data: project, error: fetchError } = await supabase
    .from("scribe_projects")
    .select("id, status, created_by")
    .eq("id", projectId)
    .eq("created_by", session.user.id)
    .single();

  if (fetchError || !project) {
    const status = fetchError?.code === "PGRST116" ? 404 : 500;
    return NextResponse.json(
      { error: { code: "not_found", message: fetchError?.message ?? "Project not found" } },
      { status },
    );
  }

  if (project.status === "archived") {
    return NextResponse.json(
      { error: { code: "forbidden", message: "Archived projects are read-only" } },
      { status: 403 },
    );
  }

  // Optional: enforce at least one SKU
  const { count: skuCount, error: skuError } = await supabase
    .from("scribe_skus")
    .select("*", { count: "exact", head: true })
    .eq("project_id", projectId);

  if (skuError) {
    return NextResponse.json({ error: { code: "server_error", message: skuError.message } }, { status: 500 });
  }

  if ((skuCount ?? 0) === 0) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "Add at least one SKU before approval" } },
      { status: 400 },
    );
  }

  const { data, error } = await supabase
    .from("scribe_projects")
    .update({ status: "stage_a_approved", updated_at: new Date().toISOString() })
    .eq("id", projectId)
    .eq("created_by", session.user.id)
    .select("id, name, status, updated_at")
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: { code: "server_error", message: error?.message ?? "Unable to approve Stage A" } },
      { status: 500 },
    );
  }

  return NextResponse.json({
    id: data.id,
    name: data.name,
    status: data.status,
    updatedAt: data.updated_at,
  });
}
