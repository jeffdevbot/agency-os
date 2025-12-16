import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { requireSession } from "@/lib/command-center/auth";
import { isUuid } from "@/lib/command-center/validators";

export const runtime = "nodejs";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ meetingId: string }> },
) {
  const { meetingId } = await params;

  if (!isUuid(meetingId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "meetingId is invalid" } },
      { status: 400 },
    );
  }

  const supabase = await createSupabaseRouteClient();
  const sessionResult = await requireSession(supabase);
  if (sessionResult.errorResponse) return sessionResult.errorResponse;

  const { data: meeting, error: meetingError } = await supabase
    .from("debrief_meeting_notes")
    .select(
      "id, google_doc_url, title, meeting_date, owner_email, raw_content, summary_content, suggested_client_id, status, extraction_error, created_at, updated_at",
    )
    .eq("id", meetingId)
    .single();

  if (meetingError || !meeting) {
    return NextResponse.json(
      { error: { code: "server_error", message: meetingError?.message ?? "Meeting not found" } },
      { status: 500 },
    );
  }

  const { data: tasks, error: tasksError } = await supabase
    .from("debrief_extracted_tasks")
    .select(
      "id, meeting_note_id, raw_text, title, description, suggested_brand_id, suggested_assignee_id, task_type, status, clickup_task_id, clickup_error, created_at, updated_at",
    )
    .eq("meeting_note_id", meetingId)
    .order("created_at", { ascending: true });

  if (tasksError) {
    return NextResponse.json(
      { error: { code: "server_error", message: tasksError.message } },
      { status: 500 },
    );
  }

  return NextResponse.json({
    meeting: {
      id: meeting.id as string,
      googleDocUrl: meeting.google_doc_url as string,
      title: meeting.title as string,
      meetingDate: (meeting.meeting_date as string | null) ?? null,
      ownerEmail: meeting.owner_email as string,
      rawContent: (meeting.raw_content as string | null) ?? null,
      summaryContent: (meeting.summary_content as string | null) ?? null,
      suggestedClientId: (meeting.suggested_client_id as string | null) ?? null,
      status: meeting.status as string,
      extractionError: (meeting.extraction_error as string | null) ?? null,
      createdAt: meeting.created_at as string,
      updatedAt: meeting.updated_at as string,
    },
    tasks: (tasks ?? []).map((task) => ({
      id: task.id as string,
      meetingNoteId: task.meeting_note_id as string,
      rawText: task.raw_text as string,
      title: task.title as string,
      description: (task.description as string | null) ?? null,
      suggestedBrandId: (task.suggested_brand_id as string | null) ?? null,
      suggestedAssigneeId: (task.suggested_assignee_id as string | null) ?? null,
      taskType: (task.task_type as string | null) ?? null,
      status: task.status as string,
      clickupTaskId: (task.clickup_task_id as string | null) ?? null,
      clickupError: (task.clickup_error as string | null) ?? null,
      createdAt: task.created_at as string,
      updatedAt: task.updated_at as string,
    })),
  });
}
