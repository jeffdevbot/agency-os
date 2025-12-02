import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";

const isUuid = (value: unknown): value is string =>
  typeof value === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);

type UpdatableFields =
  | "sku_code"
  | "asin"
  | "product_name"
  | "brand_tone"
  | "target_audience"
  | "words_to_avoid"
  | "supplied_content"
  | "attribute_preferences";

const ALLOWED_FIELDS: UpdatableFields[] = [
  "sku_code",
  "asin",
  "product_name",
  "brand_tone",
  "target_audience",
  "words_to_avoid",
  "supplied_content",
  "attribute_preferences",
];

interface AttributePreferences {
  mode?: "auto" | "overrides";
  rules?: Record<string, { sections: ("title" | "bullets" | "description" | "backend_keywords")[] }>;
}

const VALID_SECTIONS = ["title", "bullets", "description", "backend_keywords"] as const;
const isValidSection = (section: unknown): section is (typeof VALID_SECTIONS)[number] =>
  typeof section === "string" && VALID_SECTIONS.includes(section as (typeof VALID_SECTIONS)[number]);

const validateAttributePreferences = (prefs: unknown): { valid: boolean; error?: string } => {
  if (prefs === null || prefs === undefined) {
    return { valid: true };
  }

  if (typeof prefs !== "object" || Array.isArray(prefs)) {
    return { valid: false, error: "attribute_preferences must be an object" };
  }

  const typed = prefs as Partial<AttributePreferences>;

  if (typed.mode !== undefined && typed.mode !== "auto" && typed.mode !== "overrides") {
    return { valid: false, error: 'mode must be "auto" or "overrides"' };
  }

  if (typed.rules !== undefined) {
    if (typeof typed.rules !== "object" || Array.isArray(typed.rules)) {
      return { valid: false, error: "rules must be an object" };
    }

    for (const [attrName, rule] of Object.entries(typed.rules)) {
      if (!rule || typeof rule !== "object" || !("sections" in rule)) {
        return { valid: false, error: `rule for "${attrName}" must have a sections array` };
      }

      if (!Array.isArray(rule.sections)) {
        return { valid: false, error: `sections for "${attrName}" must be an array` };
      }

      for (const section of rule.sections) {
        if (!isValidSection(section)) {
          return {
            valid: false,
            error: `invalid section "${section}" for "${attrName}". Must be one of: ${VALID_SECTIONS.join(", ")}`,
          };
        }
      }
    }
  }

  return { valid: true };
};

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ projectId?: string; skuId?: string }> },
) {
  const { projectId, skuId } = await context.params;
  if (!isUuid(projectId) || !isUuid(skuId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "invalid ids" } },
      { status: 400 },
    );
  }

  const payload = (await request.json()) as Partial<Record<UpdatableFields, unknown>> & { sortOrder?: number };
  const updates: Record<string, unknown> = {};

  // Validate attribute_preferences if provided
  if (payload.attribute_preferences !== undefined) {
    const validation = validateAttributePreferences(payload.attribute_preferences);
    if (!validation.valid) {
      return NextResponse.json(
        { error: { code: "validation_error", message: validation.error ?? "Invalid attribute_preferences" } },
        { status: 400 },
      );
    }
  }

  for (const key of ALLOWED_FIELDS) {
    if (payload[key] !== undefined) {
      updates[key] = payload[key];
    }
  }
  if (payload.sortOrder !== undefined) {
    updates.sort_order = payload.sortOrder;
  }

  if (Object.keys(updates).length === 0) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "No valid fields provided" } },
      { status: 400 },
    );
  }

  updates.updated_at = new Date().toISOString();

  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Unauthorized" } }, { status: 401 });
  }

  const { data, error } = await supabase
    .from("scribe_skus")
    .update(updates)
    .eq("id", skuId)
    .eq("project_id", projectId)
    .select(
      "id, project_id, sku_code, asin, product_name, brand_tone, target_audience, words_to_avoid, supplied_content, attribute_preferences, sort_order, created_at, updated_at",
    )
    .single();

  if (error || !data) {
    const status = error?.code === "PGRST116" ? 404 : 500;
    return NextResponse.json(
      { error: { code: status === 404 ? "not_found" : "server_error", message: error?.message ?? "Unable to update SKU" } },
      { status },
    );
  }

  return NextResponse.json({
    id: data.id,
    projectId: data.project_id,
    skuCode: data.sku_code,
    asin: data.asin,
    productName: data.product_name,
    brandTone: data.brand_tone,
    targetAudience: data.target_audience,
    wordsToAvoid: data.words_to_avoid ?? [],
    suppliedContent: data.supplied_content,
    attributePreferences: data.attribute_preferences ?? null,
    sortOrder: data.sort_order,
    createdAt: data.created_at,
    updatedAt: data.updated_at,
  });
}

export async function DELETE(
  _request: NextRequest,
  context: { params: Promise<{ projectId?: string; skuId?: string }> },
) {
  const { projectId, skuId } = await context.params;
  if (!isUuid(projectId) || !isUuid(skuId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "invalid ids" } },
      { status: 400 },
    );
  }

  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Unauthorized" } }, { status: 401 });
  }

  const { error } = await supabase
    .from("scribe_skus")
    .delete()
    .eq("id", skuId)
    .eq("project_id", projectId);

  if (error) {
    const status = error.code === "PGRST116" ? 404 : 500;
    return NextResponse.json(
      { error: { code: status === 404 ? "not_found" : "server_error", message: error.message } },
      { status },
    );
  }

  return NextResponse.json({ ok: true });
}
