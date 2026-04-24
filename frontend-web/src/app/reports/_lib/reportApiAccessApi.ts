export type ReportApiAccessConnectProfile = {
  profile_id: string;
  display_name: string;
  marketplace_code: string;
  status: string;
  amazon_ads_profile_id: string | null;
  amazon_ads_account_id: string | null;
};

export type SpApiRegionCode = "NA" | "EU" | "FE";
export type ReportConnectionStatus = "connected" | "error" | "revoked";

export type ReportApiAccessSharedConnection = {
  id: string;
  provider: string;
  connection_status: ReportConnectionStatus;
  external_account_id: string | null;
  region_code: SpApiRegionCode | null;
  connected_at: string | null;
  last_validated_at: string | null;
  last_error: string | null;
  updated_at: string | null;
  lwa_account_hint: string | null;
  access_meta: Record<string, unknown>;
};

export type ReportApiAccessLegacyConnection = {
  profile_id: string;
  connection_status: "connected";
  connected_at: string | null;
  updated_at: string | null;
  lwa_account_hint: string | null;
};

export type AmazonAdsApiAccessSummary = {
  client_id: string;
  client_name: string;
  client_status: string;
  connected: boolean;
  source: "shared" | "legacy" | "none";
  shared_connection: ReportApiAccessSharedConnection | null;
  legacy_connection: ReportApiAccessLegacyConnection | null;
  connect_profiles: ReportApiAccessConnectProfile[];
};

const getBackendUrl = (): string => {
  const url = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (!url) {
    throw new Error("NEXT_PUBLIC_BACKEND_URL is not configured");
  }
  return url.replace(/\/+$/, "");
};

const authJsonHeaders = (token: string): Record<string, string> => ({
  Authorization: `Bearer ${token}`,
  "Content-Type": "application/json",
});

const parseErrorDetail = async (response: Response): Promise<string> => {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    if (typeof body?.message === "string") return body.message;
    return JSON.stringify(body);
  } catch {
    return response.statusText || `HTTP ${response.status}`;
  }
};

const asString = (value: unknown): string => (typeof value === "string" ? value : "");
const asNullableString = (value: unknown): string | null =>
  typeof value === "string" ? value : null;
const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const parseConnectProfile = (value: unknown): ReportApiAccessConnectProfile => {
  if (!isRecord(value)) {
    throw new Error("Invalid Amazon Ads API access profile");
  }

  return {
    profile_id: asString(value.profile_id),
    display_name: asString(value.display_name),
    marketplace_code: asString(value.marketplace_code),
    status: asString(value.status),
    amazon_ads_profile_id: asNullableString(value.amazon_ads_profile_id),
    amazon_ads_account_id: asNullableString(value.amazon_ads_account_id),
  };
};

const parseSharedConnection = (value: unknown): ReportApiAccessSharedConnection | null => {
  if (!isRecord(value)) {
    return null;
  }
  const connectionStatus = asString(value.connection_status);
  const regionCode = asString(value.region_code).toUpperCase();

  return {
    id: asString(value.id),
    provider: asString(value.provider),
    connection_status:
      connectionStatus === "connected" || connectionStatus === "revoked"
        ? connectionStatus
        : "error",
    external_account_id: asNullableString(value.external_account_id),
    region_code:
      regionCode === "NA" || regionCode === "EU" || regionCode === "FE"
        ? regionCode
        : null,
    connected_at: asNullableString(value.connected_at),
    last_validated_at: asNullableString(value.last_validated_at),
    last_error: asNullableString(value.last_error),
    updated_at: asNullableString(value.updated_at),
    lwa_account_hint: asNullableString(value.lwa_account_hint),
    access_meta: isRecord(value.access_meta) ? value.access_meta : {},
  };
};

const parseLegacyConnection = (value: unknown): ReportApiAccessLegacyConnection | null => {
  if (!isRecord(value)) {
    return null;
  }

  return {
    profile_id: asString(value.profile_id),
    connection_status: "connected",
    connected_at: asNullableString(value.connected_at),
    updated_at: asNullableString(value.updated_at),
    lwa_account_hint: asNullableString(value.lwa_account_hint),
  };
};

const parseSummary = (value: unknown): AmazonAdsApiAccessSummary => {
  if (!isRecord(value)) {
    throw new Error("Invalid Amazon Ads API access response");
  }

  const source = asString(value.source);
  return {
    client_id: asString(value.client_id),
    client_name: asString(value.client_name),
    client_status: asString(value.client_status),
    connected: value.connected === true,
    source: source === "shared" || source === "legacy" ? source : "none",
    shared_connection: parseSharedConnection(value.shared_connection),
    legacy_connection: parseLegacyConnection(value.legacy_connection),
    connect_profiles: Array.isArray(value.connect_profiles)
      ? value.connect_profiles.map(parseConnectProfile)
      : [],
  };
};

