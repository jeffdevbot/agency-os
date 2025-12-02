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

  // Fetch project and verify ownership
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

  // Gate: require stage_b_approved or stage_c_approved
  if (project.status !== "stage_b_approved" && project.status !== "stage_c_approved") {
    return NextResponse.json(
      {
        error: {
          code: "validation_error",
          message: "Stage B must be approved before approving copy",
        },
      },
      { status: 400 },
    );
  }

  if (project.status === "archived") {
    return NextResponse.json(
      { error: { code: "forbidden", message: "Archived projects are read-only" } },
      { status: 403 },
    );
  }

  // Get all SKUs for this project
  const { data: skus, error: skusError } = await supabase
    .from("scribe_skus")
    .select("id")
    .eq("project_id", projectId);

  if (skusError) {
    return NextResponse.json(
      { error: { code: "server_error", message: skusError.message } },
      { status: 500 },
    );
  }

  if (!skus || skus.length === 0) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "No SKUs found in project" } },
      { status: 400 },
    );
  }

  // Validate that each SKU has generated content
  for (const sku of skus) {
    const { data: content, error: contentError } = await supabase
      .from("scribe_generated_content")
      .select("id")
      .eq("sku_id", sku.id)
      .single();

    if (contentError || !content) {
      return NextResponse.json(
        {
          error: {
            code: "validation_error",
            message: "All SKUs must have generated content before approving Stage C",
          },
        },
        { status: 400 },
      );
    }
  }

  // Update project status to stage_c_approved
  const { data, error } = await supabase
    .from("scribe_projects")
    .update({ status: "stage_c_approved", updated_at: new Date().toISOString() })
    .eq("id", projectId)
    .eq("created_by", session.user.id)
    .select("id, name, status, updated_at")
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: { code: "server_error", message: error?.message ?? "Unable to approve Stage C" } },
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
