import { NextResponse, type NextRequest } from "next/server";
import type { GroupingConfig } from "@agency/lib/composer/types";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { isUuid, resolveComposerOrgIdFromSession } from "@/lib/composer/serverUtils";
import { mapRowToPool, type KeywordPoolRow } from "../route";

/**
 * POST /api/composer/keyword-pools/:id/grouping-plan
 * Generates keyword grouping plan based on configuration
 * Requirements:
 * - Pool must have status 'cleaned'
 * - Creates groups in composer_keyword_groups table
 * - Updates pool status to 'grouped' and sets grouped_at timestamp
 */
export async function POST(
  request: NextRequest,
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

  // Parse request body
  let config: GroupingConfig;
  try {
    const body = await request.json();
    config = body.config ?? {};
  } catch {
    return NextResponse.json(
      { error: "Invalid request body. Expected { config: GroupingConfig }" },
      { status: 400 },
    );
  }

  // Fetch existing pool
  const { data: pool, error: fetchError } = await supabase
    .from("composer_keyword_pools")
    .select("*")
    .eq("id", poolId)
    .eq("organization_id", organizationId)
    .single<KeywordPoolRow>();

  if (fetchError || !pool) {
    return NextResponse.json(
      { error: "Pool not found or access denied" },
      { status: 404 },
    );
  }

  // BLOCKER FIX: Validate pool status (Red Team requirement #1)
  if (pool.status !== "cleaned") {
    return NextResponse.json(
      {
        error: "Cannot generate grouping plan until cleanup is approved",
        currentStatus: pool.status,
        requiredStatus: "cleaned",
      },
      { status: 400 },
    );
  }

  // TODO: Implement actual grouping algorithm based on config.basis
  // For now, create placeholder groups from cleaned_keywords
  const cleanedKeywords = pool.cleaned_keywords || [];

  if (cleanedKeywords.length === 0) {
    return NextResponse.json(
      { error: "No cleaned keywords available for grouping" },
      { status: 400 },
    );
  }

  // Delete existing groups for this pool (regenerate scenario)
  await supabase
    .from("composer_keyword_groups")
    .delete()
    .eq("keyword_pool_id", poolId)
    .eq("organization_id", organizationId);

  // TODO: Replace with actual AI grouping logic
  // Placeholder: Create simple groups based on configuration
  const groupSize = config.phrasesPerGroup || 10;
  const groupCount = config.groupCount || Math.ceil(cleanedKeywords.length / groupSize);

  const groups: Array<{
    organization_id: string;
    keyword_pool_id: string;
    group_index: number;
    label: string | null;
    phrases: string[];
    metadata: Record<string, unknown>;
  }> = [];

  for (let i = 0; i < groupCount; i++) {
    const start = i * groupSize;
    const end = Math.min(start + groupSize, cleanedKeywords.length);
    const phrases = cleanedKeywords.slice(start, end);

    if (phrases.length > 0) {
      groups.push({
        organization_id: organizationId,
        keyword_pool_id: poolId,
        group_index: i,
        label: `Group ${i + 1}`,
        phrases,
        metadata: { generatedFrom: config.basis || "default" },
      });
    }
  }

  // Insert groups
  const { error: insertError } = await supabase
    .from("composer_keyword_groups")
    .insert(groups);

  if (insertError) {
    return NextResponse.json(
      { error: "Failed to create keyword groups", details: insertError.message },
      { status: 500 },
    );
  }

  // Update pool: set status to 'grouped', save config, set timestamp
  const { data: updatedPool, error: updateError } = await supabase
    .from("composer_keyword_pools")
    .update({
      status: "grouped",
      grouping_config: config,
      grouped_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    })
    .eq("id", poolId)
    .eq("organization_id", organizationId)
    .select("*")
    .single<KeywordPoolRow>();

  if (updateError || !updatedPool) {
    return NextResponse.json(
      { error: "Failed to update pool status" },
      { status: 500 },
    );
  }

  return NextResponse.json({
    pool: mapRowToPool(updatedPool),
    groupsCreated: groups.length,
  });
}
