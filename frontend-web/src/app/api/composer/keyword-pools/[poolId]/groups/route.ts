import { NextResponse, type NextRequest } from "next/server";
import type {
  ComposerKeywordGroup,
  ComposerKeywordGroupOverride,
} from "@agency/lib/composer/types";
import { mergeGroupsWithOverrides } from "@agency/lib/composer/keywords/mergeGroups";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { isUuid, resolveComposerOrgIdFromSession } from "@/lib/composer/serverUtils";

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

interface GroupOverrideRow {
  id: string;
  organization_id: string;
  keyword_pool_id: string;
  source_group_id: string | null;
  phrase: string;
  action: string;
  target_group_label: string | null;
  target_group_index: number | null;
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

const mapRowToOverride = (row: GroupOverrideRow): ComposerKeywordGroupOverride => ({
  id: row.id,
  organizationId: row.organization_id,
  keywordPoolId: row.keyword_pool_id,
  sourceGroupId: row.source_group_id,
  phrase: row.phrase,
  action: row.action as "move" | "remove" | "add",
  targetGroupLabel: row.target_group_label,
  targetGroupIndex: row.target_group_index,
  createdAt: row.created_at,
});

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
    return NextResponse.json(
      { error: "Organization not found in session" },
      { status: 403 },
    );
  }

  const { data: poolData, error: poolError } = await supabase
    .from("composer_keyword_pools")
    .select("id, organization_id")
    .eq("id", poolId)
    .eq("organization_id", organizationId)
    .single();

  if (poolError || !poolData) {
    return NextResponse.json({ error: "Keyword pool not found" }, { status: 404 });
  }

  const { data: groupsData, error: groupsError } = await supabase
    .from("composer_keyword_groups")
    .select("*")
    .eq("keyword_pool_id", poolId)
    .eq("organization_id", organizationId)
    .order("group_index", { ascending: true });

  if (groupsError) {
    return NextResponse.json(
      { error: groupsError.message },
      { status: 500 },
    );
  }

  const aiGroups = (groupsData || []).map((row) => mapRowToGroup(row as KeywordGroupRow));

  const { data: overridesData, error: overridesError } = await supabase
    .from("composer_keyword_group_overrides")
    .select("*")
    .eq("keyword_pool_id", poolId)
    .eq("organization_id", organizationId)
    .order("created_at", { ascending: true });

  if (overridesError) {
    return NextResponse.json(
      { error: overridesError.message },
      { status: 500 },
    );
  }

  const overrides = (overridesData || []).map((row) => mapRowToOverride(row as GroupOverrideRow));

  const merged = mergeGroupsWithOverrides(aiGroups, overrides);

  return NextResponse.json({
    aiGroups,
    overrides,
    merged,
  });
}
