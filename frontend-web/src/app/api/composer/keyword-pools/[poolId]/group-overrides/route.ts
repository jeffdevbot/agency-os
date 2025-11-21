import { NextResponse, type NextRequest } from "next/server";
import type { KeywordGroupOverrideAction } from "@agency/lib/composer/types";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { isUuid, resolveComposerOrgIdFromSession } from "@/lib/composer/serverUtils";

interface CreateOverridePayload {
  phrase: string;
  action: KeywordGroupOverrideAction;
  targetGroupLabel?: string;
  targetGroupIndex?: number;
  sourceGroupId?: string;
}

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

  const payload = (await request.json()) as CreateOverridePayload;

  if (!payload.phrase || !payload.action) {
    return NextResponse.json(
      { error: "phrase and action are required" },
      { status: 400 },
    );
  }

  const allowedActions: KeywordGroupOverrideAction[] = ["move", "remove", "add"];
  if (!allowedActions.includes(payload.action)) {
    return NextResponse.json(
      { error: "invalid action", allowed: allowedActions },
      { status: 400 },
    );
  }

  if ((payload.action === "move" || payload.action === "add") && payload.targetGroupIndex === undefined) {
    return NextResponse.json(
      { error: "targetGroupIndex is required for move and add actions" },
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

  const { data: insertedOverride, error: insertError } = await supabase
    .from("composer_keyword_group_overrides")
    .insert({
      organization_id: organizationId,
      keyword_pool_id: poolId,
      phrase: payload.phrase,
      action: payload.action,
      target_group_label: payload.targetGroupLabel || null,
      target_group_index: payload.targetGroupIndex ?? null,
      source_group_id: payload.sourceGroupId || null,
    })
    .select("*")
    .single();

  if (insertError || !insertedOverride) {
    return NextResponse.json(
      { error: insertError?.message ?? "Failed to create override" },
      { status: 500 },
    );
  }

  await supabase
    .from("composer_keyword_pools")
    .update({
      approved_at: null,
    })
    .eq("id", poolId);

  return NextResponse.json({ override: insertedOverride });
}

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

  const { error: deleteError } = await supabase
    .from("composer_keyword_group_overrides")
    .delete()
    .eq("keyword_pool_id", poolId)
    .eq("organization_id", organizationId);

  if (deleteError) {
    return NextResponse.json(
      { error: deleteError.message },
      { status: 500 },
    );
  }

  await supabase
    .from("composer_keyword_pools")
    .update({
      approved_at: null,
    })
    .eq("id", poolId);

  return NextResponse.json({ success: true, deleted: true });
}
