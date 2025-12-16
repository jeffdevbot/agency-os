import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient, createSupabaseServiceClient } from "@/lib/supabase/serverClient";
import { requireAdmin, requireSession } from "@/lib/command-center/auth";
import { asOptionalString, isUuid } from "@/lib/command-center/validators";

interface PatchClientPayload {
  name?: unknown;
  status?: unknown;
  notes?: unknown;
}

const isClientStatus = (value: string) => ["active", "inactive", "archived"].includes(value);

export async function GET(
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
    .select("id, name, status, notes, brands(id, name, clickup_space_id, clickup_list_id, product_keywords, amazon_marketplaces)")
    .eq("id", clientId)
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: { code: "server_error", message: error?.message ?? "Client not found" } },
      { status: 500 },
    );
  }

  return NextResponse.json({ client: data });
}

export async function PATCH(
  request: NextRequest,
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

  const payload = (await request.json()) as PatchClientPayload;

  const name = asOptionalString(payload.name);
  const notes = payload.notes === undefined ? undefined : asOptionalString(payload.notes);
  const status = payload.status === undefined ? undefined : asOptionalString(payload.status);

  if (status && !isClientStatus(status)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "status is invalid" } },
      { status: 400 },
    );
  }

  const update: Record<string, unknown> = {};
  if (name) update.name = name;
  if (notes !== undefined) update.notes = notes;
  if (status) update.status = status;

  const { data, error } = await supabase
    .from("agency_clients")
    .update(update)
    .eq("id", clientId)
    .select("id, name, status, notes, created_at, updated_at")
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: { code: "server_error", message: error?.message ?? "Unable to update client" } },
      { status: 500 },
    );
  }

  return NextResponse.json({ client: data });
}

export async function DELETE(
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

  const { data: client, error: clientError } = await supabase
    .from("agency_clients")
    .select("id, status")
    .eq("id", clientId)
    .single();

  if (clientError || !client) {
    return NextResponse.json(
      { error: { code: "server_error", message: clientError?.message ?? "Client not found" } },
      { status: 500 },
    );
  }

  if ((client.status as string) !== "archived") {
    return NextResponse.json(
      { error: { code: "validation_error", message: "Client must be archived before deleting" } },
      { status: 400 },
    );
  }

  const service = createSupabaseServiceClient();
  const { error: assignmentsError } = await service
    .from("client_assignments")
    .delete()
    .eq("client_id", clientId);
  if (assignmentsError) {
    return NextResponse.json(
      { error: { code: "server_error", message: assignmentsError.message } },
      { status: 500 },
    );
  }

  const { error: brandsError } = await service.from("brands").delete().eq("client_id", clientId);
  if (brandsError) {
    return NextResponse.json(
      { error: { code: "server_error", message: brandsError.message } },
      { status: 500 },
    );
  }

  const { error } = await service.from("agency_clients").delete().eq("id", clientId);
  if (error) {
    return NextResponse.json(
      { error: { code: "server_error", message: error.message } },
      { status: 500 },
    );
  }

  return NextResponse.json({ ok: true });
}
