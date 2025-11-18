import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";
import { createRouteHandlerClient } from "@supabase/auth-helpers-nextjs";
import type { Session } from "@supabase/supabase-js";
import type { ComposerSkuVariant } from "@agency/lib/composer/types";
import { DEFAULT_COMPOSER_ORG_ID } from "@/lib/composer/constants";

const VARIANT_COLUMNS =
  "id, organization_id, project_id, group_id, sku, asin, parent_sku, attributes, notes, created_at";

interface VariantRow {
  id: string;
  organization_id: string;
  project_id: string;
  group_id: string | null;
  sku: string;
  asin: string | null;
  parent_sku: string | null;
  attributes: Record<string, string | null> | null;
  notes: string | null;
  created_at: string;
}

interface SkuVariantInput {
  id?: string;
  sku: string;
  asin?: string | null;
  parentSku?: string | null;
  attributes?: Record<string, string | null>;
  notes?: string | null;
}

const mapRowToComposerVariant = (row: VariantRow): ComposerSkuVariant => ({
  id: row.id,
  organizationId: row.organization_id,
  projectId: row.project_id,
  groupId: row.group_id,
  sku: row.sku,
  asin: row.asin === "" ? null : row.asin,
  parentSku: row.parent_sku,
  attributes: row.attributes ?? {},
  notes: row.notes,
  createdAt: row.created_at,
});

const isUuid = (value: string | undefined): value is string => {
  return typeof value === "string" && /^[0-9a-fA-F-]{36}$/.test(value);
};

const resolveComposerOrgIdFromSession = (session: Session | null): string => {
  const userRecord = session?.user as Record<string, unknown> | undefined;
  const directField = userRecord?.org_id;
  if (typeof directField === "string" && directField.length > 0) {
    return directField;
  }
  const metadataOrgId =
    (session?.user?.app_metadata?.org_id as string | undefined) ??
    (session?.user?.user_metadata?.org_id as string | undefined) ??
    (session?.user?.app_metadata?.organization_id as string | undefined) ??
    (session?.user?.user_metadata?.organization_id as string | undefined);
  if (metadataOrgId && metadataOrgId.length > 0) {
    return metadataOrgId;
  }
  return DEFAULT_COMPOSER_ORG_ID;
};

const sanitizeVariantInput = (input: SkuVariantInput) => {
  const sku = input.sku?.trim();
  const asin = input.asin?.trim();
  if (!sku) {
    throw new Error("sku_required");
  }
  const parentSku =
    input.parentSku == null ? null : input.parentSku.toString().trim() || null;
  const attributes = input.attributes ?? {};
  const normalizedAttributes = Object.entries(attributes).reduce<Record<string, string | null>>(
    (acc, [key, value]) => {
      if (!key) return acc;
      const trimmedKey = key.trim();
      if (!trimmedKey) return acc;
      const trimmedValue =
        value == null
          ? null
          : typeof value === "string"
            ? value.trim() || null
            : String(value);
      acc[trimmedKey] = trimmedValue;
      return acc;
    },
    {},
  );
  return {
    id: input.id,
    sku,
    asin: asin || null,
    parentSku,
    attributes: normalizedAttributes,
    notes: input.notes ?? null,
  };
};

const getSupabaseClient = async () => {
  const cookieStore = cookies();
  return createRouteHandlerClient({
    cookies: () => cookieStore,
  });
};

