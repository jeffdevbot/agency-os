import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { requireAdmin, requireSession } from "@/lib/command-center/auth";
import { asOptionalString, isUuid } from "@/lib/command-center/validators";

interface UpsertAssignmentPayload {
  clientId?: unknown;
  brandId?: unknown;
  teamMemberId?: unknown;
  roleId?: unknown;
}

export async function POST(request: NextRequest) {
  const supabase = await createSupabaseRouteClient();
  const sessionResult = await requireSession(supabase);
  if (sessionResult.errorResponse) return sessionResult.errorResponse;

  const adminResult = await requireAdmin(supabase, sessionResult.user);
  if (adminResult.errorResponse) return adminResult.errorResponse;

  const payload = (await request.json()) as UpsertAssignmentPayload;
  const clientId = asOptionalString(payload.clientId);
  const roleId = asOptionalString(payload.roleId);
  const teamMemberId = asOptionalString(payload.teamMemberId);
  const brandId = payload.brandId === undefined ? null : asOptionalString(payload.brandId);

  if (!clientId || !isUuid(clientId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "clientId is invalid" } },
      { status: 400 },
    );
  }

  if (!roleId || !isUuid(roleId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "roleId is invalid" } },
      { status: 400 },
    );
  }

  if (!teamMemberId || !isUuid(teamMemberId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "teamMemberId is invalid" } },
      { status: 400 },
    );
  }

  if (brandId !== null && !isUuid(brandId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "brandId is invalid" } },
      { status: 400 },
    );
  }

  const now = new Date().toISOString();

  const existingQuery = supabase
    .from("client_assignments")
    .select("id")
    .eq("client_id", clientId)
    .eq("role_id", roleId);

  const { data: existing, error: existingError } =
    brandId === null
      ? await existingQuery.is("brand_id", null).maybeSingle()
      : await existingQuery.eq("brand_id", brandId).maybeSingle();

  if (existingError) {
    return NextResponse.json(
      { error: { code: "server_error", message: existingError.message } },
      { status: 500 },
    );
  }

  const assignedBy = sessionResult.user.id;

  if (existing?.id) {
    const { data, error } = await supabase
      .from("client_assignments")
      .update({
        team_member_id: teamMemberId,
        assigned_by: assignedBy,
        assigned_at: now,
      })
      .eq("id", existing.id)
      .select("id, client_id, brand_id, team_member_id, role_id, assigned_at, assigned_by")
      .single();

    if (error || !data) {
      return NextResponse.json(
        { error: { code: "server_error", message: error?.message ?? "Unable to update assignment" } },
        { status: 500 },
      );
    }

    return NextResponse.json({
      assignment: {
        id: data.id as string,
        clientId: data.client_id as string,
        brandId: (data.brand_id as string | null) ?? null,
        teamMemberId: data.team_member_id as string,
        roleId: data.role_id as string,
        assignedAt: data.assigned_at as string,
        assignedBy: (data.assigned_by as string | null) ?? null,
      },
    });
  }

  const { data, error } = await supabase
    .from("client_assignments")
    .insert({
      client_id: clientId,
      brand_id: brandId,
      team_member_id: teamMemberId,
      role_id: roleId,
      assigned_by: assignedBy,
      assigned_at: now,
    })
    .select("id, client_id, brand_id, team_member_id, role_id, assigned_at, assigned_by")
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: { code: "server_error", message: error?.message ?? "Unable to create assignment" } },
      { status: 500 },
    );
  }

  return NextResponse.json(
    {
      assignment: {
        id: data.id as string,
        clientId: data.client_id as string,
        brandId: (data.brand_id as string | null) ?? null,
        teamMemberId: data.team_member_id as string,
        roleId: data.role_id as string,
        assignedAt: data.assigned_at as string,
        assignedBy: (data.assigned_by as string | null) ?? null,
      },
    },
    { status: 201 },
  );
}
