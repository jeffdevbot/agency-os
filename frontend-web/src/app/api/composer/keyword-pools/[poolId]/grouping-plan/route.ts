import { NextResponse, type NextRequest } from "next/server";
import type { GroupingConfig } from "@agency/lib/composer/types";
import { groupKeywords } from "@agency/lib/composer/ai/groupKeywords";
import { logUsageEvent } from "@agency/lib/composer/ai/usageLogger";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { isUuid, resolveComposerOrgIdFromSession } from "@/lib/composer/serverUtils";
import { mapRowToPool, type KeywordPoolRow } from "../route";

interface GroupingPlanPayload {
  config: GroupingConfig;
}

interface ProjectRow {
  id: string;
  organization_id: string;
  client_name: string | null;
  category: string | null;
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

  const payload = (await request.json()) as GroupingPlanPayload;
  const config: GroupingConfig = payload.config || {};

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

  const { data: poolRow, error: poolError } = await supabase
    .from("composer_keyword_pools")
    .select("*")
    .eq("id", poolId)
    .eq("organization_id", organizationId)
    .single();

  if (poolError || !poolRow) {
    return NextResponse.json({ error: "Keyword pool not found" }, { status: 404 });
  }

  const pool = poolRow as KeywordPoolRow;

  if (pool.status !== "cleaned") {
    return NextResponse.json(
      { error: "pool_must_be_cleaned_before_grouping", status: pool.status },
      { status: 400 },
    );
  }

  if (!pool.cleaned_keywords || pool.cleaned_keywords.length === 0) {
    return NextResponse.json(
      { error: "no_cleaned_keywords_to_group" },
      { status: 400 },
    );
  }

  const { data: projectRow, error: projectError } = await supabase
    .from("composer_projects")
    .select("id, organization_id, client_name, category")
    .eq("id", pool.project_id)
    .eq("organization_id", organizationId)
    .single();

  if (projectError || !projectRow) {
    return NextResponse.json({ error: "Project not found" }, { status: 404 });
  }

  const project = projectRow as ProjectRow;

  const startTime = Date.now();

  try {
    const groups = await groupKeywords(pool.cleaned_keywords, config, {
      project: {
        clientName: project.client_name,
        category: project.category,
      },
      poolType: pool.pool_type as "body" | "titles",
      poolId: pool.id,
    });

    const durationMs = Date.now() - startTime;

    const { data: existingGroups } = await supabase
      .from("composer_keyword_groups")
      .select("id")
      .eq("keyword_pool_id", poolId);

    if (existingGroups && existingGroups.length > 0) {
      await supabase
        .from("composer_keyword_groups")
        .delete()
        .eq("keyword_pool_id", poolId);
    }

    const groupsToInsert = groups.map((group) => ({
      organization_id: organizationId,
      keyword_pool_id: poolId,
      group_index: group.groupIndex,
      label: group.label,
      phrases: group.phrases,
      metadata: group.metadata,
    }));

    const { data: insertedGroups, error: insertError } = await supabase
      .from("composer_keyword_groups")
      .insert(groupsToInsert)
      .select("*");

    if (insertError || !insertedGroups) {
      return NextResponse.json(
        { error: insertError?.message ?? "Failed to save groups" },
        { status: 500 },
      );
    }

    const { data: updatedPool, error: updateError } = await supabase
      .from("composer_keyword_pools")
      .update({
        grouping_config: config,
        grouped_at: new Date().toISOString(),
        approved_at: null,
      })
      .eq("id", poolId)
      .select("*")
      .single();

    if (updateError || !updatedPool) {
      return NextResponse.json(
        { error: updateError?.message ?? "Failed to update pool" },
        { status: 500 },
      );
    }

    const tokensIn = Math.ceil(pool.cleaned_keywords.join(" ").length / 4);
    const tokensOut = Math.ceil(JSON.stringify(groups).length / 4);

    await logUsageEvent({
      supabase,
      organizationId,
      projectId: pool.project_id,
      jobId: null,
      action: "keyword_grouping",
      model: process.env.OPENAI_MODEL_PRIMARY || "gpt-5.1-nano",
      tokensIn,
      tokensOut,
      tokensTotal: tokensIn + tokensOut,
      durationMs,
      meta: {
        pool_type: pool.pool_type,
        pool_id: poolId,
        keyword_count: pool.cleaned_keywords.length,
        basis: config.basis || "auto",
        group_count: groups.length,
      },
    });

    return NextResponse.json({
      pool: mapRowToPool(updatedPool as KeywordPoolRow),
      groups: insertedGroups,
    });
  } catch (error) {
    const durationMs = Date.now() - startTime;

    await logUsageEvent({
      supabase,
      organizationId,
      projectId: pool.project_id,
      jobId: null,
      action: "keyword_grouping",
      model: process.env.OPENAI_MODEL_PRIMARY || "gpt-5.1-nano",
      tokensIn: 0,
      tokensOut: 0,
      tokensTotal: 0,
      durationMs,
      meta: {
        pool_type: pool.pool_type,
        pool_id: poolId,
        keyword_count: pool.cleaned_keywords.length,
        basis: config.basis || "auto",
        error: error instanceof Error ? error.message : String(error),
      },
    });

    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Grouping failed" },
      { status: 500 },
    );
  }
}
