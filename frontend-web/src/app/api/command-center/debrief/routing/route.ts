import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { requireSession } from "@/lib/command-center/auth";
import { isUuid } from "@/lib/command-center/validators";

export async function GET(request: NextRequest) {
  const brandId = request.nextUrl.searchParams.get("brandId") ?? "";

  if (!isUuid(brandId)) {
    const message =
      process.env.NODE_ENV === "production"
        ? "brandId is invalid"
        : `brandId is invalid: ${brandId}`;
    return NextResponse.json(
      { error: { code: "validation_error", message } },
      { status: 400 },
    );
  }

  const supabase = await createSupabaseRouteClient();
  const sessionResult = await requireSession(supabase);
  if (sessionResult.errorResponse) return sessionResult.errorResponse;

  const { data: brand, error: brandError } = await supabase
    .from("brands")
    .select("id, client_id")
    .eq("id", brandId)
    .single();

  if (brandError || !brand) {
    return NextResponse.json(
      { error: { code: "server_error", message: brandError?.message ?? "Brand not found" } },
      { status: 500 },
    );
  }

  const clientId = brand.client_id as string;

  const [
    { data: roles, error: rolesError },
    { data: assignments, error: assignmentsError },
  ] = await Promise.all([
    supabase.from("agency_roles").select("id, slug, name"),
    supabase
      .from("client_assignments")
      .select("id, role_id, team_member_id, brand_id")
      .eq("client_id", clientId)
      .or(`brand_id.eq.${brandId},brand_id.is.null`),
  ]);

  const error = rolesError ?? assignmentsError;
  if (error) {
    return NextResponse.json(
      { error: { code: "server_error", message: error.message } },
      { status: 500 },
    );
  }

  const rolesById = new Map(
    (roles ?? []).map((role) => [role.id as string, { slug: role.slug as string, name: role.name as string }]),
  );

  const brandAssignmentByRoleId = new Map<string, { teamMemberId: string }>();
  const clientAssignmentByRoleId = new Map<string, { teamMemberId: string }>();

  for (const assignment of assignments ?? []) {
    const roleId = assignment.role_id as string;
    const teamMemberId = assignment.team_member_id as string;
    const isBrand = (assignment.brand_id as string | null) !== null;
    if (isBrand) brandAssignmentByRoleId.set(roleId, { teamMemberId });
    else clientAssignmentByRoleId.set(roleId, { teamMemberId });
  }

  const resolvedRoleAssignments: Array<{
    roleId: string;
    roleSlug: string;
    roleName: string;
    teamMemberId: string;
  }> = [];

  for (const [roleId, roleMeta] of rolesById.entries()) {
    const brandAssignment = brandAssignmentByRoleId.get(roleId);
    const clientAssignment = clientAssignmentByRoleId.get(roleId);
    const teamMemberId = brandAssignment?.teamMemberId ?? clientAssignment?.teamMemberId ?? null;
    if (!teamMemberId) continue;

    resolvedRoleAssignments.push({
      roleId,
      roleSlug: roleMeta.slug,
      roleName: roleMeta.name,
      teamMemberId,
    });
  }

  const uniqueTeamMemberIds = Array.from(
    new Set(resolvedRoleAssignments.map((entry) => entry.teamMemberId)),
  );

  const { data: teamMembers, error: teamError } = uniqueTeamMemberIds.length
    ? await supabase
        .from("profiles")
        .select("id, email, display_name, full_name")
        .in("id", uniqueTeamMemberIds)
    : { data: [], error: null };

  if (teamError) {
    return NextResponse.json(
      { error: { code: "server_error", message: teamError.message } },
      { status: 500 },
    );
  }

  const teamMemberById = new Map(
    (teamMembers ?? []).map((member) => [
      member.id as string,
      {
        email: member.email as string,
        name: ((member.display_name as string | null) ?? (member.full_name as string | null)) ?? null,
      },
    ]),
  );

  return NextResponse.json({
    clientId,
    brandId,
    roles: resolvedRoleAssignments
      .map((entry) => {
        const member = teamMemberById.get(entry.teamMemberId);
        if (!member) return null;
        return {
          roleSlug: entry.roleSlug,
          roleName: entry.roleName,
          teamMemberId: entry.teamMemberId,
          teamMemberName: member.name,
          teamMemberEmail: member.email,
        };
      })
      .filter((value) => value !== null),
  });
}

