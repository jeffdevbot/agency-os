import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";

const isUuid = (value: unknown): value is string =>
  typeof value === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);

interface QuestionRow {
  id: string;
  project_id: string;
  sku_id: string;
  question: string;
  source: string | null;
  created_at: string;
}

const mapQuestion = (row: QuestionRow) => ({
  id: row.id,
  projectId: row.project_id,
  skuId: row.sku_id,
  question: row.question,
  source: row.source,
  createdAt: row.created_at,
});

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ projectId?: string }> },
) {
  const { projectId } = await context.params;
  if (!isUuid(projectId)) {
    return NextResponse.json({ error: { code: "validation_error", message: "invalid project id" } }, { status: 400 });
  }

  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Unauthorized" } }, { status: 401 });
  }

  const skuId = new URL(request.url).searchParams.get("skuId");
  let query = supabase
    .from("scribe_customer_questions")
    .select("id, project_id, sku_id, question, source, created_at")
    .eq("project_id", projectId);

  // If valid skuId param is provided, filter by it; otherwise return all questions for project
  if (skuId && isUuid(skuId)) {
    query = query.eq("sku_id", skuId);
  }

  const { data, error } = await query;

  if (error) {
    return NextResponse.json({ error: { code: "server_error", message: error.message } }, { status: 500 });
  }

  return NextResponse.json((data ?? []).map(mapQuestion));
}

interface CreateQuestionPayload {
  question?: string;
  source?: string | null;
  skuId?: string;
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ projectId?: string }> },
) {
  const { projectId } = await context.params;
  if (!isUuid(projectId)) {
    return NextResponse.json({ error: { code: "validation_error", message: "invalid project id" } }, { status: 400 });
  }

  const payload = (await request.json()) as CreateQuestionPayload;
  const question = payload.question?.trim();
  const skuId = payload.skuId?.trim();

  if (!question) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "question is required" } },
      { status: 400 },
    );
  }

  if (!skuId) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "skuId is required" } },
      { status: 400 },
    );
  }

  if (!isUuid(skuId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "invalid skuId" } },
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

  const { data, error } = await supabase
    .from("scribe_customer_questions")
    .insert({
      project_id: projectId,
      sku_id: skuId,
      question,
      source: payload.source ?? null,
    })
    .select("id, project_id, sku_id, question, source, created_at")
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: { code: "server_error", message: error?.message ?? "Unable to add question" } },
      { status: 500 },
    );
  }

  return NextResponse.json(mapQuestion(data));
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ projectId?: string }> },
) {
  const { projectId } = await context.params;
  if (!isUuid(projectId)) {
    return NextResponse.json({ error: { code: "validation_error", message: "invalid project id" } }, { status: 400 });
  }
  const id = new URL(request.url).searchParams.get("id");
  if (!isUuid(id)) {
    return NextResponse.json({ error: { code: "validation_error", message: "invalid question id" } }, { status: 400 });
  }

  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Unauthorized" } }, { status: 401 });
  }

  const { error } = await supabase
    .from("scribe_customer_questions")
    .delete()
    .eq("id", id)
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
