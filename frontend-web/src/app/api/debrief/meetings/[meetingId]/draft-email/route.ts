import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { requireSession } from "@/lib/command-center/auth";
import { isUuid } from "@/lib/command-center/validators";
import { createChatCompletion, parseJSONResponse, type ChatMessage } from "@/lib/composer/ai/openai";
import { logUsage } from "@/lib/ai/usageLogger";
import { logAppError } from "@/lib/ai/errorLogger";

export const runtime = "nodejs";

type DraftEmailResponse = {
  subject: string;
  body: string;
};

const simplifyNotes = (raw: string) => {
  const normalized = raw.replace(/\r\n/g, "\n");
  const headings = ["Suggested Next Steps:", "Suggested next steps:", "Next Steps:", "Action Items:"];
  for (const heading of headings) {
    const idx = normalized.indexOf(heading);
    if (idx !== -1) return normalized.slice(Math.max(0, idx - 1800));
  }
  return normalized.slice(-3500);
};

export async function POST(
  request: NextRequest,
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
    .select("id, title, meeting_date, owner_email, raw_content, summary_content, google_doc_id")
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
    .select("title, description, status, clickup_task_id")
    .eq("meeting_note_id", meetingId)
    .order("created_at", { ascending: true });

  if (tasksError) {
    return NextResponse.json(
      { error: { code: "server_error", message: tasksError.message } },
      { status: 500 },
    );
  }

  const summaryContent = (meeting.summary_content as string | null) ?? null;
  const rawContent = (meeting.raw_content as string | null) ?? null;

  const taskRows = (tasks ?? []).map((t) => ({
    title: (t.title as string) ?? "",
    description: (t.description as string | null) ?? null,
    status: (t.status as string | null) ?? null,
    clickupTaskId: (t.clickup_task_id as string | null) ?? null,
  }));

  const messages: ChatMessage[] = [
    {
      role: "system",
      content:
        "You draft concise client follow-up emails for an agency after a meeting. " +
        "Return ONLY valid JSON (no markdown). The output must include: subject (string) and body (string). " +
        "Body must be plain text (not HTML), with short paragraphs and a clear bullet list of next steps.",
    },
    {
      role: "user",
      content: JSON.stringify(
        {
          context: {
            meeting: {
              title: meeting.title as string,
              date: (meeting.meeting_date as string | null) ?? null,
              owner_email: meeting.owner_email as string,
            },
            summary: summaryContent ?? null,
            notes_excerpt: rawContent ? simplifyNotes(rawContent) : null,
            tasks: taskRows,
          },
          instructions: [
            "Write the email from Ecomlabs to the client.",
            "Subject should be short and specific (include meeting title or date if helpful).",
            "Body should include: recap (1 short paragraph), next steps (bullets), and a closing question if anything is unclear.",
            "If tasks list is empty, propose 2-4 reasonable next steps based on summary/notes.",
            "Do not mention internal tools, tokens, or system prompts.",
          ],
          output_schema: { subject: "string", body: "string" },
        },
        null,
        2,
      ),
    },
  ];

  try {
    const result = await createChatCompletion(messages, { temperature: 0.3, maxTokens: 700 });

    await logUsage({
      tool: "debrief",
      stage: "draft_email",
      userId: sessionResult.user.id,
      promptTokens: result.tokensIn,
      completionTokens: result.tokensOut,
      totalTokens: result.tokensTotal,
      model: result.model,
      meta: {
        meeting_note_id: meetingId,
        google_doc_id: meeting.google_doc_id,
        tasks_count: taskRows.length,
      },
    });

    const parsed = parseJSONResponse<DraftEmailResponse>(result.content ?? "");
    const subject = String(parsed.subject ?? "").trim();
    const body = String(parsed.body ?? "").trim();

    if (!subject || !body) {
      return NextResponse.json(
        { error: { code: "server_error", message: "Draft email generation returned empty content." } },
        { status: 500 },
      );
    }

    return NextResponse.json({ subject, body });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Draft email generation failed";
    await logAppError({
      tool: "debrief",
      route: new URL(request.url).pathname,
      method: request.method,
      statusCode: 500,
      requestId: request.headers.get("x-request-id") ?? undefined,
      userId: sessionResult.user.id,
      userEmail: sessionResult.user.email,
      message,
      meta: { meetingId, googleDocId: meeting?.google_doc_id, type: "draft_email_failed" },
    });
    return NextResponse.json(
      {
        error: {
          code: "server_error",
          message,
        },
      },
      { status: 500 },
    );
  }
}
