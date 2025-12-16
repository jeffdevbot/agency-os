import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { requireAdmin, requireSession } from "@/lib/command-center/auth";
import { asOptionalString, asStringArray } from "@/lib/command-center/validators";

const isEmail = (value: string) =>
  /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/.test(value);

export async function GET() {
  const supabase = await createSupabaseRouteClient();
  const sessionResult = await requireSession(supabase);
  if (sessionResult.errorResponse) return sessionResult.errorResponse;

  const adminResult = await requireAdmin(supabase, sessionResult.user);
  if (adminResult.errorResponse) return adminResult.errorResponse;

  const { data, error } = await supabase
    .from("profiles")
    .select(
      "id, auth_user_id, email, display_name, full_name, avatar_url, is_admin, role, allowed_tools, employment_status, bench_status, clickup_user_id, slack_user_id, created_at, updated_at",
    )
    .order("display_name", { ascending: true, nullsFirst: false });

  if (error) {
    return NextResponse.json(
      { error: { code: "server_error", message: error.message } },
      { status: 500 },
    );
  }

  const teamMembers =
    (data ?? []).map((row) => ({
      id: row.id as string,
      authUserId: (row.auth_user_id as string | null) ?? null,
      email: row.email as string,
      displayName: (row.display_name as string | null) ?? null,
      fullName: (row.full_name as string | null) ?? null,
      avatarUrl: (row.avatar_url as string | null) ?? null,
      isAdmin: Boolean(row.is_admin),
      role: row.role as string,
      allowedTools: (row.allowed_tools as string[] | null) ?? [],
      employmentStatus: row.employment_status as string,
      benchStatus: row.bench_status as string,
      clickupUserId: (row.clickup_user_id as string | null) ?? null,
      slackUserId: (row.slack_user_id as string | null) ?? null,
      createdAt: row.created_at as string,
      updatedAt: row.updated_at as string,
    })) ?? [];

  return NextResponse.json({ teamMembers });
}

interface CreateGhostProfilePayload {
  email?: unknown;
  fullName?: unknown;
  displayName?: unknown;
  clickupUserId?: unknown;
  slackUserId?: unknown;
  isAdmin?: unknown;
  allowedTools?: unknown;
  employmentStatus?: unknown;
}

export async function POST(request: NextRequest) {
  const supabase = await createSupabaseRouteClient();
  const sessionResult = await requireSession(supabase);
  if (sessionResult.errorResponse) return sessionResult.errorResponse;

  const adminResult = await requireAdmin(supabase, sessionResult.user);
  if (adminResult.errorResponse) return adminResult.errorResponse;

  const payload = (await request.json()) as CreateGhostProfilePayload;
  if (process.env.NODE_ENV !== "production") {
    console.log("[command-center][team][create] payload.email=", payload.email);
  }
  const rawEmail = asOptionalString(payload.email);
  if (!rawEmail) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "email is required" } },
      { status: 400 },
    );
  }

  const email = rawEmail.toLowerCase();
  if (!isEmail(email)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "email is invalid" } },
      { status: 400 },
    );
  }

  const fullName = asOptionalString(payload.fullName);
  const displayName = asOptionalString(payload.displayName) ?? fullName;
  const clickupUserId = asOptionalString(payload.clickupUserId);
  const slackUserId = asOptionalString(payload.slackUserId);
  const allowedTools = asStringArray(payload.allowedTools);
  const employmentStatus = asOptionalString(payload.employmentStatus);
  const isAdmin = payload.isAdmin === true;

  if (employmentStatus && !["active", "inactive", "contractor"].includes(employmentStatus)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "employmentStatus is invalid" } },
      { status: 400 },
    );
  }

  const { data, error } = await supabase
    .from("profiles")
    .insert({
      id: crypto.randomUUID(),
      auth_user_id: null,
      email,
      full_name: fullName,
      display_name: displayName,
      is_admin: isAdmin,
      clickup_user_id: clickupUserId,
      slack_user_id: slackUserId,
      allowed_tools: allowedTools,
      employment_status: employmentStatus ?? undefined,
    })
    .select(
      "id, auth_user_id, email, full_name, display_name, avatar_url, is_admin, role, allowed_tools, employment_status, bench_status, clickup_user_id, slack_user_id, created_at, updated_at",
    )
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: { code: "server_error", message: error?.message ?? "Unable to create team member" } },
      { status: 500 },
    );
  }

  const teamMember = {
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
  };

  return NextResponse.json({ teamMember }, { status: 201 });
}
