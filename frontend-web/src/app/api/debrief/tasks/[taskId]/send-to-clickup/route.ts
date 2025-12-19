import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { requireAdmin, requireSession } from "@/lib/command-center/auth";
import { isUuid } from "@/lib/command-center/validators";
import { createClickUpTask } from "@/lib/clickup/api";
import { logAppError } from "@/lib/ai/errorLogger";

export const runtime = "nodejs";

export async function POST(
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

  const { data: sessionData, error: sessionError } = await supabase.auth.getSession();
  if (sessionError) {
    return NextResponse.json({ error: { code: "server_error", message: sessionError.message } }, { status: 500 });
  }
  const accessToken = sessionData.session?.access_token;
  if (!accessToken) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Missing session token" } }, { status: 401 });
  }

  const { data: task, error: taskError } = await supabase
    .from("debrief_extracted_tasks")
    .select(
      "id, meeting_note_id, title, description, suggested_brand_id, suggested_assignee_id, clickup_task_id, status",
    )
    .eq("id", taskId)
    .single();

  if (taskError || !task) {
    return NextResponse.json(
      { error: { code: "server_error", message: taskError?.message ?? "Task not found" } },
      { status: 500 },
    );
  }

  if ((task.clickup_task_id as string | null) ?? null) {
    return NextResponse.json({ clickupTaskId: task.clickup_task_id as string, alreadySent: true });
  }

  const { data: meeting, error: meetingError } = await supabase
    .from("debrief_meeting_notes")
    .select("id, title, google_doc_url, google_doc_id")
    .eq("id", task.meeting_note_id as string)
    .single();

  if (meetingError || !meeting) {
    return NextResponse.json(
      { error: { code: "server_error", message: meetingError?.message ?? "Meeting not found" } },
      { status: 500 },
    );
  }

  let listId: string | null = null;
  let spaceId: string | null = null;
  const suggestedBrandId = (task.suggested_brand_id as string | null) ?? null;
  if (suggestedBrandId) {
    const { data: brand, error: brandError } = await supabase
      .from("brands")
      .select("id, clickup_list_id, clickup_space_id")
      .eq("id", suggestedBrandId)
      .single();
    if (brandError) {
      return NextResponse.json({ error: { code: "server_error", message: brandError.message } }, { status: 500 });
    }
    listId = (brand?.clickup_list_id as string | null) ?? null;
    spaceId = (brand?.clickup_space_id as string | null) ?? null;
  }

  if (!listId && !spaceId) {
    return NextResponse.json(
      {
        error: {
          code: "validation_error",
          message:
            "No ClickUp destination configured. Set brands.clickup_list_id (preferred) or brands.clickup_space_id.",
        },
      },
      { status: 400 },
    );
  }

  let clickupAssigneeId: string | null = null;
  const suggestedAssigneeId = (task.suggested_assignee_id as string | null) ?? null;
  if (suggestedAssigneeId) {
    const { data: profile, error: profileError } = await supabase
      .from("profiles")
      .select("id, clickup_user_id")
      .eq("id", suggestedAssigneeId)
      .single();
    if (profileError) {
      return NextResponse.json({ error: { code: "server_error", message: profileError.message } }, { status: 500 });
    }
    clickupAssigneeId = (profile?.clickup_user_id as string | null) ?? null;
  }

  const taskTitle = String(task.title ?? "").trim();
  if (!taskTitle) {
    return NextResponse.json({ error: { code: "validation_error", message: "Task title is empty" } }, { status: 400 });
  }

  const clickupDescriptionParts: string[] = [];
  clickupDescriptionParts.push(`Meeting: ${meeting.title as string}`);
  clickupDescriptionParts.push(`Notes: ${meeting.google_doc_url as string}`);
  clickupDescriptionParts.push("");
  const taskDescription = (task.description as string | null) ?? null;
  if (taskDescription && taskDescription.trim().length > 0) {
    clickupDescriptionParts.push(taskDescription.trim());
  }
  clickupDescriptionParts.push("");
  clickupDescriptionParts.push(`Debrief meeting_note_id: ${meeting.id as string}`);
  clickupDescriptionParts.push(`Debrief google_doc_id: ${meeting.google_doc_id as string}`);

  try {
    const created = await createClickUpTask({
      accessToken,
      listId,
      spaceId,
      name: taskTitle,
      description: clickupDescriptionParts.join("\n"),
      assigneeIds: clickupAssigneeId ? [clickupAssigneeId] : [],
    });

    const { error: updateError } = await supabase
      .from("debrief_extracted_tasks")
      .update({
        status: "created",
        clickup_task_id: created.id,
        clickup_error: null,
      })
      .eq("id", taskId);

    if (updateError) {
      return NextResponse.json({ error: { code: "server_error", message: updateError.message } }, { status: 500 });
    }

    return NextResponse.json({ clickupTaskId: created.id, clickupUrl: created.url ?? null });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    await logAppError({
      tool: "debrief",
      route: new URL(request.url).pathname,
      method: request.method,
      statusCode: 500,
      requestId: request.headers.get("x-request-id") ?? undefined,
      userId: sessionResult.user.id,
      userEmail: sessionResult.user.email,
      message,
      meta: { taskId, meetingNoteId: task.meeting_note_id, type: "clickup_task_create_failed" },
    });
    await supabase
      .from("debrief_extracted_tasks")
      .update({ status: "failed", clickup_error: message })
      .eq("id", taskId);

    return NextResponse.json({ error: { code: "server_error", message } }, { status: 500 });
  }
}
