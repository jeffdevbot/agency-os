import { NextResponse, type NextRequest } from "next/server";
import type {
  ComposerProject,
  ComposerProjectStatus,
  HighlightAttributePreference,
  StrategyType,
} from "@agency/lib/composer/types";
import { DEFAULT_COMPOSER_ORG_ID } from "@/lib/composer/constants";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { isUuid, resolveComposerOrgIdFromSession } from "@/lib/composer/serverUtils";

const PROJECT_COLUMNS =
  "id, organization_id, created_by, client_name, project_name, marketplaces, category, strategy_type, active_step, status, brand_tone, what_not_to_say, supplied_info, faq, product_brief, highlight_attributes, last_saved_at, created_at";

interface ProjectRow {
  id: string;
  organization_id: string;
  created_by: string | null;
  client_name: string | null;
  project_name: string;
  marketplaces: string[] | null;
  category: string | null;
  strategy_type: string | null;
  active_step: string | null;
  status: string | null;
  brand_tone: string | null;
  what_not_to_say: string[] | null;
  supplied_info: Record<string, unknown> | null;
  faq: Array<{ question: string; answer?: string }> | null;
  product_brief: Record<string, unknown> | null;
  highlight_attributes: unknown;
  last_saved_at: string | null;
  created_at: string;
}

const normalizeHighlightAttributes = (
  raw: unknown,
): HighlightAttributePreference[] => {
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw
    .map((entry) => {
      if (!entry || typeof entry !== "object") return null;
      const key = typeof (entry as { key?: unknown }).key === "string"
        ? (entry as { key: string }).key
        : null;
      if (!key) return null;
      const surfacesRecord =
        (entry as { surfaces?: Record<string, unknown> }).surfaces ?? {};
      const surfaces = {
        title: Boolean((surfacesRecord as Record<string, unknown>).title),
        bullets: Boolean((surfacesRecord as Record<string, unknown>).bullets),
        description: Boolean(
          (surfacesRecord as Record<string, unknown>).description,
        ),
        backend_keywords: Boolean(
          (surfacesRecord as Record<string, unknown>).backend_keywords,
        ),
      };
      return { key, surfaces };
    })
    .filter((value): value is HighlightAttributePreference => value !== null);
};

const isStrategyType = (value: string | null): value is StrategyType =>
  value === "variations" || value === "distinct";

const isComposerProjectStatus = (value: string | null): value is ComposerProjectStatus =>
  value === "draft" || value === "active" || value === "completed" || value === "archived";

const mapRowToComposerProject = (row: ProjectRow): ComposerProject => ({
  id: row.id,
  organizationId: row.organization_id,
  createdBy: row.created_by,
  clientName: row.client_name,
  projectName: row.project_name,
  marketplaces: row.marketplaces ?? [],
  category: row.category,
  strategyType: isStrategyType(row.strategy_type) ? row.strategy_type : null,
  activeStep: row.active_step,
  status: isComposerProjectStatus(row.status) ? row.status : null,
  brandTone: row.brand_tone,
  whatNotToSay: row.what_not_to_say,
  suppliedInfo: row.supplied_info ?? {},
  faq: row.faq,
  productBrief: row.product_brief ?? {},
  highlightAttributes: normalizeHighlightAttributes(row.highlight_attributes),
  lastSavedAt: row.last_saved_at,
  createdAt: row.created_at,
});

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ projectId?: string }> },
) {
  const { projectId } = await context.params;
  if (!projectId || !isUuid(projectId)) {
    return NextResponse.json(
      { error: "invalid_project_id", projectId: projectId ?? null },
      { status: 400 },
    );
  }
  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const organizationId =
    resolveComposerOrgIdFromSession(session, { fallbackToDefault: true }) ?? DEFAULT_COMPOSER_ORG_ID;

  const { data, error } = await supabase
    .from("composer_projects")
    .select(PROJECT_COLUMNS)
    .eq("id", projectId)
    .eq("organization_id", organizationId)
    .single();

  if (error || !data) {
    const status = error?.code === "PGRST116" ? 404 : 500;
    return NextResponse.json({ error: error?.message ?? "Project not found" }, { status });
  }

  return NextResponse.json(mapRowToComposerProject(data));
}

interface UpdateComposerProjectPayload {
  projectName?: string;
  clientName?: string;
  marketplaces?: string[];
  category?: string | null;
  strategyType?: string | null;
  status?: string | null;
  activeStep?: string | null;
  brandTone?: string | null;
  whatNotToSay?: string[] | null;
  suppliedInfo?: Record<string, unknown>;
  faq?: Array<{ question: string; answer?: string }> | null;
  productBrief?: Record<string, unknown>;
  highlightAttributes?: HighlightAttributePreference[];
}

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ projectId?: string }> },
) {
  const { projectId } = await context.params;
  if (!projectId || !isUuid(projectId)) {
    return NextResponse.json(
      { error: "invalid_project_id", projectId: projectId ?? null },
      { status: 400 },
    );
  }
  const payload = (await request.json()) as UpdateComposerProjectPayload;
  const updates: Record<string, unknown> = {};

  if (payload.projectName !== undefined) updates.project_name = payload.projectName;
  if (payload.clientName !== undefined) updates.client_name = payload.clientName;
  if (payload.marketplaces !== undefined) updates.marketplaces = payload.marketplaces;
  if (payload.category !== undefined) updates.category = payload.category;
  if (payload.strategyType !== undefined) updates.strategy_type = payload.strategyType;
  if (payload.status !== undefined) updates.status = payload.status;
  if (payload.activeStep !== undefined) updates.active_step = payload.activeStep;
  if (payload.brandTone !== undefined) updates.brand_tone = payload.brandTone;
  if (payload.whatNotToSay !== undefined) updates.what_not_to_say = payload.whatNotToSay;
  if (payload.suppliedInfo !== undefined) updates.supplied_info = payload.suppliedInfo;
  if (payload.faq !== undefined) updates.faq = payload.faq;
  if (payload.productBrief !== undefined) updates.product_brief = payload.productBrief;
  if (payload.highlightAttributes !== undefined) {
    updates.highlight_attributes = payload.highlightAttributes;
  }

  if (Object.keys(updates).length === 0) {
    return NextResponse.json({ error: "No valid fields provided" }, { status: 400 });
  }

  updates.last_saved_at = new Date().toISOString();

  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const organizationId =
    resolveComposerOrgIdFromSession(session, { fallbackToDefault: true }) ?? DEFAULT_COMPOSER_ORG_ID;

  const { data, error } = await supabase
    .from("composer_projects")
    .update(updates)
    .eq("id", projectId)
    .eq("organization_id", organizationId)
    .select(PROJECT_COLUMNS)
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: error?.message ?? "Unable to update project" },
      { status: 500 },
    );
  }

  return NextResponse.json(mapRowToComposerProject(data));
}
