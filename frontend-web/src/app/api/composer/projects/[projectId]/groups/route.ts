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

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ projectId?: string }> },
) {
  const { projectId } = await context.params;
  if (!projectId || !isUuid(projectId)) {
    return NextResponse.json(
      { error: "invalid_project_id", projectId: projectId ?? null },
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

  const { data, error } = await supabase
    .from("composer_sku_groups")
    .select("*")
    .eq("project_id", projectId)
    .eq("organization_id", organizationId)
    .order("sort_order", { ascending: true });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const groups = (data ?? []).map(mapRowToGroup);
  return NextResponse.json({ groups });
}

interface CreateGroupPayload {
  name: string;
  description?: string | null;
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ projectId?: string }> },
) {
  const { projectId } = await context.params;
  if (!projectId || !isUuid(projectId)) {
    return NextResponse.json(
      { error: "invalid_project_id", projectId: projectId ?? null },
      { status: 400 },
    );
  }

  const payload = (await request.json()) as CreateGroupPayload;

  if (!payload.name || payload.name.trim() === "") {
    return NextResponse.json({ error: "Group name is required" }, { status: 400 });
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

  // Get the next sort order
  const { data: existingGroups } = await supabase
    .from("composer_sku_groups")
    .select("sort_order")
    .eq("project_id", projectId)
    .eq("organization_id", organizationId)
    .order("sort_order", { ascending: false })
    .limit(1);

  const nextSortOrder = existingGroups && existingGroups.length > 0
    ? existingGroups[0].sort_order + 1
    : 0;

  const { data, error } = await supabase
    .from("composer_sku_groups")
    .insert({
      organization_id: organizationId,
      project_id: projectId,
      name: payload.name.trim(),
      description: payload.description?.trim() || null,
      sort_order: nextSortOrder,
    })
    .select("*")
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ group: mapRowToGroup(data) }, { status: 201 });
}
