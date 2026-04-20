import "server-only";

import { createSupabaseServiceClient } from "@/lib/supabase/serverClient";
import type { ClientProfileSummary } from "@/app/reports/_lib/reportClientData";
import type { WbrProfile } from "@/app/reports/wbr/_lib/wbrApi";

import { canAccessNgram2, NGRAM2_TOOL_SLUG, normalizeAllowedTools } from "./accessRules";

type ServiceClient = ReturnType<typeof createSupabaseServiceClient>;

type AccessProfile = {
  id: string;
  isAdmin: boolean;
  allowedTools: string[];
};

type AccessState = {
  profile: AccessProfile;
  assignedClientIds: string[];
};

export class NgramAccessError extends Error {
  status: number;

  constructor(message: string, status = 403) {
    super(message);
    this.name = "NgramAccessError";
    this.status = status;
  }
}

const WBR_PROFILE_SELECT = [
  "id",
  "client_id",
  "marketplace_code",
  "display_name",
  "week_start_day",
  "status",
  "windsor_account_id",
  "amazon_ads_profile_id",
  "amazon_ads_account_id",
  "amazon_ads_country_code",
  "amazon_ads_currency_code",
  "amazon_ads_marketplace_string_id",
  "backfill_start_date",
  "daily_rewrite_days",
  "sp_api_auto_sync_enabled",
  "ads_api_auto_sync_enabled",
  "search_term_auto_sync_enabled",
  "search_term_sb_auto_sync_enabled",
  "search_term_sd_auto_sync_enabled",
  "created_at",
  "updated_at",
].join(",");

const toText = (value: unknown): string => String(value ?? "").trim();

const asBoolean = (value: unknown): boolean => value === true;

const asNumber = (value: unknown): number => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return 0;
};

const parseWbrProfile = (value: Record<string, unknown>): WbrProfile => ({
  id: toText(value.id),
  client_id: toText(value.client_id),
  marketplace_code: toText(value.marketplace_code),
  display_name: toText(value.display_name),
  week_start_day: toText(value.week_start_day).toLowerCase() === "monday" ? "monday" : "sunday",
  status: toText(value.status),
  windsor_account_id: toText(value.windsor_account_id) || null,
  amazon_ads_profile_id: toText(value.amazon_ads_profile_id) || null,
  amazon_ads_account_id: toText(value.amazon_ads_account_id) || null,
  amazon_ads_country_code: toText(value.amazon_ads_country_code) || null,
  amazon_ads_currency_code: toText(value.amazon_ads_currency_code) || null,
  amazon_ads_marketplace_string_id: toText(value.amazon_ads_marketplace_string_id) || null,
  backfill_start_date: toText(value.backfill_start_date) || null,
  daily_rewrite_days: asNumber(value.daily_rewrite_days),
  sp_api_auto_sync_enabled: asBoolean(value.sp_api_auto_sync_enabled),
  ads_api_auto_sync_enabled: asBoolean(value.ads_api_auto_sync_enabled),
  search_term_auto_sync_enabled: asBoolean(value.search_term_auto_sync_enabled),
  search_term_sb_auto_sync_enabled: asBoolean(value.search_term_sb_auto_sync_enabled),
  search_term_sd_auto_sync_enabled: asBoolean(value.search_term_sd_auto_sync_enabled),
  created_at: toText(value.created_at) || null,
  updated_at: toText(value.updated_at) || null,
});

const loadAccessProfile = async (
  service: ServiceClient,
  authUserId: string,
): Promise<AccessProfile | null> => {
  const { data, error } = await service
    .from("profiles")
    .select("id, is_admin, allowed_tools")
    .eq("id", authUserId)
    .limit(1)
    .maybeSingle();

  if (error) {
    throw new Error(error.message);
  }

  if (!data || typeof data !== "object") {
    return null;
  }

  return {
    id: toText((data as Record<string, unknown>).id),
    isAdmin: Boolean((data as Record<string, unknown>).is_admin),
    allowedTools: normalizeAllowedTools((data as Record<string, unknown>).allowed_tools),
  };
};

const loadAssignedClientIds = async (
  service: ServiceClient,
  teamMemberId: string,
): Promise<string[]> => {
  const { data, error } = await service
    .from("client_assignments")
    .select("client_id")
    .eq("team_member_id", teamMemberId);

  if (error) {
    throw new Error(error.message);
  }

  return Array.from(
    new Set(
      (Array.isArray(data) ? data : [])
        .map((row) => toText((row as Record<string, unknown>).client_id))
        .filter(Boolean),
    ),
  );
};

