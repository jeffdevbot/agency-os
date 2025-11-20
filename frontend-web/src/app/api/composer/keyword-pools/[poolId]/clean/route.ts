import { NextResponse, type NextRequest } from "next/server";
import type { KeywordCleanSettings } from "@agency/lib/composer/types";
import { cleanKeywords } from "@agency/lib/composer/keywords/cleaning";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { isUuid, resolveComposerOrgIdFromSession } from "@/lib/composer/serverUtils";
import { mapRowToPool, type KeywordPoolRow } from "../route";

interface CleaningPayload {
  config?: KeywordCleanSettings;
}

interface ProjectRow {
  id: string;
  organization_id: string;
  client_name: string | null;
  what_not_to_say: string[] | null;
}

interface VariantRow {
  attributes: Record<string, string | null> | null;
  group_id: string | null;
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

  const payload = (await request.json()) as CleaningPayload;
  const config: KeywordCleanSettings = {
    removeColors: payload.config?.removeColors ?? false,
    removeSizes: payload.config?.removeSizes ?? false,
    removeBrandTerms: payload.config?.removeBrandTerms ?? true,
    removeCompetitorTerms: payload.config?.removeCompetitorTerms ?? true,
  };

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

  // Fetch the pool and verify ownership
  const { data: poolRow, error: poolError } = await supabase
    .from("composer_keyword_pools")
    .select("*")
    .eq("id", poolId)
    .eq("organization_id", organizationId)
    .single();

  if (poolError || !poolRow) {
    return NextResponse.json({ error: "Keyword pool not found" }, { status: 404 });
  }

  // Fetch project context for brand/competitor lists
  const { data: projectRow, error: projectError } = await supabase
    .from("composer_projects")
    .select("id, organization_id, client_name, what_not_to_say")
    .eq("id", poolRow.project_id)
    .eq("organization_id", organizationId)
    .single();

  if (projectError || !projectRow) {
    return NextResponse.json({ error: "Project not found" }, { status: 404 });
  }

  // Fetch variants to derive attribute-driven color/size lexicons
  let variantsQuery = supabase
    .from("composer_sku_variants")
    .select("attributes, group_id")
    .eq("organization_id", organizationId)
    .eq("project_id", poolRow.project_id);

  if (poolRow.group_id) {
    variantsQuery = variantsQuery.eq("group_id", poolRow.group_id);
  }

  const { data: variants, error: variantsError } = await variantsQuery;

  if (variantsError) {
    return NextResponse.json(
      { error: variantsError.message ?? "Unable to load variants" },
      { status: 500 },
    );
  }

  const { cleaned, removed } = cleanKeywords(
    (poolRow as KeywordPoolRow).raw_keywords ?? [],
    config,
    {
      project: {
        clientName: (projectRow as ProjectRow).client_name,
        whatNotToSay: (projectRow as ProjectRow).what_not_to_say ?? [],
      },
      variants: (variants as VariantRow[] | null)?.map((variant) => ({
        attributes: variant.attributes ?? {},
      })),
    },
  );

  const cleanedAt = new Date().toISOString();

  const { data: updatedPool, error: updateError } = await supabase
    .from("composer_keyword_pools")
    .update({
      cleaned_keywords: cleaned,
      removed_keywords: removed,
      clean_settings: config,
      cleaned_at: cleanedAt,
      status: "uploaded",
      // Cleaning invalidates downstream approvals
      grouped_at: null,
      approved_at: null,
    })
    .eq("id", poolId)
    .select("*")
    .single();

  if (updateError || !updatedPool) {
    return NextResponse.json(
      { error: updateError?.message ?? "Unable to save cleaned keywords" },
      { status: 500 },
    );
  }

  return NextResponse.json({
    pool: mapRowToPool(updatedPool as KeywordPoolRow),
    cleaned,
    removed,
    config,
  });
}
