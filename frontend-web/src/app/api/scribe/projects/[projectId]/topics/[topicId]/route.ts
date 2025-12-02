import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";

const isUuid = (value: unknown): value is string =>
  typeof value === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);

interface UpdateTopicPayload {
  title?: string;
  description?: string;
  topicIndex?: number;
  approved?: boolean;
}

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ projectId?: string; topicId?: string }> },
) {
  const { projectId, topicId } = await context.params;

  if (!isUuid(projectId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "invalid project id" } },
      { status: 400 },
    );
  }

  if (!isUuid(topicId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "invalid topic id" } },
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

  // Parse request body
  let payload: UpdateTopicPayload;
  try {
    payload = (await request.json()) as UpdateTopicPayload;
  } catch {
    return NextResponse.json(
      { error: { code: "validation_error", message: "Invalid request body" } },
      { status: 400 },
    );
  }

  // Verify project ownership
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

  if (project.status === "archived") {
    return NextResponse.json(
      { error: { code: "forbidden", message: "Archived projects are read-only" } },
      { status: 403 },
    );
  }

  // Fetch existing topic
  const { data: existingTopic, error: topicFetchError } = await supabase
    .from("scribe_topics")
    .select("id, project_id, sku_id, approved")
    .eq("id", topicId)
    .eq("project_id", projectId)
    .single();

  if (topicFetchError || !existingTopic) {
    const status = topicFetchError?.code === "PGRST116" ? 404 : 500;
    return NextResponse.json(
      { error: { code: "not_found", message: topicFetchError?.message ?? "Topic not found" } },
      { status },
    );
  }

  // If approving a topic, check that SKU doesn't already have 5 approved topics
  if (payload.approved === true && !existingTopic.approved) {
    const { count, error: countError } = await supabase
      .from("scribe_topics")
      .select("*", { count: "exact", head: true })
      .eq("sku_id", existingTopic.sku_id)
      .eq("approved", true);

    if (countError) {
      return NextResponse.json(
        { error: { code: "server_error", message: countError.message } },
        { status: 500 },
      );
    }

    if ((count ?? 0) >= 5) {
      return NextResponse.json(
        { error: { code: "validation_error", message: "SKU already has 5 approved topics" } },
        { status: 400 },
      );
    }
  }

  // Build update object
  const updates: Record<string, unknown> = { updated_at: new Date().toISOString() };

  if (payload.title !== undefined) updates.title = payload.title.trim();
  if (payload.description !== undefined) updates.description = payload.description?.trim() || null;
  if (payload.topicIndex !== undefined) updates.topic_index = payload.topicIndex;
  if (payload.approved !== undefined) {
    updates.approved = payload.approved;
    updates.approved_at = payload.approved ? new Date().toISOString() : null;
  }

  // Update topic
  const { data, error } = await supabase
    .from("scribe_topics")
    .update(updates)
    .eq("id", topicId)
    .eq("project_id", projectId)
    .select("*")
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: { code: "server_error", message: error?.message ?? "Failed to update topic" } },
      { status: 500 },
    );
  }

  return NextResponse.json({
    id: data.id,
    projectId: data.project_id,
    skuId: data.sku_id,
    topicIndex: data.topic_index,
    title: data.title,
    description: data.description,
    generatedBy: data.generated_by,
    approved: data.approved,
    approvedAt: data.approved_at,
    createdAt: data.created_at,
    updatedAt: data.updated_at,
  });
}
