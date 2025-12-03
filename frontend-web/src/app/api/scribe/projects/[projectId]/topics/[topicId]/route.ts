import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";

const isUuid = (value: unknown): value is string =>
  typeof value === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);

interface UpdateTopicPayload {
  selected?: boolean;
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
    return NextResponse.json(
      { error: { code: "unauthorized", message: "Unauthorized" } },
      { status: 401 },
    );
  }

  // Parse request body
  const body = (await request.json()) as UpdateTopicPayload;
  const { selected } = body;

  if (typeof selected !== "boolean") {
    return NextResponse.json(
      { error: { code: "validation_error", message: "selected must be a boolean" } },
      { status: 400 },
    );
  }

  // Verify project ownership and get topic
  const { data: project, error: projectError } = await supabase
    .from("scribe_projects")
    .select("id, created_by")
    .eq("id", projectId)
    .eq("created_by", session.user.id)
    .single();

  if (projectError || !project) {
    return NextResponse.json(
      { error: { code: "not_found", message: "Project not found" } },
      { status: 404 },
    );
  }

  // Get the topic and verify it belongs to this project
  const { data: topic, error: topicError } = await supabase
    .from("scribe_topics")
    .select("id, sku_id, project_id")
    .eq("id", topicId)
    .eq("project_id", projectId)
    .single();

  if (topicError || !topic) {
    return NextResponse.json(
      { error: { code: "not_found", message: "Topic not found" } },
      { status: 404 },
    );
  }

  // If selecting a topic, verify the SKU doesn't already have 5 selected
  if (selected) {
    const { data: selectedTopics, error: countError } = await supabase
      .from("scribe_topics")
      .select("id")
      .eq("sku_id", topic.sku_id)
      .eq("selected", true);

    if (countError) {
      return NextResponse.json(
        { error: { code: "internal_error", message: "Failed to check topic count" } },
        { status: 500 },
      );
    }

    // Allow if this topic is already selected, or if count is less than 5
    if (selectedTopics && selectedTopics.length >= 5 && !selectedTopics.find((t) => t.id === topicId)) {
      return NextResponse.json(
        { error: { code: "validation_error", message: "Maximum 5 topics can be selected per SKU" } },
        { status: 400 },
      );
    }
  }

  // Update the topic
  const { data: updatedTopic, error: updateError } = await supabase
    .from("scribe_topics")
    .update({ selected, updated_at: new Date().toISOString() })
    .eq("id", topicId)
    .select()
    .single();

  if (updateError || !updatedTopic) {
    return NextResponse.json(
      { error: { code: "internal_error", message: "Failed to update topic" } },
      { status: 500 },
    );
  }

  return NextResponse.json({
    id: updatedTopic.id,
    selected: updatedTopic.selected,
    skuId: updatedTopic.sku_id,
  });
}
