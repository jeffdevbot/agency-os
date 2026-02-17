import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { requireAdmin, requireSession } from "@/lib/command-center/auth";
import { isUuid } from "@/lib/command-center/validators";
import { createChatCompletion, parseJSONResponse, type ChatMessage } from "@/lib/composer/ai/openai";
import { exportGoogleDocAsText } from "@/lib/debrief/googleDrive";
import { logUsage } from "@/lib/ai/usageLogger";
import { logAppError } from "@/lib/ai/errorLogger";
import { simplifyNotesForExtraction, normalizeExtractedTasks } from "@/lib/debrief/meetingParser";
import { reviewExtractedTasks } from "@/lib/debrief/taskReview";

export const runtime = "nodejs";

type ExtractedTaskJson = {
  raw_text: string;
  title: string;
  description?: string | null;
  brand_id?: string | null;
  role_slug?: string | null;
};

type ExtractionResponse = {
  tasks: ExtractedTaskJson[];
};



export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ meetingId: string }> },
) {
  const { meetingId } = await params;
  const url = new URL(request.url);
  const replace = url.searchParams.get("replace") === "1";
  const requestId = request.headers.get("x-request-id") ?? undefined;
  const route = url.pathname;

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

  const { data: meeting, error: meetingError } = await supabase
    .from("debrief_meeting_notes")
    .select("id, google_doc_id, title, raw_content, status")
    .eq("id", meetingId)
    .single();

  if (meetingError || !meeting) {
    return NextResponse.json(
      { error: { code: "server_error", message: meetingError?.message ?? "Meeting not found" } },
      { status: 500 },
    );
  }

  const { count, error: countError } = await supabase
    .from("debrief_extracted_tasks")
    .select("id", { count: "exact", head: true })
    .eq("meeting_note_id", meetingId);

  if (countError) {
    return NextResponse.json(
      { error: { code: "server_error", message: countError.message } },
      { status: 500 },
    );
  }

  if (!replace && (count ?? 0) > 0) {
    return NextResponse.json(
      { error: { code: "conflict", message: "Meeting already has extracted tasks; use replace=1 to re-extract." } },
      { status: 409 },
    );
  }

  await supabase
    .from("debrief_meeting_notes")
    .update({ status: "processing", extraction_error: null })
    .eq("id", meetingId);

  try {
    const [{ data: brands, error: brandsError }, { data: roles, error: rolesError }] = await Promise.all([
      supabase.from("brands").select("id, client_id, name, product_keywords, amazon_marketplaces"),
      supabase.from("agency_roles").select("id, slug, name"),
    ]);

    const error = brandsError ?? rolesError;
    if (error) throw new Error(error.message);

    const brandList = (brands ?? []).map((brand) => ({
      id: brand.id as string,
      clientId: brand.client_id as string,
      name: brand.name as string,
      productKeywords: (brand.product_keywords as string[] | null) ?? [],
      amazonMarketplaces: (brand.amazon_marketplaces as string[] | null) ?? [],
    }));

    const roleBySlug = new Map(
      (roles ?? []).map((role) => [role.slug as string, { id: role.id as string, name: role.name as string }]),
    );

    const rawContent =
      (meeting.raw_content as string | null) ??
      (await exportGoogleDocAsText(meeting.google_doc_id as string));

    const focusedNotes = simplifyNotesForExtraction(rawContent);

    const messages: ChatMessage[] = [
      {
        role: "system",
        content:
          "You extract actionable tasks from meeting notes for an agency team. " +
          "Return ONLY valid JSON (no markdown).",
      },
      {
        role: "user",
        content: JSON.stringify(
          {
            instructions: [
              "Extract only actionable tasks that Ecomlabs should do after this meeting.",
              "Ignore pure informational notes, introductions, and recruiting/interview discussion unless there are explicit action items.",
              "Each task must have a short title and optional description.",
              "If you can map to a known brand, set brand_id to one of the provided brand IDs; otherwise brand_id = null.",
              "If you can map to a role, set role_slug to one of the allowed role slugs; otherwise role_slug = null.",
              "Prefer fewer, higher-quality tasks over many low-quality tasks.",
            ],
            allowed_role_slugs: Array.from(roleBySlug.keys()),
            brands: brandList,
            meeting: {
              title: meeting.title as string,
              notes: focusedNotes,
            },
            output_schema: {
              tasks: [
                {
                  raw_text: "string (verbatim task sentence if possible)",
                  title: "string",
                  description: "string|null",
                  brand_id: "uuid|null",
                  role_slug: "string|null",
                },
              ],
            },
          },
          null,
          2,
        ),
      },
    ];

    const result = await createChatCompletion(messages, { temperature: 0.2, maxTokens: 1200 });

    await logUsage({
      tool: "debrief",
      stage: "extract",
      userId: sessionResult.user.id,
      promptTokens: result.tokensIn,
      completionTokens: result.tokensOut,
      totalTokens: result.tokensTotal,
      model: result.model,
      meta: {
        meeting_note_id: meetingId,
        google_doc_id: meeting.google_doc_id,
        replace,
      },
    });

    const content = result.content ?? "";
    const parsed = parseJSONResponse<ExtractionResponse>(content);
    const tasks = Array.isArray(parsed.tasks) ? parsed.tasks : [];

    // Use standalone parser for validation and normalization
    const cleanedTasks = normalizeExtractedTasks(tasks);

    // Quality Review (Logging only)
    const droppedCount = tasks.length - cleanedTasks.length;
    const reviewResult = reviewExtractedTasks(cleanedTasks, droppedCount);

    // In V1, we just log this for observability. 
    // In future, this could trigger a warming/blocking UI state.
    if (reviewResult.severity !== "ok") {
      console.log(JSON.stringify({
        event: "debrief_quality_review",
        meetingId,
        severity: reviewResult.severity,
        summary: reviewResult.summary,
        flagsCount: reviewResult.flags.length
      }));
    }

    if (replace) {
      const { error: deleteError } = await supabase
        .from("debrief_extracted_tasks")
        .delete()
        .eq("meeting_note_id", meetingId);
      if (deleteError) throw new Error(deleteError.message);
    }

    const assignmentsByBrandRoleSlug = new Map<string, string>();
    const byClientId = new Map<string, string[]>();
    for (const brand of brandList) {
      if (!byClientId.has(brand.clientId)) byClientId.set(brand.clientId, []);
      byClientId.get(brand.clientId)?.push(brand.id);
    }

    // Only compute assignees if we have brand_id + role_slug.
    const neededBrandIds = Array.from(new Set(cleanedTasks.map((t) => t.brandId).filter(Boolean))) as string[];
    if (neededBrandIds.length > 0) {
      const { data: brandRows, error: brandFetchError } = await supabase
        .from("brands")
        .select("id, client_id")
        .in("id", neededBrandIds);
      if (brandFetchError) throw new Error(brandFetchError.message);

      const clientIds = Array.from(new Set((brandRows ?? []).map((row) => row.client_id as string)));
      if (clientIds.length > 0) {
        const { data: assignments, error: assignmentError } = await supabase
          .from("client_assignments")
          .select("client_id, brand_id, team_member_id, role_id")
          .in("client_id", clientIds);
        if (assignmentError) throw new Error(assignmentError.message);

        for (const assignment of assignments ?? []) {
          const brandId = (assignment.brand_id as string | null) ?? null;
          if (!brandId) continue; // brand-level only in current workflow
          const roleId = assignment.role_id as string;
          const roleSlug = Array.from(roleBySlug.entries()).find(([, meta]) => meta.id === roleId)?.[0] ?? null;
          if (!roleSlug) continue;
          assignmentsByBrandRoleSlug.set(`${brandId}:${roleSlug}`, assignment.team_member_id as string);
        }
      }
    }

    const rows = cleanedTasks.map((task) => {
      const suggestedAssigneeId =
        task.brandId && task.roleSlug ? assignmentsByBrandRoleSlug.get(`${task.brandId}:${task.roleSlug}`) ?? null : null;

      return {
        meeting_note_id: meetingId,
        raw_text: task.rawText.length > 0 ? task.rawText : task.title,
        title: task.title,
        description: task.description,
        suggested_brand_id: task.brandId,
        suggested_assignee_id: suggestedAssigneeId,
        task_type: task.roleSlug,
        status: "pending",
      };
    });

    if (rows.length > 0) {
      const { error: insertError } = await supabase.from("debrief_extracted_tasks").insert(rows);
      if (insertError) throw new Error(insertError.message);
    }

    const { error: meetingUpdateError } = await supabase
      .from("debrief_meeting_notes")
      .update({ status: "ready", raw_content: rawContent })
      .eq("id", meetingId);
    if (meetingUpdateError) throw new Error(meetingUpdateError.message);

    return NextResponse.json({ extracted: rows.length });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    await logAppError({
      tool: "debrief",
      route,
      method: request.method,
      statusCode: 500,
      requestId,
      userId: sessionResult.user.id,
      userEmail: sessionResult.user.email,
      message,
      meta: { meetingId, googleDocId: meeting.google_doc_id, replace, type: "extract_failed" },
    });
    await supabase
      .from("debrief_meeting_notes")
      .update({ status: "failed", extraction_error: message })
      .eq("id", meetingId);

    return NextResponse.json(
      { error: { code: "server_error", message } },
      { status: 500 },
    );
  }
}
