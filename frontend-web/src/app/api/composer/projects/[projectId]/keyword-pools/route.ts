import { NextResponse, type NextRequest } from "next/server";
import type { ComposerKeywordPool } from "@agency/lib/composer/types";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { isUuid, resolveComposerOrgIdFromSession } from "@/lib/composer/serverUtils";
import {
  dedupeKeywords,
  mergeKeywords,
  validateKeywordCount,
} from "@agency/lib/composer/keywords/utils";

interface KeywordPoolRow {
  id: string;
  organization_id: string;
  project_id: string;
  group_id: string | null;
  pool_type: string;
  status: string;
  raw_keywords: string[];
  raw_keywords_url: string | null;
  cleaned_keywords: string[];
  removed_keywords: Array<{ term: string; reason: string }>;
  clean_settings: {
    removeColors?: boolean;
    removeSizes?: boolean;
    removeBrandTerms?: boolean;
    removeCompetitorTerms?: boolean;
  };
  grouping_config: {
    basis?: string;
    attributeName?: string;
    groupCount?: number;
    phrasesPerGroup?: number;
  };
  cleaned_at: string | null;
  grouped_at: string | null;
  approved_at: string | null;
  created_at: string;
}

const mapRowToPool = (row: KeywordPoolRow): ComposerKeywordPool => ({
  id: row.id,
  organizationId: row.organization_id,
  projectId: row.project_id,
  groupId: row.group_id,
  poolType: row.pool_type as "body" | "titles",
  status: row.status as "empty" | "uploaded" | "cleaned" | "grouped",
  rawKeywords: row.raw_keywords,
  rawKeywordsUrl: row.raw_keywords_url,
  cleanedKeywords: row.cleaned_keywords,
  removedKeywords: row.removed_keywords,
  cleanSettings: row.clean_settings,
  groupingConfig: row.grouping_config,
  cleanedAt: row.cleaned_at,
  groupedAt: row.grouped_at,
  approvedAt: row.approved_at,
  createdAt: row.created_at,
});

/**
 * GET /api/composer/projects/:id/keyword-pools
 * Returns all keyword pools for a project (filtered by group_id if provided)
 */
export async function GET(
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

  // Optional: filter by group_id if provided
  const { searchParams } = new URL(request.url);
  const groupId = searchParams.get("groupId");

  let query = supabase
    .from("composer_keyword_pools")
    .select("*")
    .eq("project_id", projectId)
    .eq("organization_id", organizationId);

  if (groupId) {
    if (!isUuid(groupId)) {
      return NextResponse.json(
        { error: "invalid_group_id", groupId },
        { status: 400 },
      );
    }
    query = query.eq("group_id", groupId);
  }

  const { data, error } = await query.order("created_at", { ascending: true });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const pools = (data ?? []).map(mapRowToPool);
  return NextResponse.json({ pools });
}

interface CreateKeywordPoolPayload {
  poolType: "body" | "titles";
  groupId?: string | null;
  keywords: string[];
}

/**
 * POST /api/composer/projects/:id/keyword-pools
 * Create or update a keyword pool by uploading keywords.
 * - Merges with existing raw_keywords if pool exists
 * - Deduplicates keywords (case-insensitive)
 * - Resets cleaning/grouping approvals when uploading
 * - Validates min 5, max 5000 keywords
 */
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

  const payload = (await request.json()) as CreateKeywordPoolPayload;

  // Validate payload
  if (!payload.poolType || !["body", "titles"].includes(payload.poolType)) {
    return NextResponse.json(
      { error: "poolType must be 'body' or 'titles'" },
      { status: 400 },
    );
  }

  if (!Array.isArray(payload.keywords)) {
    return NextResponse.json(
      { error: "keywords must be an array" },
      { status: 400 },
    );
  }

  // Dedupe incoming keywords
  const incomingKeywords = dedupeKeywords(payload.keywords);

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

  // If groupId provided, verify it exists and belongs to this project
  if (payload.groupId) {
    if (!isUuid(payload.groupId)) {
      return NextResponse.json(
        { error: "invalid_group_id", groupId: payload.groupId },
        { status: 400 },
      );
    }

    const { data: group, error: groupError } = await supabase
      .from("composer_sku_groups")
      .select("id")
      .eq("id", payload.groupId)
      .eq("project_id", projectId)
      .eq("organization_id", organizationId)
      .single();

    if (groupError || !group) {
      return NextResponse.json({ error: "Group not found" }, { status: 404 });
    }
  }

  // Check if pool already exists for this project/groupId/poolType combination
  let query = supabase
    .from("composer_keyword_pools")
    .select("*")
    .eq("project_id", projectId)
    .eq("organization_id", organizationId)
    .eq("pool_type", payload.poolType);

  if (payload.groupId) {
    query = query.eq("group_id", payload.groupId);
  } else {
    query = query.is("group_id", null);
  }

  const { data: existingPools } = await query.single();

  let finalKeywords: string[];

  if (existingPools) {
    // Merge with existing keywords
    const existingKeywords = existingPools.raw_keywords as string[];
    finalKeywords = mergeKeywords(existingKeywords, incomingKeywords);
  } else {
    // New pool - use incoming keywords
    finalKeywords = incomingKeywords;
  }

  // Validate keyword count
  const validation = validateKeywordCount(finalKeywords);
  if (!validation.valid) {
    return NextResponse.json(
      { error: validation.error, count: finalKeywords.length },
      { status: 400 },
    );
  }

  if (existingPools) {
    // Update existing pool - merge keywords and reset approvals
    const { data, error } = await supabase
      .from("composer_keyword_pools")
      .update({
        raw_keywords: finalKeywords,
        status: "uploaded",
        // Reset approvals when uploading new keywords
        cleaned_at: null,
        grouped_at: null,
        approved_at: null,
        // Reset cleaned/removed keywords since raw changed
        cleaned_keywords: [],
        removed_keywords: [],
      })
      .eq("id", existingPools.id)
      .select("*")
      .single();

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json({
      pool: mapRowToPool(data),
      merged: true,
      warning: validation.warning,
    });
  } else {
    // Create new pool
    const { data, error } = await supabase
      .from("composer_keyword_pools")
      .insert({
        organization_id: organizationId,
        project_id: projectId,
        group_id: payload.groupId || null,
        pool_type: payload.poolType,
        status: "uploaded",
        raw_keywords: finalKeywords,
      })
      .select("*")
      .single();

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json(
      {
        pool: mapRowToPool(data),
        merged: false,
        warning: validation.warning,
      },
      { status: 201 },
    );
  }
}
