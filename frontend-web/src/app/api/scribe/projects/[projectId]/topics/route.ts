import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";

const isUuid = (value: unknown): value is string =>
  typeof value === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);

interface TopicRow {
  id: string;
  project_id: string;
  sku_id: string;
  topic_index: number;
  title: string;
  description: string | null;
  generated_by: string | null;
  selected: boolean;
  created_at: string;
  updated_at: string;
}

const mapTopicRow = (row: TopicRow) => ({
  id: row.id,
  projectId: row.project_id,
  skuId: row.sku_id,
  topicIndex: row.topic_index,
  title: row.title,
  description: row.description,
  generatedBy: row.generated_by,
  selected: row.selected,
  createdAt: row.created_at,
  updatedAt: row.updated_at,
});

export async function GET(
  request: NextRequest,
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
    return NextResponse.json({ error: { code: "unauthorized", message: "Unauthorized" } }, { status: 401 });
  }

  // Verify project ownership
  const { data: project, error: fetchError } = await supabase
    .from("scribe_projects")
    .select("id, created_by")
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

  // Get optional skuId filter from query params
  const { searchParams } = new URL(request.url);
  const skuId = searchParams.get("skuId");

  if (skuId && !isUuid(skuId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "invalid SKU ID" } },
      { status: 400 },
    );
  }

  // Build query
  let query = supabase
    .from("scribe_topics")
    .select("*")
    .eq("project_id", projectId)
    .order("topic_index", { ascending: true });

  if (skuId) {
    query = query.eq("sku_id", skuId);
  }

  const { data, error } = await query;

  if (error) {
    return NextResponse.json(
      { error: { code: "server_error", message: error.message } },
      { status: 500 },
    );
  }

  return NextResponse.json((data as TopicRow[]).map(mapTopicRow));
}
