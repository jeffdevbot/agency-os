import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { requireAdmin, requireSession } from "@/lib/command-center/auth";
import { isUuid } from "@/lib/command-center/validators";

export const runtime = "nodejs";

type ApiError = { error: { code: string; message: string } };

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ taskId: string }> },
) {
  const { taskId } = await params;
  if (!isUuid(taskId)) {
    return NextResponse.json({ error: { code: "validation_error", message: "taskId is invalid" } }, { status: 400 });
  }

  const supabase = await createSupabaseRouteClient();
  const sessionResult = await requireSession(supabase);
  if (sessionResult.errorResponse) return sessionResult.errorResponse;
  const adminResult = await requireAdmin(supabase, sessionResult.user);
  if (adminResult.errorResponse) return adminResult.errorResponse;

  const body = (await request.json().catch(() => null)) as
    | { title?: unknown; description?: unknown; suggestedBrandId?: unknown; suggestedAssigneeId?: unknown }
    | null;

  if (!body) {
    return NextResponse.json({ error: { code: "validation_error", message: "Invalid JSON body" } }, { status: 400 });
  }

  const update: Record<string, unknown> = {};
  if (body.title !== undefined) update.title = String(body.title).trim();
  if (body.description !== undefined) {
    update.description = body.description === null ? null : String(body.description).trim();
  }
  if (body.suggestedBrandId !== undefined) {
    update.suggested_brand_id = body.suggestedBrandId === null ? null : String(body.suggestedBrandId);
  }
  if (body.suggestedAssigneeId !== undefined) {
    update.suggested_assignee_id = body.suggestedAssigneeId === null ? null : String(body.suggestedAssigneeId);
  }

  if (Object.keys(update).length === 0) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "No fields provided" } },
      { status: 400 },
    );
  }

  if (typeof update.title === "string" && update.title.length === 0) {
    return NextResponse.json({ error: { code: "validation_error", message: "Title cannot be empty" } }, { status: 400 });
  }

  const { data, error } = await supabase
    .from("debrief_extracted_tasks")
    .update(update)
    .eq("id", taskId)
    .select(
      "id, meeting_note_id, raw_text, title, description, suggested_brand_id, suggested_assignee_id, task_type, status, clickup_task_id, clickup_error, created_at, updated_at",
    )
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: { code: "server_error", message: error?.message ?? "Unable to update task" } } satisfies ApiError,
      { status: 500 },
    );
  }

  return NextResponse.json({
    task: {
      id: data.id as string,
      meetingNoteId: data.meeting_note_id as string,
      rawText: data.raw_text as string,
      title: data.title as string,
      description: (data.description as string | null) ?? null,
      suggestedBrandId: (data.suggested_brand_id as string | null) ?? null,
      suggestedAssigneeId: (data.suggested_assignee_id as string | null) ?? null,
      taskType: (data.task_type as string | null) ?? null,
      status: data.status as string,
      clickupTaskId: (data.clickup_task_id as string | null) ?? null,
      clickupError: (data.clickup_error as string | null) ?? null,
      createdAt: data.created_at as string,
      updatedAt: data.updated_at as string,
    },
  });
}

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ taskId: string }> },
) {
  const { taskId } = await params;
  if (!isUuid(taskId)) {
    return NextResponse.json({ error: { code: "validation_error", message: "taskId is invalid" } }, { status: 400 });
  }

  const supabase = await createSupabaseRouteClient();
  const sessionResult = await requireSession(supabase);
  if (sessionResult.errorResponse) return sessionResult.errorResponse;
  const adminResult = await requireAdmin(supabase, sessionResult.user);
  if (adminResult.errorResponse) return adminResult.errorResponse;

  const { error } = await supabase.from("debrief_extracted_tasks").delete().eq("id", taskId);

  if (error) {
    return NextResponse.json({ error: { code: "server_error", message: error.message } }, { status: 500 });
  }

  return NextResponse.json({ removed: true });
}