const fetchVariantsForProject = async (supabase: ReturnType<typeof createRouteHandlerClient>, projectId: string, organizationId: string) => {
  const { data, error } = await supabase
    .from("composer_sku_variants")
    .select(VARIANT_COLUMNS)
    .eq("organization_id", organizationId)
    .eq("project_id", projectId)
    .order("created_at", { ascending: true });

  if (error) {
    throw new Error(error.message);
  }
  return (data ?? []).map(mapRowToComposerVariant);
};

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ projectId?: string }> },
) {
  const { projectId } = await context.params;
  if (!isUuid(projectId)) {
    return NextResponse.json({ error: "invalid_project_id" }, { status: 400 });
  }

  const supabase = await getSupabaseClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const organizationId = resolveComposerOrgIdFromSession(session);

  try {
    const variants = await fetchVariantsForProject(supabase, projectId, organizationId);
    return NextResponse.json({ variants });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unable to load variants" },
      { status: 500 },
    );
  }
}

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ projectId?: string }> },
) {
  const { projectId } = await context.params;
  if (!isUuid(projectId)) {
    return NextResponse.json({ error: "invalid_project_id" }, { status: 400 });
  }

  const body = (await request.json()) as { variants?: SkuVariantInput[] };
  if (!Array.isArray(body.variants)) {
    return NextResponse.json({ error: "variants array required" }, { status: 400 });
  }

  let sanitized: ReturnType<typeof sanitizeVariantInput>[] = [];
  try {
    sanitized = body.variants.map(sanitizeVariantInput);
  } catch (error) {
    if (error instanceof Error && error.message === "sku_required") {
      return NextResponse.json({ error: "Each variant requires sku" }, { status: 400 });
    }
    return NextResponse.json({ error: "Invalid variant payload" }, { status: 400 });
  }

  const duplicateSkus = new Set<string>();
  const seen = new Set<string>();
  for (const variant of sanitized) {
    const key = variant.sku.toLowerCase();
    if (seen.has(key)) {
      duplicateSkus.add(variant.sku);
    }
    seen.add(key);
  }
  if (duplicateSkus.size > 0) {
    return NextResponse.json(
      {
        error: `Duplicate SKU values in payload: ${Array.from(duplicateSkus).join(", ")}`,
      },
      { status: 400 },
    );
  }

  const supabase = await getSupabaseClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const organizationId = resolveComposerOrgIdFromSession(session);

  if (sanitized.length === 0) {
    const { error: deleteError } = await supabase
      .from("composer_sku_variants")
      .delete()
      .eq("organization_id", organizationId)
      .eq("project_id", projectId);
    if (deleteError) {
      return NextResponse.json({ error: deleteError.message }, { status: 500 });
    }
    return NextResponse.json({ variants: [] });
  }

  const incomingSkus = sanitized.map((variant) => variant.sku);
  const { data: existingRows, error: existingError } = await supabase
    .from("composer_sku_variants")
    .select("id, sku")
    .eq("organization_id", organizationId)
    .eq("project_id", projectId)
    .in("sku", incomingSkus);

  if (existingError) {
    return NextResponse.json({ error: existingError.message }, { status: 500 });
  }

  const conflicts =
    existingRows?.filter((row) => {
      const incoming = sanitized.find((variant) => variant.sku === row.sku);
      if (!incoming) return false;
      if (!incoming.id) return true;
      return incoming.id !== row.id;
    }) ?? [];

  if (conflicts.length > 0) {
    return NextResponse.json(
      {
        error: `SKU already exists: ${conflicts.map((row) => row.sku).join(", ")}`,
      },
      { status: 409 },
    );
  }

  const toUpdate = sanitized.filter((variant) => variant.id);
  const toInsert = sanitized.filter((variant) => !variant.id);

  if (toUpdate.length > 0) {
    const updatePayload = toUpdate.map((variant) => ({
      id: variant.id,
      organization_id: organizationId,
      project_id: projectId,
      group_id: null,
      sku: variant.sku,
      asin: variant.asin ?? "",
      parent_sku: variant.parentSku,
      attributes: variant.attributes,
      notes: variant.notes ?? null,
    }));
    const { error: updateError } = await supabase
      .from("composer_sku_variants")
      .upsert(updatePayload, { onConflict: "id" });
    if (updateError) {
      return NextResponse.json({ error: updateError.message }, { status: 500 });
    }
  }

  if (toInsert.length > 0) {
    const insertPayload = toInsert.map((variant) => ({
      organization_id: organizationId,
      project_id: projectId,
      group_id: null,
      sku: variant.sku,
      asin: variant.asin ?? "",
      parent_sku: variant.parentSku,
      attributes: variant.attributes,
      notes: variant.notes ?? null,
    }));
    const { error: insertError } = await supabase
      .from("composer_sku_variants")
      .insert(insertPayload);
    if (insertError) {
      return NextResponse.json({ error: insertError.message }, { status: 500 });
    }
  }

  try {
    const variants = await fetchVariantsForProject(supabase, projectId, organizationId);
    return NextResponse.json({ variants });
  } catch (fetchError) {
    return NextResponse.json(
      { error: fetchError instanceof Error ? fetchError.message : "Unable to load variants" },
      { status: 500 },
    );
  }
}
