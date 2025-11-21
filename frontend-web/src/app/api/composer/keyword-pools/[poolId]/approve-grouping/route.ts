import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { isUuid, resolveComposerOrgIdFromSession } from "@/lib/composer/serverUtils";
import { mapRowToPool, type KeywordPoolRow } from "../../route";

/**
 * POST /api/composer/keyword-pools/:id/approve-grouping
 * Approves the keyword grouping plan, allowing progression to next step
 * Requirements (Red Team BLOCKER fixes):
 * - Pool must have status 'grouped' (cannot skip cleanup approval)
 * - Updates pool status and sets approved_at timestamp
 * - TODO: Add optimistic locking using updated_at (Red Team WARNING #4)
 */
export async function POST(
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
  // Cannot approve grouping unless grouping plan was generated first
  if (pool.status !== "grouped") {
    return NextResponse.json(
      {
        error: "Cannot approve grouping until grouping plan is generated",
        currentStatus: pool.status,
        requiredStatus: "grouped",
      },
      { status: 400 },
    );
  }

  // Update pool: set approved_at timestamp
  // Note: Status remains 'grouped' - approval is tracked via approved_at field
  // This allows the step validation logic to check for both pools having approved_at set
  const { data: updatedPool, error: updateError } = await supabase
    .from("composer_keyword_pools")
    .update({
      approved_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    })
    .eq("id", poolId)
    .eq("organization_id", organizationId)
    // TODO (Red Team WARNING #4): Add optimistic locking check
    // .eq("updated_at", pool.updated_at)
    .select("*")
    .single<KeywordPoolRow>();

  if (updateError || !updatedPool) {
    // TODO: Check if this failed due to optimistic lock conflict
    return NextResponse.json(
      { error: "Failed to approve grouping" },
      { status: 500 },
    );
  }

  return NextResponse.json({ pool: mapRowToPool(updatedPool) });
}

/**
 * DELETE /api/composer/keyword-pools/:id/approve-grouping
 * Unapproves the grouping (user wants to regenerate or modify)
 * Requirements:
 * - Pool must have approved_at set
 * - Clears approved_at timestamp
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

  if (!pool.approved_at) {
    return NextResponse.json(
      { error: "Grouping is not approved" },
      { status: 400 },
    );
  }

  // Clear approval timestamp
  const { data: updatedPool, error: updateError } = await supabase
    .from("composer_keyword_pools")
    .update({
      approved_at: null,
      updated_at: new Date().toISOString(),
    })
    .eq("id", poolId)
    .eq("organization_id", organizationId)
    .select("*")
    .single<KeywordPoolRow>();

  if (updateError || !updatedPool) {
    return NextResponse.json(
      { error: "Failed to unapprove grouping" },
      { status: 500 },
    );
  }

  return NextResponse.json({ pool: mapRowToPool(updatedPool) });
}
