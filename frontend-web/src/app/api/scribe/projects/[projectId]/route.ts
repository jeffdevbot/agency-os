import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";

type ScribeProjectStatus = "draft" | "stage_a_approved" | "archived";

interface FormatPreferences {
  bulletCapsHeaders?: boolean;
  descriptionParagraphs?: boolean;
}

interface ProjectRow {
  id: string;
  created_by: string;
  name: string;
  locale: string | null;
  category: string | null;
  sub_category: string | null;
  format_preferences: FormatPreferences | null;
  status: string;
  created_at: string;
  updated_at: string;
}

const isUuid = (value: unknown): value is string =>
  typeof value === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);

const isStatus = (value: string): value is ScribeProjectStatus =>
  value === "draft" || value === "stage_a_approved" || value === "archived";

const mapProjectRow = (row: ProjectRow) => ({
  id: row.id,
  name: row.name,
  locale: row.locale,
  category: row.category,
  subCategory: row.sub_category,
  formatPreferences: row.format_preferences,
  status: isStatus(row.status) ? row.status : null,
  createdAt: row.created_at,
  updatedAt: row.updated_at,
});

const canTransition = (current: ScribeProjectStatus, next: ScribeProjectStatus) => {
  if (current === next) return true;
  if (next === "archived") return true; // archive allowed from any state
  if (current === "draft" && next === "stage_a_approved") return true;
  if (current === "stage_a_approved" && next === "draft") return true;
  return false;
};

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ projectId?: string }> },
) {
  const { projectId } = await context.params;
  if (!projectId || !isUuid(projectId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "invalid project id" } },
      { status: 400 },
    );
  }

  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Unauthorized" } }, { status: 401 });
  }

  const { data, error } = await supabase
    .from("scribe_projects")
    .select("id, created_by, name, locale, category, sub_category, format_preferences, status, created_at, updated_at")
    .eq("id", projectId)
    .eq("created_by", session.user.id)
    .single();

  if (error || !data) {
    const status = error?.code === "PGRST116" ? 404 : 500;
    return NextResponse.json(
      { error: { code: "not_found", message: error?.message ?? "Project not found" } },
      { status },
    );
  }

  return NextResponse.json(mapProjectRow(data));
}

interface UpdateProjectPayload {
  name?: string;
  locale?: string;
  category?: string | null;
  subCategory?: string | null;
  formatPreferences?: FormatPreferences | null;
  status?: ScribeProjectStatus;
}

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ projectId?: string }> },
) {
  const { projectId } = await context.params;
  if (!projectId || !isUuid(projectId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "invalid project id" } },
      { status: 400 },
    );
  }

  const payload = (await request.json()) as UpdateProjectPayload;
  const updates: Record<string, unknown> = {};

  if (payload.name !== undefined) updates.name = payload.name?.trim();
  if (payload.locale !== undefined) updates.locale = payload.locale;
  if (payload.category !== undefined) updates.category = payload.category;
  if (payload.subCategory !== undefined) updates.sub_category = payload.subCategory;
  if (payload.formatPreferences !== undefined) updates.format_preferences = payload.formatPreferences;

  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Unauthorized" } }, { status: 401 });
  }

  const { data: existing, error: fetchError } = await supabase
    .from("scribe_projects")
    .select("id, created_by, status, updated_at")
    .eq("id", projectId)
    .eq("created_by", session.user.id)
    .single();

  if (fetchError || !existing) {
    const status = fetchError?.code === "PGRST116" ? 404 : 500;
    return NextResponse.json(
      { error: { code: "not_found", message: fetchError?.message ?? "Project not found" } },
      { status },
    );
  }

  const currentStatus = isStatus(existing.status) ? existing.status : "draft";

  if (currentStatus === "archived") {
    return NextResponse.json(
      { error: { code: "forbidden", message: "Archived projects are read-only" } },
      { status: 403 },
    );
  }

  if (payload.status !== undefined) {
    if (!isStatus(payload.status)) {
      return NextResponse.json(
        { error: { code: "validation_error", message: "invalid status" } },
        { status: 400 },
      );
    }
    if (!canTransition(currentStatus, payload.status)) {
      return NextResponse.json(
        { error: { code: "conflict", message: "invalid status transition" } },
        { status: 409 },
      );
    }
    updates.status = payload.status;
  }

  if (Object.keys(updates).length === 0) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "No valid fields provided" } },
      { status: 400 },
    );
  }

  updates.updated_at = new Date().toISOString();

  const { data, error } = await supabase
    .from("scribe_projects")
    .update(updates)
    .eq("id", projectId)
    .eq("created_by", session.user.id)
    .select("id, created_by, name, locale, category, sub_category, format_preferences, status, created_at, updated_at")
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: { code: "server_error", message: error?.message ?? "Unable to update project" } },
      { status: 500 },
    );
  }

  return NextResponse.json(mapProjectRow(data));
}
