import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { requireAdmin, requireSession } from "@/lib/command-center/auth";
import { isUuid } from "@/lib/command-center/validators";

export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ clientId: string }> },
) {
  const { clientId } = await params;

  if (!isUuid(clientId)) {
    const message =
      process.env.NODE_ENV === "production"
        ? "clientId is invalid"
        : `clientId is invalid: ${clientId}`;
    return NextResponse.json(
      { error: { code: "validation_error", message } },
      { status: 400 },
    );
  }

  const supabase = await createSupabaseRouteClient();
  const sessionResult = await requireSession(supabase);
  if (sessionResult.errorResponse) return sessionResult.errorResponse;

  const adminResult = await requireAdmin(supabase, sessionResult.user);
  if (adminResult.errorResponse) return adminResult.errorResponse;

  const { data, error } = await supabase
    .from("agency_clients")
    .update({ status: "archived" })
    .eq("id", clientId)
    .select("id, name, status, notes, created_at, updated_at")
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: { code: "server_error", message: error?.message ?? "Unable to archive client" } },
      { status: 500 },
    );
  }

  return NextResponse.json({ client: data });
}
