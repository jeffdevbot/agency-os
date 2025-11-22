import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { isUuid, resolveComposerOrgIdFromSession } from "@/lib/composer/serverUtils";

/**
 * POST /api/composer/keyword-pools/:id/group-overrides
 * Adds a keyword grouping override (move, remove, or add action)
 * Requirements:
 * - Pool must have status 'cleaned' or 'grouped'
 * - Creates override record for tracking manual adjustments
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
  let override: {
    phrase: string;
    action: "move" | "remove" | "add" | "rename";
    sourceGroupId?: string | null;
    targetGroupLabel?: string;
    targetGroupIndex?: number;
  };
  try {
    override = await request.json();
  } catch {
    return NextResponse.json(
      { error: "Invalid request body" },
      { status: 400 },
    );
  }

  // Validate required fields
  if (!override.phrase || !override.action) {
    return NextResponse.json(
      { error: "Missing required fields: phrase, action" },
      { status: 400 },
    );
  }

  if (override.action === "rename" && !override.targetGroupLabel) {
    return NextResponse.json(
      { error: "Rename override requires targetGroupLabel" },
      { status: 400 },
    );
  }

  if (override.targetGroupIndex !== undefined && override.targetGroupIndex !== null) {
    if (override.targetGroupIndex < 0) {
      return NextResponse.json(
        { error: "targetGroupIndex must be >= 0" },
        { status: 400 },
      );
    }
  }

  // Verify pool exists and status allows overrides
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

  if (pool.status !== "cleaned" && pool.status !== "grouped") {
    return NextResponse.json(
      {
        error: "Cannot add overrides until pool is cleaned or grouped",
        currentStatus: pool.status,
      },
      { status: 400 },
    );
  }

  // Insert override record
  const { data: newOverride, error: insertError } = await supabase
    .from("composer_keyword_group_overrides")
    .insert({
      organization_id: organizationId,
      keyword_pool_id: poolId,
      phrase: override.phrase,
      action: override.action,
      source_group_id: override.sourceGroupId || null,
      target_group_label: override.targetGroupLabel || null,
      target_group_index: override.targetGroupIndex ?? null,
    })
    .select()
    .single();

  if (insertError) {
    return NextResponse.json(
      { error: "Failed to create override", details: insertError.message },
      { status: 500 },
    );
  }

  return NextResponse.json({ override: newOverride });
}

/**
 * DELETE /api/composer/keyword-pools/:id/group-overrides
 * Deletes all overrides for a pool (reset to AI-generated grouping)
 * Requirements:
 * - Pool must have status 'cleaned' or 'grouped'
 * - Removes all override records for the pool
 */
export async function DELETE(
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

  // Verify pool exists
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

  // Delete all overrides
  const { error: deleteError } = await supabase
    .from("composer_keyword_group_overrides")
    .delete()
    .eq("keyword_pool_id", poolId)
    .eq("organization_id", organizationId);

  if (deleteError) {
    return NextResponse.json(
      { error: "Failed to delete overrides", details: deleteError.message },
      { status: 500 },
    );
  }

  return NextResponse.json({ success: true });
}