export const listAmazonAdsApiAccess = async (token: string): Promise<AmazonAdsApiAccessSummary[]> => {
  const response = await fetch(`${getBackendUrl()}/admin/reports/api-access/amazon-ads/connections`, {
    cache: "no-store",
    headers: authJsonHeaders(token),
  });
  if (!response.ok) {
    throw new Error(await parseErrorDetail(response));
  }

  const body = (await response.json()) as { connections?: unknown[] };
  return Array.isArray(body.connections) ? body.connections.map(parseSummary) : [];
};

// ---------------------------------------------------------------------------
// Amazon Seller API (SP-API)
// ---------------------------------------------------------------------------

export type SpApiConnectionSummary = {
  client_id: string;
  client_name: string;
  client_status: string;
  connected: boolean;
  connection: ReportApiAccessSharedConnection | null;
};

const parseSpApiSummary = (value: unknown): SpApiConnectionSummary => {
  if (!isRecord(value)) {
    throw new Error("Invalid SP-API connection response");
  }

  return {
    client_id: asString(value.client_id),
    client_name: asString(value.client_name),
    client_status: asString(value.client_status),
    connected: value.connected === true,
    connection: parseSharedConnection(value.connection),
  };
};

export const listSpApiConnections = async (
  token: string,
): Promise<SpApiConnectionSummary[]> => {
  const response = await fetch(
    `${getBackendUrl()}/admin/reports/api-access/amazon-spapi/connections`,
    {
      cache: "no-store",
      headers: authJsonHeaders(token),
    },
  );
  if (!response.ok) {
    throw new Error(await parseErrorDetail(response));
  }

  const body = (await response.json()) as { connections?: unknown[] };
  return Array.isArray(body.connections)
    ? body.connections.map(parseSpApiSummary)
    : [];
};

export const createSpApiAuthorizationUrl = async (
  token: string,
  clientId: string,
  regionCode: SpApiRegionCode,
  returnPath = "/reports/client-data-access",
): Promise<string> => {
  const response = await fetch(
    `${getBackendUrl()}/admin/reports/api-access/amazon-spapi/connect`,
    {
      method: "POST",
      cache: "no-store",
      headers: authJsonHeaders(token),
      body: JSON.stringify({
        client_id: clientId,
        region_code: regionCode,
        return_path: returnPath,
      }),
    },
  );
  if (!response.ok) {
    throw new Error(await parseErrorDetail(response));
  }

  const body = (await response.json()) as { authorization_url?: unknown };
  const url = asString(body.authorization_url);
  if (!url) {
    throw new Error("Missing Seller API authorization URL");
  }
  return url;
};

export type SpApiValidateResult = {
  ok: boolean;
  step?: string;
  error?: string;
  region_code?: SpApiRegionCode;
  marketplace_count?: number;
  marketplace_ids?: string[];
};

export const validateSpApiConnection = async (
  token: string,
  clientId: string,
): Promise<SpApiValidateResult> => {
  const response = await fetch(
    `${getBackendUrl()}/admin/reports/api-access/amazon-spapi/validate`,
    {
      method: "POST",
      cache: "no-store",
      headers: authJsonHeaders(token),
      body: JSON.stringify({ client_id: clientId }),
    },
  );
  if (!response.ok) {
    throw new Error(await parseErrorDetail(response));
  }

  return (await response.json()) as SpApiValidateResult;
};

export type SpApiFinanceSmokeResult = {
  ok: boolean;
  step?: string;
  error?: string;
  note?: string;
  region_code?: SpApiRegionCode;
  target_group_id?: string;
  group_count?: number;
  groups?: Record<string, unknown>[];
  transaction_count?: number;
  transactions?: Record<string, unknown>[];
};

export const runSpApiFinanceSmokeTest = async (
  token: string,
  clientId: string,
): Promise<SpApiFinanceSmokeResult> => {
  const response = await fetch(
    `${getBackendUrl()}/admin/reports/api-access/amazon-spapi/finance-smoke-test`,
    {
      method: "POST",
      cache: "no-store",
      headers: authJsonHeaders(token),
      body: JSON.stringify({ client_id: clientId }),
    },
  );
  if (!response.ok) {
    throw new Error(await parseErrorDetail(response));
  }

  return (await response.json()) as SpApiFinanceSmokeResult;
};

// ---------------------------------------------------------------------------
// Amazon Ads
// ---------------------------------------------------------------------------

export const createAmazonAdsAuthorizationUrl = async (
  token: string,
  profileId: string,
  returnPath = "/reports/client-data-access",
  region?: SpApiRegionCode,
): Promise<string> => {
  const response = await fetch(`${getBackendUrl()}/admin/reports/api-access/amazon-ads/connect`, {
    method: "POST",
    cache: "no-store",
    headers: authJsonHeaders(token),
    body: JSON.stringify({
      profile_id: profileId,
      return_path: returnPath,
      ...(region ? { region } : {}),
    }),
  });
  if (!response.ok) {
    throw new Error(await parseErrorDetail(response));
  }

  const body = (await response.json()) as { authorization_url?: unknown };
  const url = asString(body.authorization_url);
  if (!url) {
    throw new Error("Missing Amazon Ads authorization URL");
  }
  return url;
};
