import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";
import { createRouteHandlerClient } from "@supabase/auth-helpers-nextjs";
import type { Session } from "@supabase/supabase-js";
import { DEFAULT_COMPOSER_ORG_ID } from "@/lib/composer/constants";
import type { ISODateString, StrategyType } from "@agency/lib/composer/types";
import { PROJECTS_PAGE_SIZE } from "@/lib/composer/projectUtils";
import type {
  CreateProjectPayload,
  ProjectListResponse,
  ProjectSummary,
} from "@/lib/composer/projectSummary";

interface ProjectRow {
  id: string;
  project_name: string;
  client_name: string | null;
  marketplaces: string[] | null;
  strategy_type: StrategyType | null;
  status: string | null;
  active_step: string | null;
  created_at: ISODateString;
  last_saved_at: ISODateString | null;
}

const mapProjectRowToSummary = (row: ProjectRow): ProjectSummary => ({
  id: row.id,
  projectName: row.project_name,
  clientName: row.client_name,
  marketplaces: row.marketplaces ?? [],
  strategyType: row.strategy_type,
  status: row.status,
  activeStep: row.active_step,
  createdAt: row.created_at,
  lastEditedAt: row.last_saved_at,
});

const parseNumber = (value: string | null, fallback: number): number => {
  if (!value) return fallback;
  const parsed = Number.parseInt(value, 10);
  return Number.isNaN(parsed) ? fallback : parsed;
};

const resolveComposerOrgIdFromSession = (session: Session | null): string => {
  const userRecord = session?.user as Record<string, unknown> | undefined;
  const directField = userRecord?.org_id;
  if (typeof directField === "string" && directField.length > 0) {
    return directField;
  }
  const metadataOrgId =
    (session?.user?.app_metadata?.org_id as string | undefined) ??
    (session?.user?.user_metadata?.org_id as string | undefined) ??
    (session?.user?.app_metadata?.organization_id as string | undefined) ??
    (session?.user?.user_metadata?.organization_id as string | undefined);
  if (metadataOrgId && metadataOrgId.length > 0) {
    return metadataOrgId;
  }
  return DEFAULT_COMPOSER_ORG_ID;
};

export async function GET(request: NextRequest) {
  const cookieStore = await cookies();
  const supabase = createRouteHandlerClient({
    cookies: () => cookieStore,
  });
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const url = new URL(request.url);
  const search = url.searchParams.get("search")?.trim() ?? "";
  const status = url.searchParams.get("status");
  const strategy = url.searchParams.get("strategy");
  const page = Math.max(1, parseNumber(url.searchParams.get("page"), 1));
  const pageSize = Math.max(1, parseNumber(url.searchParams.get("pageSize"), PROJECTS_PAGE_SIZE));
  const from = (page - 1) * pageSize;
  const to = from + pageSize - 1;

  let query = supabase
    .from("composer_projects")
    .select(
      "id, project_name, client_name, marketplaces, strategy_type, status, active_step, created_at, last_saved_at",
      { count: "exact" },
    )
    .order("last_saved_at", { ascending: false, nullsFirst: false })
    .range(from, to);

  if (search) {
    const pattern = `%${search.replace(/%/g, "").replace(/_/g, "")}%`;
    query = query.or(
      `project_name.ilike.${pattern},client_name.ilike.${pattern}`,
    );
  }

  if (status && status !== "all") {
    query = query.eq("status", status);
  }

  if (strategy && strategy !== "all") {
    query = query.eq("strategy_type", strategy);
  }

  const { data, error, count } = await query;

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const projects = (data ?? []).map(mapProjectRowToSummary);

  const response: ProjectListResponse = {
    projects,
    page,
    pageSize,
    total: count ?? 0,
  };

  return NextResponse.json(response);
}

export async function POST(request: NextRequest) {
  const cookieStore = await cookies();
  const supabase = createRouteHandlerClient({
    cookies: () => cookieStore,
  });
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const payload = (await request.json()) as CreateProjectPayload;
  const projectName = payload.projectName?.trim();

  if (!projectName) {
    return NextResponse.json({ error: "projectName is required" }, { status: 400 });
  }

  const organizationId = resolveComposerOrgIdFromSession(session);

  const now = new Date().toISOString();
  const insertResult = await supabase
    .from("composer_projects")
    .insert({
      organization_id: organizationId,
      created_by: session.user.id,
      client_name: payload.clientName ?? null,
      project_name: projectName,
      marketplaces: payload.marketplaces ?? [],
      strategy_type: null,
      status: "draft",
      active_step: "product_info",
      last_saved_at: now,
    })
    .select(
      "id, project_name, client_name, marketplaces, strategy_type, status, active_step, created_at, last_saved_at",
    )
    .single();

  if (insertResult.error || !insertResult.data) {
    return NextResponse.json(
      { error: insertResult.error?.message ?? "Unable to create project" },
      { status: 500 },
    );
  }

  return NextResponse.json(mapProjectRowToSummary(insertResult.data));
}
