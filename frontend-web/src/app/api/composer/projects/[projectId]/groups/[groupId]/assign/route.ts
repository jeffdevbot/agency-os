import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { isUuid, resolveComposerOrgIdFromSession } from "@/lib/composer/serverUtils";

interface AssignPayload {
  variantIds: string[];
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ projectId?: string; groupId?: string }> },
) {
  const { projectId, groupId } = await context.params;
  if (!projectId || !isUuid(projectId)) {
    return NextResponse.json(
      { error: "invalid_project_id", projectId: projectId ?? null },
      { status: 400 },
    );
  }
  if (!groupId || !isUuid(groupId)) {
    return NextResponse.json(
      { error: "invalid_group_id", groupId: groupId ?? null },
      { status: 400 },
    );
  }

  const payload = (await request.json()) as AssignPayload;

  if (!Array.isArray(payload.variantIds)) {
    return NextResponse.json({ error: "variantIds must be an array" }, { status: 400 });
  }

  // Validate all variant IDs are UUIDs
  const invalidIds = payload.variantIds.filter((id) => !isUuid(id));
  if (invalidIds.length > 0) {
    return NextResponse.json(
      { error: "Invalid variant IDs", invalidIds },
      { status: 400 },
    );
  }

  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const organizationId = resolveComposerOrgIdFromSession(session);

  if (!organizationId) {
    return NextResponse.json({ error: "Organization not found in session" }, { status: 403 });
  }

  // Verify the project belongs to this organization
  const { data: project, error: projectError } = await supabase
    .from("composer_projects")
    .select("id")
    .eq("id", projectId)
    .eq("organization_id", organizationId)
    .single();

  if (projectError || !project) {
    return NextResponse.json({ error: "Project not found" }, { status: 404 });
  }

  // Verify the group exists and belongs to this project
  const { data: group, error: groupError } = await supabase
    .from("composer_sku_groups")
    .select("id")
    .eq("id", groupId)
    .eq("project_id", projectId)
    .eq("organization_id", organizationId)
    .single();

  if (groupError || !group) {
    return NextResponse.json({ error: "Group not found" }, { status: 404 });
  }

  // Update all specified variants to belong to this group
  if (payload.variantIds.length > 0) {
    const { error: updateError } = await supabase
      .from("composer_sku_variants")
      .update({ group_id: groupId })
      .in("id", payload.variantIds)
      .eq("project_id", projectId)
      .eq("organization_id", organizationId);

    if (updateError) {
      return NextResponse.json({ error: updateError.message }, { status: 500 });
    }
  }

  return NextResponse.json({ success: true, assignedCount: payload.variantIds.length });
}
