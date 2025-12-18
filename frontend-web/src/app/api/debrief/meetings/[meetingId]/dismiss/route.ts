import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { requireAdmin, requireSession } from "@/lib/command-center/auth";
import { isUuid } from "@/lib/command-center/validators";

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

  const now = new Date().toISOString();

  const { error } = await supabase
    .from("debrief_meeting_notes")
    .update({
      status: "dismissed",
      dismissed_by: sessionResult.user.id,
      dismissed_at: now,
    })
    .eq("id", meetingId);

  if (error) {
    return NextResponse.json(
      { error: { code: "server_error", message: error.message } },
      { status: 500 },
    );
  }

  return NextResponse.json({ ok: true });
}

