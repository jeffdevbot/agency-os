import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { requireSession } from "@/lib/command-center/auth";

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const status = url.searchParams.get("status");

  const supabase = await createSupabaseRouteClient();
  const sessionResult = await requireSession(supabase);
  if (sessionResult.errorResponse) return sessionResult.errorResponse;

  let query = supabase
    .from("debrief_meeting_notes")
    .select("id, google_doc_url, title, meeting_date, owner_email, status, created_at, updated_at")
    .order("meeting_date", { ascending: false, nullsFirst: false })
    .order("updated_at", { ascending: false });

  if (status) {
    query = query.eq("status", status);
  }

  const { data, error } = await query;
  if (error) {
    return NextResponse.json(
      { error: { code: "server_error", message: error.message } },
      { status: 500 },
    );
  }

  return NextResponse.json({
    meetings: (data ?? []).map((row) => ({
      id: row.id as string,
      googleDocUrl: row.google_doc_url as string,
      title: row.title as string,
      meetingDate: (row.meeting_date as string | null) ?? null,
      ownerEmail: row.owner_email as string,
      status: row.status as string,
      createdAt: row.created_at as string,
      updatedAt: row.updated_at as string,
    })),
  });
}

