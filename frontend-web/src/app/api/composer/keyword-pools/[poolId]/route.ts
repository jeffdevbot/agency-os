import { NextResponse, type NextRequest } from "next/server";
import type { ComposerKeywordPool } from "@agency/lib/composer/types";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { isUuid, resolveComposerOrgIdFromSession } from "@/lib/composer/serverUtils";

export interface KeywordPoolRow {
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

export const mapRowToPool = (row: KeywordPoolRow): ComposerKeywordPool => ({
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
 * GET /api/composer/keyword-pools/:id
 * Returns a single keyword pool by ID with org verification
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
    return NextResponse.json(
      { error: "Organization not found in session" },
      { status: 403 },
    );
  }

  const { data, error } = await supabase
    .from("composer_keyword_pools")
    .select("*")
    .eq("id", poolId)
    .eq("organization_id", organizationId)
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: "Keyword pool not found" },
      { status: 404 },
    );
  }

  return NextResponse.json({ pool: mapRowToPool(data) });
}

interface UpdateKeywordPoolPayload {
  rawKeywords?: string[];
  cleanedKeywords?: string[];
  removedKeywords?: Array<{ term: string; reason: string }>;
  cleanSettings?: {
    removeColors?: boolean;
    removeSizes?: boolean;
    removeBrandTerms?: boolean;
    removeCompetitorTerms?: boolean;
  };
  groupingConfig?: {
    basis?: "single" | "per_sku" | "attribute" | "custom";
    attributeName?: string;
    groupCount?: number;
    phrasesPerGroup?: number;
  };
  status?: "empty" | "uploaded" | "cleaned" | "grouped";
  cleanedAt?: string | null;
  groupedAt?: string | null;
  approvedAt?: string | null;
  approved?: boolean;
}

/**
 * PATCH /api/composer/keyword-pools/:id
 * Update a keyword pool
 * - Supports updating raw_keywords, status, approval flags
 * - Implements state transition logic (uploading resets approvals)
 */
export async function PATCH(
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

  const payload = (await request.json()) as UpdateKeywordPoolPayload;

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

  // Fetch existing pool to verify ownership and get current state
  const { data: existingPool, error: fetchError } = await supabase
    .from("composer_keyword_pools")
    .select("*")
    .eq("id", poolId)
    .eq("organization_id", organizationId)
    .single();

  if (fetchError || !existingPool) {
    return NextResponse.json(
      { error: "Keyword pool not found" },
      { status: 404 },
    );
  }

  // Build update object
  const updates: Partial<KeywordPoolRow> = {};

  // Handle raw_keywords update - reset approvals if raw keywords change
  if (payload.rawKeywords !== undefined) {
    updates.raw_keywords = payload.rawKeywords;
    updates.status = "uploaded";
    updates.cleaned_at = null;
    updates.grouped_at = null;
    updates.approved_at = null;
    updates.cleaned_keywords = [];
    updates.removed_keywords = [];
  }

  // Handle cleaned_keywords/removed_keywords manual updates
  if (payload.cleanedKeywords !== undefined) {
    updates.cleaned_keywords = payload.cleanedKeywords;
  }

  if (payload.removedKeywords !== undefined) {
    updates.removed_keywords = payload.removedKeywords;
  }

  // Handle clean_settings
  if (payload.cleanSettings !== undefined) {
    updates.clean_settings = payload.cleanSettings;
  }

  // Handle grouping_config
  if (payload.groupingConfig !== undefined) {
    updates.grouping_config = payload.groupingConfig;
    // Reset grouped_at and approved_at when config changes
    updates.grouped_at = null;
    updates.approved_at = null;
  }

  // Handle status transitions
  const targetStatus = payload.status;

  // Handle timestamp updates
  if (payload.cleanedAt !== undefined) {
    updates.cleaned_at = payload.cleanedAt;
  }

  if (payload.groupedAt !== undefined) {
    updates.grouped_at = payload.groupedAt;
  }

  if (payload.approvedAt !== undefined) {
    updates.approved_at = payload.approvedAt;
  }

  // Approval gating: require cleaned keywords and correct state
  const wantsApproval =
    payload.approved === true || targetStatus === "cleaned";
  if (wantsApproval) {
    const effectiveCleaned =
      updates.cleaned_keywords ??
      (existingPool.cleaned_keywords as string[] | null) ??
      [];

    if (!effectiveCleaned || effectiveCleaned.length === 0) {
      return NextResponse.json(
        { error: "cannot_approve_without_cleaned_keywords" },
        { status: 400 },
      );
    }

    if (existingPool.status !== "uploaded") {
      return NextResponse.json(
        { error: "approval_not_allowed_from_state", status: existingPool.status },
        { status: 400 },
      );
    }

    updates.status = "cleaned";
    if (updates.cleaned_at === undefined || updates.cleaned_at === null) {
      updates.cleaned_at = new Date().toISOString();
    }
  } else if (targetStatus !== undefined) {
    updates.status = targetStatus;
  }

  // Perform the update
  const { data, error } = await supabase
    .from("composer_keyword_pools")
    .update(updates)
    .eq("id", poolId)
    .select("*")
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ pool: mapRowToPool(data) });
}
