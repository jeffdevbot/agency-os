import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";

const isUuid = (value: unknown): value is string =>
  typeof value === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);

interface UpdateGeneratedContentPayload {
  title?: string;
  bullets?: string[]; // Must be exactly 5 if provided
  description?: string;
  backend_keywords?: string;
}

// Amazon listing limits
const TITLE_MAX_LENGTH = 200;
const BULLET_MAX_LENGTH = 500;
const DESCRIPTION_MAX_LENGTH = 2000;
const BACKEND_KEYWORDS_MAX_BYTES = 249;

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ projectId?: string; skuId?: string }> },
) {
  const { projectId, skuId } = await context.params;

  if (!isUuid(projectId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "invalid project id" } },
      { status: 400 },
    );
  }

  if (!isUuid(skuId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "invalid sku id" } },
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

  // Fetch project and verify ownership
  const { data: project, error: fetchError } = await supabase
    .from("scribe_projects")
    .select("id, status, created_by")
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

  // Note: Reading is allowed for archived projects (read-only OK)

  // Fetch generated content for this SKU
  const { data: content, error: contentError } = await supabase
    .from("scribe_generated_content")
    .select(
      "id, project_id, sku_id, version, title, bullets, description, backend_keywords, model_used, prompt_version, approved, approved_at, created_at, updated_at",
    )
    .eq("sku_id", skuId)
    .single();

  if (contentError) {
    if (contentError.code === "PGRST116") {
      return NextResponse.json(
        { error: { code: "not_found", message: "Generated content not found" } },
        { status: 404 },
      );
    }
    return NextResponse.json(
      { error: { code: "server_error", message: contentError.message } },
      { status: 500 },
    );
  }

  return NextResponse.json({
    id: content.id,
    projectId: content.project_id,
    skuId: content.sku_id,
    version: content.version,
    title: content.title,
    bullets: content.bullets,
    description: content.description,
    backendKeywords: content.backend_keywords,
    modelUsed: content.model_used,
    promptVersion: content.prompt_version,
    approved: content.approved,
    approvedAt: content.approved_at,
    createdAt: content.created_at,
    updatedAt: content.updated_at,
  });
}

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ projectId?: string; skuId?: string }> },
) {
  const { projectId, skuId } = await context.params;

  if (!isUuid(projectId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "invalid project id" } },
      { status: 400 },
    );
  }

  if (!isUuid(skuId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "invalid sku id" } },
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

  // Parse request body
  const body = (await request.json()) as UpdateGeneratedContentPayload;
  const { title, bullets, description, backend_keywords } = body;

  // Validate limits
  if (title !== undefined && title.length > TITLE_MAX_LENGTH) {
    return NextResponse.json(
      {
        error: {
          code: "validation_error",
          message: `Title must not exceed ${TITLE_MAX_LENGTH} characters`,
        },
      },
      { status: 400 },
    );
  }

  if (bullets !== undefined) {
    if (bullets.length !== 5) {
      return NextResponse.json(
        {
          error: {
            code: "validation_error",
            message: "Bullets must be exactly 5 items",
          },
        },
        { status: 400 },
      );
    }

    for (let i = 0; i < bullets.length; i++) {
      if (bullets[i].length > BULLET_MAX_LENGTH) {
        return NextResponse.json(
          {
            error: {
              code: "validation_error",
              message: `Bullet ${i + 1} must not exceed ${BULLET_MAX_LENGTH} characters`,
            },
          },
          { status: 400 },
        );
      }
    }
  }

  if (description !== undefined && description.length > DESCRIPTION_MAX_LENGTH) {
    return NextResponse.json(
      {
        error: {
          code: "validation_error",
          message: `Description must not exceed ${DESCRIPTION_MAX_LENGTH} characters`,
        },
      },
      { status: 400 },
    );
  }

  if (backend_keywords !== undefined) {
    const byteLength = new TextEncoder().encode(backend_keywords).length;
    if (byteLength > BACKEND_KEYWORDS_MAX_BYTES) {
      return NextResponse.json(
        {
          error: {
            code: "validation_error",
            message: `Backend keywords must not exceed ${BACKEND_KEYWORDS_MAX_BYTES} bytes (currently ${byteLength} bytes)`,
          },
        },
        { status: 400 },
      );
    }
  }

  // Fetch project and verify ownership
  const { data: project, error: fetchError } = await supabase
    .from("scribe_projects")
    .select("id, status, created_by")
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

  // Only prevent editing on archived projects
  if (project.status === "archived") {
    return NextResponse.json(
      { error: { code: "forbidden", message: "Archived projects are read-only" } },
      { status: 403 },
    );
  }

  // Verify SKU belongs to project
  const { data: sku, error: skuError } = await supabase
    .from("scribe_skus")
    .select("id")
    .eq("id", skuId)
    .eq("project_id", projectId)
    .single();

  if (skuError || !sku) {
    return NextResponse.json(
      { error: { code: "not_found", message: "SKU not found" } },
      { status: 404 },
    );
  }

  // Gate: require exactly 5 selected topics
  const { count, error: countError } = await supabase
    .from("scribe_topics")
    .select("*", { count: "exact", head: true })
    .eq("sku_id", skuId)
    .eq("selected", true);

  if (countError) {
    return NextResponse.json(
      { error: { code: "server_error", message: countError.message } },
      { status: 500 },
    );
  }

  if ((count ?? 0) !== 5) {
    return NextResponse.json(
      {
        error: {
          code: "validation_error",
          message: "SKU must have exactly 5 selected topics before editing generated content",
        },
      },
      { status: 400 },
    );
  }

  // Fetch existing content
  const { data: existingContent, error: contentError } = await supabase
    .from("scribe_generated_content")
    .select("*")
    .eq("sku_id", skuId)
    .single();

  if (contentError && contentError.code !== "PGRST116") {
    return NextResponse.json(
      { error: { code: "server_error", message: contentError.message } },
      { status: 500 },
    );
  }

  // Build update payload; always include project/sku to satisfy RLS and NOT NULL columns
  const upsertData: {
    project_id: string;
    sku_id: string;
    title?: string;
    bullets?: string[];
    description?: string;
    backend_keywords?: string;
    version: number;
    updated_at: string;
  } = {
    project_id: projectId,
    sku_id: skuId,
    version: existingContent ? (existingContent.version || 1) + 1 : 1,
    updated_at: new Date().toISOString(),
  };

  if (title !== undefined) upsertData.title = title;
  if (bullets !== undefined) upsertData.bullets = bullets;
  if (description !== undefined) upsertData.description = description;
  if (backend_keywords !== undefined) upsertData.backend_keywords = backend_keywords;

  const { data, error } = await supabase
    .from("scribe_generated_content")
    .upsert(upsertData, { onConflict: "sku_id" })
    .select("id, version, title, bullets, description, backend_keywords, updated_at")
    .single();

  if (error || !data) {
    return NextResponse.json(
      {
        error: { code: "server_error", message: error?.message ?? "Failed to update content" },
      },
      { status: 500 },
    );
  }

  return NextResponse.json({
    id: data.id,
    version: data.version,
    title: data.title,
    bullets: data.bullets,
    description: data.description,
    backendKeywords: data.backend_keywords,
    updatedAt: data.updated_at,
  });
}
