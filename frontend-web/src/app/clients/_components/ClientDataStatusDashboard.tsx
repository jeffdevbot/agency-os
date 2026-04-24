import type { SupabaseRouteClient } from "@/lib/supabase/serverClient";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";

type ClientDataStatusDashboardProps = {
  clientId: string;
  supabase?: SupabaseRouteClient;
};

type ApiConnection = {
  provider: "amazon_ads" | "amazon_spapi" | string;
  region_code: string | null;
  external_account_id: string | null;
  connection_status: "connected" | "error" | "revoked" | string;
  last_validated_at: string | null;
  last_error: string | null;
  connected_at: string | null;
};

type WbrProfile = {
  id: string;
  marketplace_code: string;
  display_name: string;
  status: string;
  backfill_start_date: string | null;
  sp_api_auto_sync_enabled: boolean;
  ads_api_auto_sync_enabled: boolean;
  search_term_auto_sync_enabled: boolean;
  search_term_sb_auto_sync_enabled: boolean;
  search_term_sd_auto_sync_enabled: boolean;
};

type Coverage = {
  earliest: string | null;
  latest: string | null;
};

type StreamRow = {
  label: string;
  enabled: boolean;
  syncNote?: string;
  coverage: Coverage;
};

const EMPTY = "—";

const PROVIDERS: Array<{
  key: "amazon_ads" | "amazon_spapi";
  label: string;
}> = [
  { key: "amazon_ads", label: "Amazon Ads" },
  { key: "amazon_spapi", label: "SP-API" },
];

const statusBadgeClass = (status: string | null) => {
  switch (status) {
    case "connected":
      return "border-[#86efac] bg-[#dcfce7] text-[#166534]";
    case "error":
      return "border-[#fecaca] bg-[#fee2e2] text-[#991b1b]";
    case "revoked":
      return "border-slate-200 bg-slate-100 text-slate-500";
    default:
      return "border-slate-300 bg-white text-slate-500";
  }
};

const statusLabel = (status: string | null) => {
  switch (status) {
    case "connected":
      return "Connected";
    case "error":
      return "Error";
    case "revoked":
      return "Revoked";
    default:
      return "Not connected";
  }
};

const syncBadgeClass = (enabled: boolean) =>
  enabled
    ? "border-[#86efac] bg-[#16a34a] text-white"
    : "border-slate-300 bg-white text-slate-500";

const formatDate = (value: string | null) => {
  if (!value) return EMPTY;
  const parsed = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-CA", {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(parsed);
};

const formatRelativeTime = (value: string | null) => {
  if (!value) return "Never validated";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;

  const deltaSeconds = Math.round((parsed - Date.now()) / 1000);
  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  const absSeconds = Math.abs(deltaSeconds);
  if (absSeconds < 60) return formatter.format(deltaSeconds, "second");

  const deltaMinutes = Math.round(deltaSeconds / 60);
  if (Math.abs(deltaMinutes) < 60) return formatter.format(deltaMinutes, "minute");

  const deltaHours = Math.round(deltaMinutes / 60);
  if (Math.abs(deltaHours) < 24) return formatter.format(deltaHours, "hour");

  const deltaDays = Math.round(deltaHours / 24);
  if (Math.abs(deltaDays) < 30) return formatter.format(deltaDays, "day");

  const deltaMonths = Math.round(deltaDays / 30);
  if (Math.abs(deltaMonths) < 12) return formatter.format(deltaMonths, "month");

  return formatter.format(Math.round(deltaMonths / 12), "year");
};

const formatDaysSinceLatest = (value: string | null) => {
  if (!value) return EMPTY;
  const latest = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(latest.getTime())) return EMPTY;

  const now = new Date();
  const todayUtc = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  const latestUtc = Date.UTC(
    latest.getUTCFullYear(),
    latest.getUTCMonth(),
    latest.getUTCDate(),
  );
  const days = Math.max(0, Math.floor((todayUtc - latestUtc) / 86_400_000));
  return days === 1 ? "1 day" : `${days} days`;
};

const truncateError = (value: string | null) => {
  if (!value) return null;
  const trimmed = value.trim();
  return trimmed.length > 160 ? `${trimmed.slice(0, 157)}...` : trimmed;
};

async function fetchCoverage(
  supabase: SupabaseRouteClient,
  tableName: string,
  dateColumn: string,
  profileId: string,
  adProduct?: string,
): Promise<Coverage> {
  let query = supabase
    .from(tableName)
    .select(`earliest:${dateColumn}.min(),latest:${dateColumn}.max()`)
    .eq("profile_id", profileId);

  if (adProduct) {
    query = query.eq("ad_product", adProduct);
  }

  const { data, error } = await query.maybeSingle();
  if (error || !data || typeof data !== "object") {
    return { earliest: null, latest: null };
  }

  const row = data as Record<string, unknown>;
  return {
    earliest: typeof row.earliest === "string" ? row.earliest : null,
    latest: typeof row.latest === "string" ? row.latest : null,
  };
}

