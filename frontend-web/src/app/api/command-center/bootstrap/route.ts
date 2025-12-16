import { NextResponse } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { requireAdmin, requireSession } from "@/lib/command-center/auth";

export async function GET() {
  const supabase = await createSupabaseRouteClient();
  const sessionResult = await requireSession(supabase);
  if (sessionResult.errorResponse) return sessionResult.errorResponse;

  const adminResult = await requireAdmin(supabase, sessionResult.user);
  if (adminResult.errorResponse) return adminResult.errorResponse;

  const [{ data: roles, error: rolesError }, { data: clients, error: clientsError }, { data: teamMembers, error: teamError }, { data: assignments, error: assignmentsError }] =
    await Promise.all([
      supabase.from("agency_roles").select("id, slug, name").order("created_at", { ascending: true }),
      supabase
        .from("agency_clients")
        .select(
          "id, name, status, brands(id, name, clickup_space_id, clickup_list_id, product_keywords, amazon_marketplaces)",
        )
        .order("name", { ascending: true }),
      supabase
        .from("profiles")
        .select(
          "id, email, display_name, full_name, avatar_url, is_admin, allowed_tools, employment_status, bench_status, clickup_user_id, slack_user_id",
        )
        .order("display_name", { ascending: true, nullsFirst: false }),
      supabase
        .from("client_assignments")
        .select("id, client_id, brand_id, team_member_id, role_id, assigned_at, assigned_by"),
    ]);

  const error = rolesError ?? clientsError ?? teamError ?? assignmentsError;
  if (error) {
    return NextResponse.json(
      { error: { code: "server_error", message: error.message } },
      { status: 500 },
    );
  }

  const response = {
    roles: (roles ?? []).map((role) => ({
      id: role.id as string,
      slug: role.slug as string,
      name: role.name as string,
    })),
    clients: (clients ?? []).map((client) => ({
      id: client.id as string,
      name: client.name as string,
      status: client.status as string,
      brands: ((client as { brands?: unknown }).brands as Array<Record<string, unknown>> | null | undefined ?? []).map(
        (brand) => ({
          id: brand.id as string,
          name: brand.name as string,
          clickupSpaceId: (brand.clickup_space_id as string | null) ?? null,
          clickupListId: (brand.clickup_list_id as string | null) ?? null,
          productKeywords: (brand.product_keywords as string[] | null) ?? [],
          amazonMarketplaces: (brand.amazon_marketplaces as string[] | null) ?? [],
        }),
      ),
    })),
    teamMembers: (teamMembers ?? []).map((row) => ({
      id: row.id as string,
      email: row.email as string,
      displayName: (row.display_name as string | null) ?? null,
      fullName: (row.full_name as string | null) ?? null,
      avatarUrl: (row.avatar_url as string | null) ?? null,
      isAdmin: Boolean(row.is_admin),
      allowedTools: (row.allowed_tools as string[] | null) ?? [],
      employmentStatus: row.employment_status as string,
      benchStatus: row.bench_status as string,
      clickupUserId: (row.clickup_user_id as string | null) ?? null,
      slackUserId: (row.slack_user_id as string | null) ?? null,
    })),
    assignments: (assignments ?? []).map((row) => ({
      id: row.id as string,
      clientId: row.client_id as string,
      brandId: (row.brand_id as string | null) ?? null,
      teamMemberId: row.team_member_id as string,
      roleId: row.role_id as string,
      assignedAt: row.assigned_at as string,
      assignedBy: (row.assigned_by as string | null) ?? null,
    })),
  };

  return NextResponse.json({
    ...response,
  });
}
