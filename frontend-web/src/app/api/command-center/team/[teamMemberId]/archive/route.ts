import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { requireAdmin, requireSession } from "@/lib/command-center/auth";
import { isUuid } from "@/lib/command-center/validators";

export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ teamMemberId: string }> },
) {
  const { teamMemberId } = await params;

  if (!isUuid(teamMemberId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "teamMemberId is invalid" } },
      { status: 400 },
    );
  }

  const supabase = await createSupabaseRouteClient();
  const sessionResult = await requireSession(supabase);
  if (sessionResult.errorResponse) return sessionResult.errorResponse;

  const adminResult = await requireAdmin(supabase, sessionResult.user);
  if (adminResult.errorResponse) return adminResult.errorResponse;

  const { data, error } = await supabase
    .from("profiles")
    .update({ employment_status: "inactive" })
    .eq("id", teamMemberId)
    .select(
      "id, auth_user_id, email, full_name, display_name, avatar_url, is_admin, role, allowed_tools, employment_status, bench_status, clickup_user_id, slack_user_id, created_at, updated_at",
    )
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: { code: "server_error", message: error?.message ?? "Unable to archive team member" } },
      { status: 500 },
    );
  }

  return NextResponse.json({
    teamMember: {
      id: data.id as string,
      authUserId: (data.auth_user_id as string | null) ?? null,
      email: data.email as string,
      displayName: (data.display_name as string | null) ?? null,
      fullName: (data.full_name as string | null) ?? null,
      avatarUrl: (data.avatar_url as string | null) ?? null,
      isAdmin: Boolean(data.is_admin),
      role: data.role as string,
      allowedTools: (data.allowed_tools as string[] | null) ?? [],
      employmentStatus: data.employment_status as string,
      benchStatus: data.bench_status as string,
      clickupUserId: (data.clickup_user_id as string | null) ?? null,
      slackUserId: (data.slack_user_id as string | null) ?? null,
      createdAt: data.created_at as string,
      updatedAt: data.updated_at as string,
    },
  });
}
