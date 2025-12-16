import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { requireAdmin, requireSession } from "@/lib/command-center/auth";
import { asOptionalString, isUuid } from "@/lib/command-center/validators";

interface RemoveAssignmentPayload {
  assignmentId?: unknown;
}

export async function POST(request: NextRequest) {
  const supabase = await createSupabaseRouteClient();
  const sessionResult = await requireSession(supabase);
  if (sessionResult.errorResponse) return sessionResult.errorResponse;

  const adminResult = await requireAdmin(supabase, sessionResult.user);
  if (adminResult.errorResponse) return adminResult.errorResponse;

  const payload = (await request.json()) as RemoveAssignmentPayload;
  const assignmentId = asOptionalString(payload.assignmentId);

  if (!assignmentId || !isUuid(assignmentId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "assignmentId is invalid" } },
      { status: 400 },
    );
  }

  const { error } = await supabase.from("client_assignments").delete().eq("id", assignmentId);
  if (error) {
    return NextResponse.json(
      { error: { code: "server_error", message: error.message } },
      { status: 500 },
    );
  }

  return NextResponse.json({ ok: true });
}
