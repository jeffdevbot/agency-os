import { NextResponse, type NextRequest } from "next/server";
import type { ComposerSkuGroup } from "@agency/lib/composer/types";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { isUuid, resolveComposerOrgIdFromSession } from "@/lib/composer/serverUtils";

interface GroupRow {
  id: string;
  organization_id: string;
  project_id: string;
  name: string;
  description: string | null;
  sort_order: number;
  created_at: string;
}

const mapRowToGroup = (row: GroupRow): ComposerSkuGroup => ({
  id: row.id,
  organizationId: row.organization_id,
  projectId: row.project_id,
  name: row.name,
  description: row.description,
  sortOrder: row.sort_order,
  createdAt: row.created_at,
});

interface UpdateGroupPayload {
  name?: string;
  description?: string | null;
  sortOrder?: number;
}

export async function PATCH(
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

  const payload = (await request.json()) as UpdateGroupPayload;
  const updates: Record<string, unknown> = {};

  if (payload.name !== undefined) {
    if (payload.name.trim() === "") {
      return NextResponse.json({ error: "Group name cannot be empty" }, { status: 400 });
    }
    updates.name = payload.name.trim();
  }
  if (payload.description !== undefined) {
    updates.description = payload.description?.trim() || null;
  }
  if (payload.sortOrder !== undefined) {
    updates.sort_order = payload.sortOrder;
  }

  if (Object.keys(updates).length === 0) {
    return NextResponse.json({ error: "No valid fields provided" }, { status: 400 });
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

  const { data, error } = await supabase
    .from("composer_sku_groups")
    .update(updates)
    .eq("id", groupId)
    .eq("project_id", projectId)
    .eq("organization_id", organizationId)
    .select("*")
    .single();

  if (error || !data) {
    const status = error?.code === "PGRST116" ? 404 : 500;
    return NextResponse.json(
      { error: error?.message ?? "Group not found" },
      { status },
    );
  }

  return NextResponse.json({ group: mapRowToGroup(data) });
}

export async function DELETE(
  _request: NextRequest,
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

  // Check if any SKUs are assigned to this group
  const { count } = await supabase
    .from("composer_sku_variants")
    .select("id", { count: "exact", head: true })
    .eq("group_id", groupId)
    .eq("organization_id", organizationId);

  if (count && count > 0) {
    return NextResponse.json(
      { error: "Cannot delete group with assigned SKUs. Unassign all SKUs first." },
      { status: 400 },
    );
  }

  const { error } = await supabase
    .from("composer_sku_groups")
    .delete()
    .eq("id", groupId)
    .eq("project_id", projectId)
    .eq("organization_id", organizationId);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ success: true });
}
