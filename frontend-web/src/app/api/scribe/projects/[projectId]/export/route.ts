import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";

const isUuid = (value: unknown): value is string =>
  typeof value === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);

type VariantValueRow = {
  attribute_id: string;
  value: string | null;
  // Supabase can return either a single object or a 1-element array for the FK relation
  scribe_variant_attributes: { name: string | null } | { name: string | null }[] | null;
};

/**
 * CSV Export for Scribe Project
 *
 * Exports project data including:
 * - Stage A: SKU details, brand tone, target audience, supplied content
 * - Stage B: Keywords, questions, variant attributes
 * - Stage C: title, bullet_1..bullet_5, description, backend_keywords
 *
 * Allows export for archived projects (read-only).
 */
export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ projectId?: string }> },
) {
  const { projectId } = await context.params;

  if (!isUuid(projectId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "invalid project id" } },
      { status: 400 },
    );
  }

  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json(
      { error: { code: "unauthorized", message: "Unauthorized" } },
      { status: 401 },
    );
  }

  // Fetch project and verify ownership (allow archived)
  const { data: project, error: fetchError } = await supabase
    .from("scribe_projects")
    .select("id, name, created_by")
    .eq("id", projectId)
    .eq("created_by", session.user.id)
    .single();

  if (fetchError || !project) {
    const status = fetchError?.code === "PGRST116" ? 404 : 500;
    return NextResponse.json(
      { error: { code: "not_found", message: fetchError?.message ?? "Project not found" } },
      { status },
    );
  }

  // Fetch all SKUs with variant values
  const { data: skus, error: skusError } = await supabase
    .from("scribe_skus")
    .select(
      `
      id,
      sku_code,
      asin,
      product_name,
      brand_tone,
      target_audience,
      supplied_content,
      words_to_avoid,
      scribe_sku_variant_values (
        attribute_id,
        value,
        scribe_variant_attributes (
          name
        )
      )
    `,
    )
    .eq("project_id", projectId)
    .order("sku_code");

  if (skusError) {
    return NextResponse.json(
      { error: { code: "server_error", message: skusError.message } },
      { status: 500 },
    );
  }

  if (!skus || skus.length === 0) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "No SKUs found in project" } },
      { status: 400 },
    );
  }

  // Fetch keywords (grouped by SKU)
  const { data: keywords } = await supabase
    .from("scribe_keywords")
    .select("sku_id, keyword")
    .in(
      "sku_id",
      skus.map((s) => s.id),
    )
    .order("keyword");

  // Fetch questions (grouped by SKU)
  const { data: questions } = await supabase
    .from("scribe_customer_questions")
    .select("sku_id, question")
    .in(
      "sku_id",
      skus.map((s) => s.id),
    )
    .order("question");

  // Fetch generated content (Stage C)
  const { data: generatedContent } = await supabase
    .from("scribe_generated_content")
    .select("sku_id, title, bullets, description, backend_keywords")
    .in(
      "sku_id",
      skus.map((s) => s.id),
    );

  // Build maps for quick lookup
  const keywordsBySku = new Map<string, string[]>();
  keywords?.forEach((kw) => {
    if (!keywordsBySku.has(kw.sku_id)) {
      keywordsBySku.set(kw.sku_id, []);
    }
    keywordsBySku.get(kw.sku_id)!.push(kw.keyword);
  });

  const questionsBySku = new Map<string, string[]>();
  questions?.forEach((q) => {
    if (!questionsBySku.has(q.sku_id)) {
      questionsBySku.set(q.sku_id, []);
    }
    questionsBySku.get(q.sku_id)!.push(q.question);
  });

  const contentBySku = new Map<
    string,
    { title: string; bullets: string[]; description: string; backend_keywords: string }
  >();
  generatedContent?.forEach((gc) => {
    contentBySku.set(gc.sku_id, {
      title: gc.title || "",
      bullets: gc.bullets || [],
      description: gc.description || "",
      backend_keywords: gc.backend_keywords || "",
    });
  });

  // Determine all variant attribute names (for dynamic columns)
  const variantAttrNamesSet = new Set<string>();
  skus.forEach((sku) => {
    const variants = (sku.scribe_sku_variant_values as VariantValueRow[] | null) ?? [];
    variants.forEach((vv) => {
      const attrRelation = vv.scribe_variant_attributes;
      const attrName = Array.isArray(attrRelation) ? attrRelation[0]?.name : attrRelation?.name;
      if (attrName) {
        variantAttrNamesSet.add(attrName);
      }
    });
  });
  const variantAttrNames = Array.from(variantAttrNamesSet).sort();

  // CSV helper: always quote and escape, strip newlines for Excel compatibility
  const escapeCSV = (value: string | null | undefined): string => {
    if (value === null || value === undefined) return '""';
    const str = String(value).replace(/[\r\n]+/g, ' '); // Replace newlines with spaces
    return `"${str.replace(/"/g, '""')}"`;
  };

  // Build CSV
  // Header order: base Stage A fields, dynamic attributes, then remaining A/B/C fields
  const headers = [
    "sku_code",
    "asin",
    "product_name",
    "brand_tone",
    "target_audience",
    "supplied_content",
    ...variantAttrNames,
    "words_to_avoid",
    "keywords",
    "questions",
    "title",
    "bullet_1",
    "bullet_2",
    "bullet_3",
    "bullet_4",
    "bullet_5",
    "description",
    "backend_keywords",
  ];

  const escapeHeader = (h: string) => `"${h.replace(/"/g, '""')}"`;
  const rows: string[] = [headers.map(escapeHeader).join(",")];

  skus.forEach((sku) => {
    // Build variant values map
    const variantValues = new Map<string, string>();
    const variants = (sku.scribe_sku_variant_values as VariantValueRow[] | null) ?? [];
    variants.forEach((vv) => {
      const attrRelation = vv.scribe_variant_attributes;
      const attrName = Array.isArray(attrRelation) ? attrRelation[0]?.name : attrRelation?.name;
      if (attrName) {
        variantValues.set(attrName, vv.value || "");
      }
    });

    // Stage A/B fields
    const skuKeywords = keywordsBySku.get(sku.id) || [];
    const skuQuestions = questionsBySku.get(sku.id) || [];
    const wordsToAvoid = sku.words_to_avoid || [];

    // Stage C fields
    const content = contentBySku.get(sku.id);
    const title = content?.title || "";
    const bullets = content?.bullets || [];
    const bullet_1 = bullets[0] || "";
    const bullet_2 = bullets[1] || "";
    const bullet_3 = bullets[2] || "";
    const bullet_4 = bullets[3] || "";
    const bullet_5 = bullets[4] || "";
    const description = content?.description || "";
    const backendKeywords = content?.backend_keywords || "";

    const row = [
      escapeCSV(sku.sku_code), // sku_code
      escapeCSV(sku.asin), // asin
      escapeCSV(sku.product_name), // product_name
      escapeCSV(sku.brand_tone), // brand_tone
      escapeCSV(sku.target_audience), // target_audience
      escapeCSV(sku.supplied_content), // supplied_content
      ...variantAttrNames.map((attrName) => escapeCSV(variantValues.get(attrName) || "")), // dynamic attrs
      escapeCSV(wordsToAvoid.join("|")), // words_to_avoid
      escapeCSV(skuKeywords.join("|")), // keywords
      escapeCSV(skuQuestions.join("|")), // questions
      escapeCSV(title),
      escapeCSV(bullet_1),
      escapeCSV(bullet_2),
      escapeCSV(bullet_3),
      escapeCSV(bullet_4),
      escapeCSV(bullet_5),
      escapeCSV(description),
      escapeCSV(backendKeywords),
    ];

    rows.push(row.join(","));
  });

  const BOM = '\uFEFF'; // UTF-8 BOM for Excel compatibility
  const csv = BOM + rows.join("\n");
  const filename = `${project.name.replace(/[^a-z0-9]/gi, "_")}_export.csv`;

  return new NextResponse(csv, {
    status: 200,
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="${filename}"`,
    },
  });
}
