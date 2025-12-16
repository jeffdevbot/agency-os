import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { requireAdmin, requireSession } from "@/lib/command-center/auth";
import { isUuid } from "@/lib/command-center/validators";
import { createClickUpTask } from "@/lib/clickup/api";

export const runtime = "nodejs";

export async function POST(
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

  const { data: meeting, error: meetingError } = await supabase
    .from("debrief_meeting_notes")
    .select("id, title, google_doc_url, google_doc_id, status")
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
      "id, title, description, suggested_brand_id, suggested_assignee_id, clickup_task_id, status",
    )
    .eq("meeting_note_id", meetingId)
    .order("created_at", { ascending: true });

  if (tasksError) {
    return NextResponse.json({ error: { code: "server_error", message: tasksError.message } }, { status: 500 });
  }

  const results: Array<{ taskId: string; clickupTaskId?: string; error?: string; skipped?: boolean }> = [];
  let attempted = 0;
  let created = 0;
  let skipped = 0;
  let failed = 0;
  let allSent = (tasks ?? []).length > 0;

  for (const task of tasks ?? []) {
    const existingClickupTaskId = (task.clickup_task_id as string | null) ?? null;
    if (existingClickupTaskId) {
      results.push({ taskId: task.id as string, clickupTaskId: existingClickupTaskId, skipped: true });
      skipped += 1;
      continue;
    }

    const taskTitle = String(task.title ?? "").trim();
    if (!taskTitle) {
      const message = "Task title is empty";
      results.push({ taskId: task.id as string, error: message });
      failed += 1;
      allSent = false;
      await supabase
        .from("debrief_extracted_tasks")
        .update({ status: "failed", clickup_error: message })
        .eq("id", task.id as string);
      continue;
    }

    attempted += 1;

    let listId: string | null = null;
    let spaceId: string | null = null;
    const brandId = (task.suggested_brand_id as string | null) ?? null;
    if (brandId) {
      const { data: brand, error: brandError } = await supabase
        .from("brands")
        .select("id, clickup_list_id, clickup_space_id")
        .eq("id", brandId)
        .single();
      if (brandError) {
        results.push({ taskId: task.id as string, error: brandError.message });
        failed += 1;
        await supabase
          .from("debrief_extracted_tasks")
          .update({ status: "failed", clickup_error: brandError.message })
        .eq("id", task.id as string);
        continue;
      }
      listId = (brand?.clickup_list_id as string | null) ?? null;
      spaceId = (brand?.clickup_space_id as string | null) ?? null;
    }

    if (!listId && !spaceId) {
      const message = "No ClickUp destination configured. Set brands.clickup_list_id (preferred) or brands.clickup_space_id.";
      results.push({ taskId: task.id as string, error: message });
      failed += 1;
      await supabase
        .from("debrief_extracted_tasks")
        .update({ status: "failed", clickup_error: message })
        .eq("id", task.id as string);
      continue;
    }

    let clickupAssigneeId: string | null = null;
    const assigneeId = (task.suggested_assignee_id as string | null) ?? null;
    if (assigneeId) {
      const { data: profile, error: profileError } = await supabase
        .from("profiles")
        .select("id, clickup_user_id")
        .eq("id", assigneeId)
        .single();
      if (profileError) {
        results.push({ taskId: task.id as string, error: profileError.message });
        failed += 1;
        await supabase
          .from("debrief_extracted_tasks")
          .update({ status: "failed", clickup_error: profileError.message })
          .eq("id", task.id as string);
        continue;
      }
      clickupAssigneeId = (profile?.clickup_user_id as string | null) ?? null;
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
      const createdTask = await createClickUpTask({
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
          clickup_task_id: createdTask.id,
          clickup_error: null,
        })
        .eq("id", task.id as string);

      if (updateError) {
        results.push({ taskId: task.id as string, error: updateError.message });
        failed += 1;
        allSent = false;
        continue;
      }

      results.push({ taskId: task.id as string, clickupTaskId: createdTask.id });
      created += 1;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      results.push({ taskId: task.id as string, error: message });
      failed += 1;
      allSent = false;
      await supabase
        .from("debrief_extracted_tasks")
        .update({ status: "failed", clickup_error: message })
        .eq("id", task.id as string);
    }
  }

  if (allSent && failed === 0) {
    await supabase.from("debrief_meeting_notes").update({ status: "processed" }).eq("id", meetingId);
  }

  return NextResponse.json({
    attempted,
    created,
    skipped,
    failed,
    results,
  });
}
