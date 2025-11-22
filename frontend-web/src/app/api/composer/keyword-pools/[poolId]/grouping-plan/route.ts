import { NextResponse, type NextRequest } from "next/server";
import type { GroupingConfig } from "@agency/lib/composer/types";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { isUuid, resolveComposerOrgIdFromSession } from "@/lib/composer/serverUtils";
import { mapRowToPool, type KeywordPoolRow } from "../route";
import { groupKeywords } from "@agency/lib/composer/ai/groupKeywords";
import { logUsageEvent } from "@agency/lib/composer/ai/usageLogger";

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

  const cleanedKeywords = pool.cleaned_keywords || [];

  if (cleanedKeywords.length === 0) {
    return NextResponse.json(
      { error: "no_cleaned_keywords_to_group" },
      { status: 400 },
    );
  }

  // Fetch project details for AI context
  const { data: project } = await supabase
    .from("composer_projects")
    .select("client_name, category")
    .eq("id", pool.project_id)
    .eq("organization_id", organizationId)
    .single();

  const startTime = Date.now();
  let aiGroups;
  let usage;

  try {
    // Call actual AI grouping function
    const result = await groupKeywords(cleanedKeywords, config, {
      project: {
        clientName: project?.client_name || "",
        category: project?.category || "",
      },
      poolType: pool.pool_type as "body" | "titles",
      poolId: pool.id,
    });

    aiGroups = result.groups;
    usage = result.usage;
  } catch (error) {
    // Log failed usage event
    const durationMs = Date.now() - startTime;
    await logUsageEvent({
      supabase,
      organizationId,
      projectId: pool.project_id,
      jobId: null,
      action: "keyword_grouping",
      model: "unknown",
      tokensIn: 0,
      tokensOut: 0,
      tokensTotal: 0,
      durationMs,
      meta: {
        pool_type: pool.pool_type,
        pool_id: poolId,
        keyword_count: cleanedKeywords.length,
        basis: config.basis || "unknown",
        error: error instanceof Error ? error.message : String(error),
      },
    });

    return NextResponse.json(
      { error: "AI grouping failed", details: error instanceof Error ? error.message : String(error) },
      { status: 500 },
    );
  }

  // Map AI groups to database format
  const dbGroups = aiGroups.map((group) => ({
    organization_id: organizationId,
    keyword_pool_id: poolId,
    group_index: group.groupIndex,
    label: group.label,
    phrases: group.phrases,
    metadata: group.metadata,
  }));

  // Insert groups
  const { data: upsertedGroups, error: insertError } = await supabase
    .from("composer_keyword_groups")
    .upsert(dbGroups, { onConflict: "keyword_pool_id,group_index" })
    .select("*");

  if (insertError || !upsertedGroups) {
    return NextResponse.json(
      { error: "Failed to create keyword groups", details: insertError?.message },
      { status: 500 },
    );
  }

  // Remove stale groups that are no longer present
  const newGroupIndexes = aiGroups.map((group) => group.groupIndex);
  if (newGroupIndexes.length > 0) {
    await supabase
      .from("composer_keyword_groups")
      .delete()
      .eq("keyword_pool_id", poolId)
      .eq("organization_id", organizationId)
      .not("group_index", "in", `(${newGroupIndexes.join(",")})`);
  }

  // Update pool: set status to 'grouped', save config, set timestamp
  const nextVersion = (pool.version ?? 1) + 1;
  const { data: updatedPool, error: updateError, status: updateStatus } = await supabase
    .from("composer_keyword_pools")
    .update({
      status: "grouped",
      grouping_config: config,
      grouped_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      version: nextVersion,
    })
    .eq("id", poolId)
    .eq("organization_id", organizationId)
    .eq("version", pool.version ?? 1)
    .select("*")
    .single<KeywordPoolRow>();

  if ((updateStatus === 204 && !updatedPool) || (!updatedPool && !updateError)) {
    return NextResponse.json(
      {
        error: "Concurrent update detected. Please refresh and try again.",
        code: "CONCURRENT_MODIFICATION",
      },
      { status: 409 },
    );
  }

  if (updateError || !updatedPool) {
    return NextResponse.json(
      { error: "Failed to update pool status" },
      { status: 500 },
    );
  }

  // Log successful usage event
  await logUsageEvent({
    supabase,
    organizationId,
    projectId: pool.project_id,
    jobId: null,
    action: "keyword_grouping",
    model: usage.model,
    tokensIn: usage.tokensIn,
    tokensOut: usage.tokensOut,
    tokensTotal: usage.tokensTotal,
    durationMs: usage.durationMs,
    meta: {
      pool_type: pool.pool_type,
      pool_id: poolId,
      keyword_count: cleanedKeywords.length,
      basis: config.basis || "unknown",
      group_count: aiGroups.length,
    },
  });

  // Map inserted groups to frontend format
  const mappedGroups = upsertedGroups.map((row) => ({
    id: row.id,
    organizationId: row.organization_id,
    keywordPoolId: row.keyword_pool_id,
    groupIndex: row.group_index,
    label: row.label,
    phrases: row.phrases,
    metadata: row.metadata,
    createdAt: row.created_at,
  }));

  return NextResponse.json({
    pool: mapRowToPool(updatedPool),
    groups: mappedGroups,
  });
}
