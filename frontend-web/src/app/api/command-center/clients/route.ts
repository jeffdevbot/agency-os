import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { requireAdmin, requireSession } from "@/lib/command-center/auth";
import { asOptionalString } from "@/lib/command-center/validators";

interface CreateClientPayload {
  name?: unknown;
  status?: unknown;
  notes?: unknown;
}

const isClientStatus = (value: string) => ["active", "inactive", "archived"].includes(value);

export async function GET() {
  const supabase = await createSupabaseRouteClient();
  const sessionResult = await requireSession(supabase);
  if (sessionResult.errorResponse) return sessionResult.errorResponse;

  const adminResult = await requireAdmin(supabase, sessionResult.user);
  if (adminResult.errorResponse) return adminResult.errorResponse;

  const { data, error } = await supabase
    .from("agency_clients")
    .select("id, name, status, notes, created_at, updated_at, brands(id, name)")
    .order("name", { ascending: true });

  if (error) {
    return NextResponse.json(
      { error: { code: "server_error", message: error.message } },
      { status: 500 },
    );
  }

  return NextResponse.json({ clients: data ?? [] });
}

export async function POST(request: NextRequest) {
  const supabase = await createSupabaseRouteClient();
  const sessionResult = await requireSession(supabase);
  if (sessionResult.errorResponse) return sessionResult.errorResponse;

  const adminResult = await requireAdmin(supabase, sessionResult.user);
  if (adminResult.errorResponse) return adminResult.errorResponse;

  const payload = (await request.json()) as CreateClientPayload;
  const name = asOptionalString(payload.name);
  const notes = asOptionalString(payload.notes);
  const status = asOptionalString(payload.status) ?? "active";

  if (!name) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "name is required" } },
      { status: 400 },
    );
  }

  if (!isClientStatus(status)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "status is invalid" } },
      { status: 400 },
    );
  }

  const now = new Date().toISOString();
  const { data, error } = await supabase
    .from("agency_clients")
    .insert({ name, status, notes, created_at: now, updated_at: now })
    .select("id, name, status, notes, created_at, updated_at")
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: { code: "server_error", message: error?.message ?? "Unable to create client" } },
      { status: 500 },
    );
  }

  return NextResponse.json({ client: data }, { status: 201 });
}
