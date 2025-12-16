import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { requireAdmin, requireSession } from "@/lib/command-center/auth";
import { exportGoogleDocAsText, listMeetFolderFiles } from "@/lib/debrief/googleDrive";

export const runtime = "nodejs";

const clampLimit = (value: number) => Math.max(1, Math.min(50, value));

export async function POST(request: NextRequest) {
  const url = new URL(request.url);
  const limitParam = url.searchParams.get("limit");
  const limit = clampLimit(Number.parseInt(limitParam ?? "10", 10) || 10);

  const supabase = await createSupabaseRouteClient();
  const sessionResult = await requireSession(supabase);
  if (sessionResult.errorResponse) return sessionResult.errorResponse;

  const adminResult = await requireAdmin(supabase, sessionResult.user);
  if (adminResult.errorResponse) return adminResult.errorResponse;

  const files = await listMeetFolderFiles(limit);

  const rows: Array<Record<string, unknown>> = [];
  for (const file of files) {
    const content =
      file.mimeType === "application/vnd.google-apps.document"
        ? await exportGoogleDocAsText(file.id)
        : null;

    const ownerEmail = file.owners?.[0]?.emailAddress ?? null;
    const docUrl =
      file.webViewLink ??
      (file.mimeType === "application/vnd.google-apps.document"
        ? `https://docs.google.com/document/d/${file.id}/edit`
        : `https://drive.google.com/file/d/${file.id}/view`);

    rows.push({
      google_doc_id: file.id,
      google_doc_url: docUrl,
      title: file.name,
      // Drive metadata doesn't guarantee the actual meeting timestamp, but `modifiedTime`
      // is a good proxy for ordering until we parse dates from the title/content.
      meeting_date: file.modifiedTime,
      owner_email: ownerEmail ?? "unknown@ecomlabs.ca",
      raw_content: content,
      summary_content: null,
      status: "pending",
      extraction_error: null,
    });
  }

  if (rows.length === 0) {
    return NextResponse.json({ synced: 0 });
  }

  const { error } = await supabase
    .from("debrief_meeting_notes")
    .upsert(rows, { onConflict: "google_doc_id" });

  if (error) {
    return NextResponse.json(
      { error: { code: "server_error", message: error.message } },
      { status: 500 },
    );
  }

  return NextResponse.json({ synced: rows.length });
}
