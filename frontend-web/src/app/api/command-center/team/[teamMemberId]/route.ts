import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient, createSupabaseServiceClient } from "@/lib/supabase/serverClient";
import { requireAdmin, requireSession } from "@/lib/command-center/auth";
import { asOptionalString, asStringArray, isUuid } from "@/lib/command-center/validators";

const isEmploymentStatus = (value: string) => ["active", "inactive", "contractor"].includes(value);

interface PatchTeamMemberPayload {
  fullName?: unknown;
  displayName?: unknown;
  clickupUserId?: unknown;
  slackUserId?: unknown;
  isAdmin?: unknown;
  allowedTools?: unknown;
  employmentStatus?: unknown;
}

export async function PATCH(
  request: NextRequest,
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

  const payload = (await request.json()) as PatchTeamMemberPayload;

  const fullName = asOptionalString(payload.fullName);
  const displayName = asOptionalString(payload.displayName);
  const clickupUserId = asOptionalString(payload.clickupUserId);
  const slackUserId = asOptionalString(payload.slackUserId);
  const allowedTools = payload.allowedTools === undefined ? undefined : asStringArray(payload.allowedTools);
  const employmentStatus = asOptionalString(payload.employmentStatus);

  if (employmentStatus && !isEmploymentStatus(employmentStatus)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "employmentStatus is invalid" } },
      { status: 400 },
    );
  }

  const update: Record<string, unknown> = {
    full_name: fullName ?? undefined,
    display_name: displayName ?? undefined,
    clickup_user_id: clickupUserId ?? undefined,
    slack_user_id: slackUserId ?? undefined,
  };

  if (payload.isAdmin === true || payload.isAdmin === false) {
    update.is_admin = payload.isAdmin;
  }

  if (allowedTools !== undefined) {
    update.allowed_tools = allowedTools;
  }

  if (employmentStatus) {
    update.employment_status = employmentStatus;
  }

  const { data, error } = await supabase
    .from("profiles")
    .update(update)
    .eq("id", teamMemberId)
    .select(
      "id, auth_user_id, email, full_name, display_name, avatar_url, is_admin, role, allowed_tools, employment_status, bench_status, clickup_user_id, slack_user_id, created_at, updated_at",
    )
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: { code: "server_error", message: error?.message ?? "Unable to update team member" } },
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

export async function DELETE(
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

  const { data: profile, error: profileError } = await supabase
    .from("profiles")
    .select("id, auth_user_id, employment_status")
    .eq("id", teamMemberId)
    .single();

  if (profileError || !profile) {
    return NextResponse.json(
      { error: { code: "server_error", message: profileError?.message ?? "Team member not found" } },
      { status: 500 },
    );
  }

  if ((profile.auth_user_id as string | null) !== null) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "Cannot delete a linked user; archive instead" } },
      { status: 400 },
    );
  }

  if ((profile.employment_status as string) !== "inactive") {
    return NextResponse.json(
      { error: { code: "validation_error", message: "Team member must be archived before deleting" } },
      { status: 400 },
    );
  }

  const { count, error: assignmentError } = await supabase
    .from("client_assignments")
    .select("id", { count: "exact", head: true })
    .eq("team_member_id", teamMemberId);

  if (assignmentError) {
    return NextResponse.json(
      { error: { code: "server_error", message: assignmentError.message } },
      { status: 500 },
    );
  }

  if ((count ?? 0) > 0) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "Cannot delete team member with assignments; archive instead" } },
      { status: 400 },
    );
  }

  const service = createSupabaseServiceClient();
  const { error } = await service.from("profiles").delete().eq("id", teamMemberId);

  if (error) {
    return NextResponse.json(
      { error: { code: "server_error", message: error.message } },
      { status: 500 },
    );
  }

  return NextResponse.json({ ok: true });
}
