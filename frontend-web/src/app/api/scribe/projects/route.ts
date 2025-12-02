import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { isSupportedLocale, type ScribeLocale } from "@/lib/scribe/locales";

type ScribeProjectStatus =
  | "draft"
  | "stage_a_approved"
  | "stage_b_approved"
  | "stage_c_approved"
  | "approved"
  | "archived";

interface ProjectRow {
  id: string;
  name: string;
  locale: string | null;
  category: string | null;
  sub_category: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

const parseIntParam = (value: string | null, fallback: number) => {
  if (!value) return fallback;
  const parsed = Number.parseInt(value, 10);
  return Number.isNaN(parsed) ? fallback : parsed;
};

const isStatus = (value: string): value is ScribeProjectStatus =>
  value === "draft" ||
  value === "stage_a_approved" ||
  value === "stage_b_approved" ||
  value === "stage_c_approved" ||
  value === "approved" ||
  value === "archived";

const mapProjectRow = (row: ProjectRow) => ({
  id: row.id,
  name: row.name,
  locale: isSupportedLocale(row.locale) ? row.locale : "en-US",
  category: row.category,
  subCategory: row.sub_category,
  status: isStatus(row.status) ? row.status : null,
  createdAt: row.created_at,
  updatedAt: row.updated_at,
});

export async function GET(request: NextRequest) {
  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Unauthorized" } }, { status: 401 });
  }

  const url = new URL(request.url);
  const page = Math.max(1, parseIntParam(url.searchParams.get("page"), 1));
  const pageSize = Math.max(1, parseIntParam(url.searchParams.get("pageSize"), 20));
  const sort = url.searchParams.get("sort") === "created_at" ? "created_at" : "updated_at";
  const from = (page - 1) * pageSize;
  const to = from + pageSize - 1;

  const { data, error, count } = await supabase
    .from("scribe_projects")
    .select("id, name, locale, category, sub_category, status, created_at, updated_at", { count: "exact" })
    .eq("created_by", session.user.id)
    .order(sort, { ascending: false, nullsFirst: false })
    .range(from, to);

  if (error) {
    return NextResponse.json(
      { error: { code: "server_error", message: error.message } },
      { status: 500 },
    );
  }

  const projects = (data ?? []).map(mapProjectRow);

  return NextResponse.json({
    projects,
    page,
    pageSize,
    total: count ?? 0,
  });
}

interface CreateProjectPayload {
  name?: string;
  locale?: string;
  category?: string | null;
  subCategory?: string | null;
}

export async function POST(request: NextRequest) {
  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Unauthorized" } }, { status: 401 });
  }

  const payload = (await request.json()) as CreateProjectPayload;
  const name = payload.name?.trim();
  const locale: ScribeLocale = isSupportedLocale(payload.locale) ? payload.locale : "en-US";

  if (!name) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "name is required" } },
      { status: 400 },
    );
  }

  const now = new Date().toISOString();

  const { data, error } = await supabase
    .from("scribe_projects")
    .insert({
      name,
      locale,
      category: payload.category ?? null,
      sub_category: payload.subCategory ?? null,
      status: "draft",
      created_by: session.user.id,
      created_at: now,
      updated_at: now,
    })
    .select("id, name, locale, category, sub_category, status, created_at, updated_at")
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: { code: "server_error", message: error?.message ?? "Unable to create project" } },
      { status: 500 },
    );
  }

  return NextResponse.json(mapProjectRow(data));
}
