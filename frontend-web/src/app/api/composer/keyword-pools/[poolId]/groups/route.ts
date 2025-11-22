import { NextResponse, type NextRequest } from "next/server";
import type { ComposerKeywordGroup } from "@agency/lib/composer/types";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { isUuid, resolveComposerOrgIdFromSession } from "@/lib/composer/serverUtils";
import { mergeGroupsWithOverrides } from "@agency/lib/composer/keywords/mergeGroups";

interface KeywordGroupRow {
  id: string;
  organization_id: string;
  keyword_pool_id: string;
  group_index: number;
  label: string | null;
  phrases: string[];
  metadata: Record<string, unknown>;
  created_at: string;
}

const mapRowToGroup = (row: KeywordGroupRow): ComposerKeywordGroup => ({
  id: row.id,
  organizationId: row.organization_id,
  keywordPoolId: row.keyword_pool_id,
  groupIndex: row.group_index,
  label: row.label,
  phrases: row.phrases,
  metadata: row.metadata,
  createdAt: row.created_at,
});

interface OverrideRow {
  id: string;
  organization_id: string;
  keyword_pool_id: string;
  source_group_id: string | null;
  phrase: string;
  action: "move" | "remove" | "add" | "rename";
  target_group_label: string | null;
  target_group_index: number | null;
  created_at: string;
}

/**
 * GET /api/composer/keyword-pools/:id/groups
 * Returns all keyword groups for a pool, plus any overrides
 * Requirements:
 * - Pool must have status 'cleaned', 'grouped', or higher
 * - Returns groups ordered by group_index
 * - Includes overrides for manual adjustments tracking
 */
export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ poolId?: string }> },
) {
  const { poolId } = await context.params;

  if (!poolId || !isUuid(poolId)) {
    return NextResponse.json(
      { error: "invalid_pool_id", poolId: poolId ?? null },
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
    return NextResponse.json({ error: "Organization not found" }, { status: 401 });
  }

  // Verify pool exists and belongs to org
  const { data: pool, error: poolError } = await supabase
    .from("composer_keyword_pools")
    .select("id, status")
    .eq("id", poolId)
    .eq("organization_id", organizationId)
    .single();

  if (poolError || !pool) {
    return NextResponse.json(
      { error: "Pool not found or access denied" },
      { status: 404 },
    );
  }

  // Fetch groups
  const { data: groups, error: groupsError } = await supabase
    .from("composer_keyword_groups")
    .select("*")
    .eq("keyword_pool_id", poolId)
    .eq("organization_id", organizationId)
    .order("group_index", { ascending: true });

  if (groupsError) {
    return NextResponse.json(
      { error: "Failed to fetch groups", details: groupsError.message },
      { status: 500 },
    );
  }

  // Fetch overrides
  const { data: overrides, error: overridesError } = await supabase
    .from("composer_keyword_group_overrides")
    .select("*")
    .eq("keyword_pool_id", poolId)
    .eq("organization_id", organizationId)
    .order("created_at", { ascending: true });

  if (overridesError) {
    return NextResponse.json(
      { error: "Failed to fetch overrides", details: overridesError.message },
      { status: 500 },
    );
  }

  const mappedGroups = (groups || []).map(mapRowToGroup);
  const mappedOverrides =
    (overrides || []).map((row: OverrideRow) => ({
      id: row.id,
      organizationId: row.organization_id,
      keywordPoolId: row.keyword_pool_id,
      sourceGroupId: row.source_group_id,
      phrase: row.phrase,
      action: row.action,
      targetGroupLabel: row.target_group_label,
      targetGroupIndex: row.target_group_index,
      createdAt: row.created_at,
    })) ?? [];

  const merged = mergeGroupsWithOverrides(mappedGroups, mappedOverrides);

  return NextResponse.json({
    groups: mappedGroups,
    overrides: mappedOverrides,
    merged,
  });
}