export const getNgram2AccessState = async (
  service: ServiceClient,
  authUserId: string,
): Promise<AccessState> => {
  const profile = await loadAccessProfile(service, authUserId);
  if (!profile) {
    throw new NgramAccessError("Your profile could not be found.", 403);
  }

  if (!canAccessNgram2(profile)) {
    throw new NgramAccessError("You do not have access to N-Gram 2.0.", 403);
  }

  const assignedClientIds = profile.isAdmin ? [] : await loadAssignedClientIds(service, profile.id);
  return { profile, assignedClientIds };
};

export const listAccessibleNgram2Summaries = async (
  service: ServiceClient,
  accessState: AccessState,
): Promise<{ summaries: ClientProfileSummary[]; failures: string[] }> => {
  const { profile, assignedClientIds } = accessState;

  if (!profile.isAdmin && assignedClientIds.length === 0) {
    return {
      summaries: [],
      failures: [
        "No client assignments found. Grant the tool here, then assign this teammate to at least one client or brand.",
      ],
    };
  }

  let clientsQuery = service
    .from("agency_clients")
    .select("id, name, status")
    .neq("status", "archived")
    .order("name", { ascending: true });

  if (!profile.isAdmin) {
    clientsQuery = clientsQuery.in("id", assignedClientIds);
  }

  const { data: clientsData, error: clientsError } = await clientsQuery;
  if (clientsError) {
    throw new Error(clientsError.message);
  }

  const clientRows = (Array.isArray(clientsData) ? clientsData : []).filter(
    (row) => Boolean(row) && typeof row === "object" && !Array.isArray(row),
  ) as Record<string, unknown>[];

  const clients = clientRows
    .map((row) => ({
      id: toText(row.id),
      name: toText(row.name),
      status: toText(row.status),
    }))
    .filter((client) => client.id && client.name);

  if (clients.length === 0) {
    return {
      summaries: [],
      failures: ["No active client profiles are available for this teammate."],
    };
  }

  const clientIds = clients.map((client) => client.id);
  const { data: profilesData, error: profilesError } = await service
    .from("wbr_profiles")
    .select(WBR_PROFILE_SELECT)
    .in("client_id", clientIds)
    .order("display_name", { ascending: true });

  if (profilesError) {
    throw new Error(profilesError.message);
  }

  const profilesByClientId = new Map<string, WbrProfile[]>();
  for (const row of Array.isArray(profilesData) ? profilesData : []) {
    if (!row || typeof row !== "object") continue;
    const profileRow = row as Record<string, unknown>;
    const clientId = toText(profileRow.client_id);
    if (!clientId) continue;
    const parsed = parseWbrProfile(profileRow);
    const current = profilesByClientId.get(clientId) ?? [];
    current.push(parsed);
    profilesByClientId.set(clientId, current);
  }

  const summaries = clients
    .map((client) => ({
      client,
      profiles: profilesByClientId.get(client.id) ?? [],
    }))
    .filter((summary) => summary.profiles.length > 0);

  const clientsWithoutProfiles = clients
    .filter((client) => (profilesByClientId.get(client.id) ?? []).length === 0)
    .map((client) => client.name);

  const failures =
    clientsWithoutProfiles.length > 0
      ? [`No WBR marketplaces are configured yet for: ${clientsWithoutProfiles.join(", ")}.`]
      : [];

  return { summaries, failures };
};

export const assertNgram2ProfileAccess = async (
  service: ServiceClient,
  authUserId: string,
  profileId: string,
): Promise<void> => {
  const accessState = await getNgram2AccessState(service, authUserId);
  if (accessState.profile.isAdmin) return;

  const { data, error } = await service
    .from("wbr_profiles")
    .select("id, client_id")
    .eq("id", profileId)
    .limit(1)
    .maybeSingle();

  if (error) {
    throw new Error(error.message);
  }

  if (!data || typeof data !== "object") {
    throw new NgramAccessError("The selected marketplace profile was not found.", 404);
  }

  const clientId = toText((data as Record<string, unknown>).client_id);
  if (!clientId || !accessState.assignedClientIds.includes(clientId)) {
    throw new NgramAccessError("You do not have access to that N-Gram 2.0 marketplace.", 403);
  }
};

export const getNgram2ToolSlug = (): string => NGRAM2_TOOL_SLUG;