async function buildStreamRows(
  supabase: SupabaseRouteClient,
  profile: WbrProfile,
): Promise<StreamRow[]> {
  const [
    business,
    ads,
    searchTermsSp,
    searchTermsSb,
    searchTermsSd,
    inventory,
    returns,
  ] = await Promise.all([
    fetchCoverage(supabase, "wbr_business_asin_daily", "report_date", profile.id),
    fetchCoverage(supabase, "wbr_ads_campaign_daily", "report_date", profile.id),
    fetchCoverage(
      supabase,
      "search_term_daily_facts",
      "report_date",
      profile.id,
      "SPONSORED_PRODUCTS",
    ),
    fetchCoverage(
      supabase,
      "search_term_daily_facts",
      "report_date",
      profile.id,
      "SPONSORED_BRANDS",
    ),
    fetchCoverage(
      supabase,
      "search_term_daily_facts",
      "report_date",
      profile.id,
      "SPONSORED_DISPLAY",
    ),
    fetchCoverage(supabase, "wbr_inventory_asin_snapshots", "snapshot_date", profile.id),
    fetchCoverage(supabase, "wbr_returns_asin_daily", "return_date", profile.id),
  ]);

  return [
    {
      label: "Business",
      enabled: profile.sp_api_auto_sync_enabled,
      coverage: business,
    },
    {
      label: "Ads",
      enabled: profile.ads_api_auto_sync_enabled,
      coverage: ads,
    },
    {
      label: "Search Terms (SP)",
      enabled: profile.search_term_auto_sync_enabled,
      coverage: searchTermsSp,
    },
    {
      label: "Search Terms (SB)",
      enabled: profile.search_term_sb_auto_sync_enabled,
      coverage: searchTermsSb,
    },
    {
      label: "Search Terms (SD)",
      enabled: profile.search_term_sd_auto_sync_enabled,
      coverage: searchTermsSd,
    },
    {
      label: "Inventory",
      enabled: profile.sp_api_auto_sync_enabled,
      syncNote: "inherits SP",
      coverage: inventory,
    },
    {
      label: "Returns",
      enabled: profile.sp_api_auto_sync_enabled,
      syncNote: "inherits SP",
      coverage: returns,
    },
  ];
}

