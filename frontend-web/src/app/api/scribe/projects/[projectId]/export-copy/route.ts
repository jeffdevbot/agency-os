import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";

const isUuid = (value: unknown): value is string =>
  typeof value === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);

const slugify = (value: string) =>
  value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

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

  const { data: project, error: projectError } = await supabase
    .from("scribe_projects")
    .select("id, name, created_by")
    .eq("id", projectId)
    .eq("created_by", session.user.id)
    .single();

  if (projectError || !project) {
    const status = projectError?.code === "PGRST116" ? 404 : 500;
    return NextResponse.json(
      { error: { code: "not_found", message: projectError?.message ?? "Project not found" } },
      { status },
    );
  }

  const { data: skus, error: skusError } = await supabase
    .from("scribe_skus")
    .select("id, sku_code, product_name, asin, sort_order")
    .eq("project_id", projectId)
    .order("sort_order");

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

  const skuIds = skus.map((s) => s.id);

  const { data: variantAttributes, error: variantAttrsError } = await supabase
    .from("scribe_variant_attributes")
    .select("id, name, sort_order")
    .eq("project_id", projectId)
    .order("sort_order");

  if (variantAttrsError) {
    return NextResponse.json(
      { error: { code: "server_error", message: variantAttrsError.message } },
      { status: 500 },
    );
  }

  const { data: variantValues, error: variantValuesError } = await supabase
    .from("scribe_sku_variant_values")
    .select("sku_id, attribute_id, value")
    .in("sku_id", skuIds);

  if (variantValuesError) {
    return NextResponse.json(
      { error: { code: "server_error", message: variantValuesError.message } },
      { status: 500 },
    );
  }

  const { data: generatedContent, error: contentError } = await supabase
    .from("scribe_generated_content")
    .select("sku_id, title, bullets, description, backend_keywords")
    .in("sku_id", skuIds);

  if (contentError) {
    return NextResponse.json(
      { error: { code: "server_error", message: contentError.message } },
      { status: 500 },
    );
  }

  const variantAttrMap = new Map<string, { name: string | null }>();
  (variantAttributes || []).forEach((attr) => {
    variantAttrMap.set(attr.id, { name: attr.name });
  });

  const variantValuesBySku = new Map<string, Map<string, string>>();
  (variantValues || []).forEach((row) => {
    if (!variantValuesBySku.has(row.sku_id)) {
      variantValuesBySku.set(row.sku_id, new Map());
    }
    const name = variantAttrMap.get(row.attribute_id)?.name;
    if (name) {
      variantValuesBySku.get(row.sku_id)!.set(name, row.value || "");
    }
  });

  const contentBySku = new Map<
    string,
    { title: string; bullets: string[]; description: string; backend_keywords: string }
  >();
  (generatedContent || []).forEach((gc) => {
    contentBySku.set(gc.sku_id, {
      title: gc.title || "",
      bullets: Array.isArray(gc.bullets) ? gc.bullets : [],
      description: gc.description || "",
      backend_keywords: gc.backend_keywords || "",
    });
  });

  const variantAttrNames = (variantAttributes || [])
    .filter((attr) => attr.name)
    .map((attr) => attr.name as string);

  const escapeCSV = (value: string | null | undefined): string => {
    if (value === null || value === undefined) return '""';
    const cleaned = String(value).replace(/[\r\n]+/g, " ");
    return `"${cleaned.replace(/"/g, '""')}"`;
  };

  const headers = [
    "SKU",
    "Product Name",
    "ASIN",
    ...variantAttrNames,
    "Product Title",
    "Bullet Point 1",
    "Bullet Point 2",
    "Bullet Point 3",
    "Bullet Point 4",
    "Bullet Point 5",
    "Description",
    "Backend Keywords",
  ];

  const rows: string[] = [headers.map((h) => `"${h.replace(/"/g, '""')}"`).join(",")];

  skus.forEach((sku) => {
    const variantsForSku = variantValuesBySku.get(sku.id) ?? new Map<string, string>();
    const content = contentBySku.get(sku.id);

    const bullets = content?.bullets ?? [];
    const paddedBullets = [
      bullets[0] || "",
      bullets[1] || "",
      bullets[2] || "",
      bullets[3] || "",
      bullets[4] || "",
    ];

    const backendKeywordsRaw = content?.backend_keywords || "";
    const backendKeywordsClean = backendKeywordsRaw
      .replace(/,/g, " ")
      .replace(/\s+/g, " ")
      .trim();

    const row = [
      escapeCSV(sku.sku_code),
      escapeCSV(sku.product_name),
      escapeCSV(sku.asin),
      ...variantAttrNames.map((name) => escapeCSV(variantsForSku.get(name) || "")),
      escapeCSV(content?.title || ""),
      ...paddedBullets.map((b) => escapeCSV(b)),
      escapeCSV(content?.description || ""),
      escapeCSV(backendKeywordsClean),
    ];

    rows.push(row.join(","));
  });

  const BOM = "\uFEFF";
  const csv = BOM + rows.join("\n");
  const projectSlug = slugify(project.name || "project");
  const now = new Date();
  const timestamp = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}-${String(now.getHours()).padStart(2, "0")}${String(now.getMinutes()).padStart(2, "0")}`;
  const filename = `scribe_${projectSlug}_amazon_content_${timestamp}.csv`;

  return new NextResponse(csv, {
    status: 200,
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="${filename}"`,
    },
  });
}