export default async function ClientDataStatusDashboard({
  clientId,
  supabase: providedSupabase,
}: ClientDataStatusDashboardProps) {
  const supabase = providedSupabase ?? (await createSupabaseRouteClient());

  const [connectionsResult, profilesResult] = await Promise.all([
    supabase
      .from("report_api_connections")
      .select(
        "provider, region_code, external_account_id, connection_status, last_validated_at, last_error, connected_at",
      )
      .eq("client_id", clientId)
      .order("provider", { ascending: true })
      .order("region_code", { ascending: true }),
    supabase
      .from("wbr_profiles")
      .select(
        "id, marketplace_code, display_name, status, backfill_start_date, sp_api_auto_sync_enabled, ads_api_auto_sync_enabled, search_term_auto_sync_enabled, search_term_sb_auto_sync_enabled, search_term_sd_auto_sync_enabled",
      )
      .eq("client_id", clientId)
      .eq("status", "active")
      .order("marketplace_code", { ascending: true })
      .order("display_name", { ascending: true }),
  ]);

  const connections = (connectionsResult.data ?? []) as ApiConnection[];
  const profiles = (profilesResult.data ?? []) as WbrProfile[];
  const connectionsByProvider = new Map<string, ApiConnection[]>();
  connections.forEach((connection) => {
    const current = connectionsByProvider.get(connection.provider) ?? [];
    current.push(connection);
    connectionsByProvider.set(connection.provider, current);
  });

  const profileRows = await Promise.all(
    profiles.map(async (profile) => ({
      profile,
      streams: await buildStreamRows(supabase, profile),
    })),
  );

  return (
    <section className="space-y-6">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[#0a6fd6]">
              Data Status
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-[#0f172a]">
              Connection and sync health
            </h2>
            <p className="mt-2 max-w-3xl text-sm text-[#4c576f]">
              Read-only view of API authorization, nightly sync flags, and the date coverage
              currently available for each marketplace profile.
            </p>
          </div>
        </div>
      </div>

      <div className="rounded-3xl bg-white/95 p-6 shadow-[0_24px_70px_rgba(10,59,130,0.12)] backdrop-blur md:p-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[#0a6fd6]">
              Connections
            </p>
            <h3 className="mt-2 text-xl font-semibold text-[#0f172a]">API authorization</h3>
          </div>
        </div>

        {connectionsResult.error ? (
          <p className="mt-4 rounded-2xl border border-[#fecaca] bg-[#fff1f2] px-4 py-3 text-sm text-[#991b1b]">
            Connection status is unavailable: {connectionsResult.error.message}
          </p>
        ) : connections.length === 0 ? (
          <p className="mt-4 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-[#64748b]">
            No API connections yet. Use the Connect buttons below to authorize.
          </p>
        ) : null}

        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          {PROVIDERS.map((provider) => {
            const providerConnections = connectionsByProvider.get(provider.key) ?? [];
            const rows =
              providerConnections.length > 0
                ? providerConnections
                : [
                    {
                      provider: provider.key,
                      region_code: null,
                      external_account_id: null,
                      connection_status: "not_connected",
                      last_validated_at: null,
                      last_error: null,
                      connected_at: null,
                    },
                  ];

            return (
              <div key={provider.key} className="rounded-2xl border border-slate-200 bg-white p-5">
                <p className="text-base font-semibold text-[#0f172a]">{provider.label}</p>
                <div className="mt-4 space-y-3">
                  {rows.map((connection, index) => {
                    const status = connection.connection_status ?? "not_connected";
                    const errorText = status === "error" ? truncateError(connection.last_error) : null;
                    return (
                      <div
                        key={`${provider.key}-${connection.region_code ?? "none"}-${index}`}
                        className="rounded-xl border border-slate-100 bg-[#f8fbff] px-4 py-3"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="text-sm font-medium text-[#0f172a]">
                              {connection.region_code ?? "No region"}
                            </p>
                            <p className="mt-1 text-xs text-[#64748b]">
                              {connection.external_account_id ?? "No external account recorded"}
                            </p>
                          </div>
                          <span
                            className={`rounded-full border px-3 py-1 text-xs font-semibold ${statusBadgeClass(
                              status,
                            )}`}
                          >
                            {statusLabel(status)}
                          </span>
                        </div>
                        <p className="mt-3 text-xs text-[#64748b]">
                          Last validated: {formatRelativeTime(connection.last_validated_at)}
                        </p>
                        {errorText ? (
                          <p className="mt-2 truncate rounded-lg border border-[#fecaca] bg-white px-3 py-2 text-xs text-[#991b1b]">
                            {errorText}
                          </p>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="rounded-3xl bg-white/95 p-6 shadow-[0_24px_70px_rgba(10,59,130,0.12)] backdrop-blur md:p-8">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[#0a6fd6]">
            Marketplace Profiles
          </p>
          <h3 className="mt-2 text-xl font-semibold text-[#0f172a]">Nightly sync and coverage</h3>
        </div>

        {profilesResult.error ? (
          <p className="mt-4 rounded-2xl border border-[#fecaca] bg-[#fff1f2] px-4 py-3 text-sm text-[#991b1b]">
            Marketplace profiles are unavailable: {profilesResult.error.message}
          </p>
        ) : profiles.length === 0 ? (
          <p className="mt-4 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-[#64748b]">
            No marketplace profiles configured yet. Create one in Reports &gt; WBR.
          </p>
        ) : (
          <div className="mt-5 space-y-5">
            {profileRows.map(({ profile, streams }) => (
              <div key={profile.id} className="rounded-2xl border border-slate-200 bg-white p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h4 className="text-lg font-semibold text-[#0f172a]">
                      {profile.display_name}
                    </h4>
                    <p className="mt-1 text-sm text-[#64748b]">
                      Backfill start target: {formatDate(profile.backfill_start_date)}
                    </p>
                  </div>
                  <span className="rounded-full bg-[#e8eefc] px-3 py-1 text-xs font-semibold text-[#0a6fd6]">
                    {profile.marketplace_code}
                  </span>
                </div>

                <div className="mt-5 overflow-x-auto">
                  <table className="min-w-full divide-y divide-slate-200 text-sm">
                    <thead>
                      <tr className="text-left text-xs font-semibold uppercase tracking-[0.12em] text-[#64748b]">
                        <th className="whitespace-nowrap px-3 py-3">Stream</th>
                        <th className="whitespace-nowrap px-3 py-3">Nightly Sync</th>
                        <th className="whitespace-nowrap px-3 py-3">Earliest Data</th>
                        <th className="whitespace-nowrap px-3 py-3">Latest Data</th>
                        <th className="whitespace-nowrap px-3 py-3">Days Since Latest</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {streams.map((stream) => (
                        <tr key={stream.label} className="text-[#334155]">
                          <td className="whitespace-nowrap px-3 py-3 font-medium text-[#0f172a]">
                            {stream.label}
                          </td>
                          <td className="whitespace-nowrap px-3 py-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <span
                                className={`rounded-full border px-3 py-1 text-xs font-semibold ${syncBadgeClass(
                                  stream.enabled,
                                )}`}
                              >
                                {stream.enabled ? "On" : "Off"}
                              </span>
                              {stream.syncNote ? (
                                <span className="text-xs text-[#64748b]">{stream.syncNote}</span>
                              ) : null}
                            </div>
                          </td>
                          <td className="whitespace-nowrap px-3 py-3">
                            {formatDate(stream.coverage.earliest)}
                          </td>
                          <td className="whitespace-nowrap px-3 py-3">
                            {formatDate(stream.coverage.latest)}
                          </td>
                          <td className="whitespace-nowrap px-3 py-3">
                            {formatDaysSinceLatest(stream.coverage.latest)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
