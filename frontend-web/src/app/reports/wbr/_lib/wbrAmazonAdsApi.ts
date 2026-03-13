export type AmazonAdsConnection = {
  profile_id: string;
  connected_at: string | null;
  lwa_account_hint: string | null;
};

export type AmazonAdsAdvertiserProfile = {
  profileId: number;
  countryCode: string;
  currencyCode: string;
  dailyBudget: number;
  timezone: string;
  accountInfo: {
    marketplaceStringId: string;
    id: string;
    type: string;
    name: string;
  };
};

export type WbrSyncRunStatus = "running" | "success" | "error";
export type WbrSyncJobType = "backfill" | "daily_refresh" | "manual_rerun" | "import";

export type WbrSyncRun = {
  id: string;
  profile_id: string;
  source_type: string;
  job_type: WbrSyncJobType;
  date_from: string | null;
  date_to: string | null;
  status: WbrSyncRunStatus;
  rows_fetched: number;
  rows_loaded: number;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type RunAmazonAdsBackfillRequest = {
  date_from: string;
  date_to: string;
  chunk_days: number;
};

export type RunAmazonAdsChunkResult = {
  run: WbrSyncRun;
  rows_fetched: number;
  rows_loaded: number;
};

export type RunAmazonAdsBackfillResult = {
  profile_id: string;
  job_type: "backfill";
  chunk_days: number;
  date_from: string;
  date_to: string;
  chunks: RunAmazonAdsChunkResult[];
};

export type RunAmazonAdsDailyRefreshResult = {
  profile_id: string;
  job_type: "daily_refresh";
  date_from: string;
  date_to: string;
  chunk: RunAmazonAdsChunkResult;
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

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const asString = (value: unknown): string => (typeof value === "string" ? value : "");
const asNullableString = (value: unknown): string | null =>
  typeof value === "string" ? value : null;
const asNumber = (value: unknown): number => {
  if (typeof value === "number") return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (!Number.isNaN(parsed)) return parsed;
  }
  return 0;
};

const requestJson = async <T>(token: string, path: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(`${getBackendUrl()}${path}`, {
    ...init,
    headers: {
      ...authJsonHeaders(token),
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new Error(detail);
  }

  return (await response.json()) as T;
};

type ConnectResponse = { ok: boolean; authorization_url: string };
type ConnectionStatusResponse = {
  ok: boolean;
  connected: boolean;
  connection: AmazonAdsConnection | null;
};
type ProfilesResponse = { ok: boolean; profiles: AmazonAdsAdvertiserProfile[] };

const parseSyncRun = (value: unknown): WbrSyncRun => {
  if (!isRecord(value)) {
    throw new Error("Invalid WBR sync run response");
  }

  const status = asString(value.status);
  const jobType = asString(value.job_type);

  return {
    id: asString(value.id),
    profile_id: asString(value.profile_id),
    source_type: asString(value.source_type),
    job_type:
      jobType === "daily_refresh" || jobType === "manual_rerun" || jobType === "import"
        ? jobType
        : "backfill",
    date_from: asNullableString(value.date_from),
    date_to: asNullableString(value.date_to),
    status: status === "running" || status === "error" ? status : "success",
    rows_fetched: asNumber(value.rows_fetched),
    rows_loaded: asNumber(value.rows_loaded),
    error_message: asNullableString(value.error_message),
    started_at: asNullableString(value.started_at),
    finished_at: asNullableString(value.finished_at),
    created_at: asNullableString(value.created_at),
    updated_at: asNullableString(value.updated_at),
  };
};

const parseSyncRunList = (payload: unknown): WbrSyncRun[] => {
  if (Array.isArray(payload)) {
    return payload.map(parseSyncRun);
  }
  if (!isRecord(payload) || !Array.isArray(payload.runs)) {
    return [];
  }
  return payload.runs.map(parseSyncRun);
};

const parseChunkResult = (value: unknown): RunAmazonAdsChunkResult => {
  if (!isRecord(value) || !isRecord(value.run)) {
    throw new Error("Invalid Amazon Ads sync chunk response");
  }
  return {
    run: parseSyncRun(value.run),
    rows_fetched: asNumber(value.rows_fetched),
    rows_loaded: asNumber(value.rows_loaded),
  };
};

export const getAmazonAdsConnectUrl = async (
  token: string,
  profileId: string,
  returnPath: string,
): Promise<string> => {
  const data = await requestJson<ConnectResponse>(
    token,
    `/admin/wbr/profiles/${profileId}/amazon-ads/connect`,
    {
      method: "POST",
      body: JSON.stringify({ return_path: returnPath }),
    },
  );
  return data.authorization_url;
};

export const getAmazonAdsConnectionStatus = async (
  token: string,
  profileId: string,
): Promise<{ connected: boolean; connection: AmazonAdsConnection | null }> => {
  const data = await requestJson<ConnectionStatusResponse>(
    token,
    `/admin/wbr/profiles/${profileId}/amazon-ads/connection`,
    { method: "GET" },
  );
  return { connected: data.connected, connection: data.connection };
};

export const listAmazonAdsProfiles = async (
  token: string,
  profileId: string,
): Promise<AmazonAdsAdvertiserProfile[]> => {
  const data = await requestJson<ProfilesResponse>(
    token,
    `/admin/wbr/profiles/${profileId}/amazon-ads/profiles`,
    { method: "GET" },
  );
  return data.profiles ?? [];
};

export const selectAmazonAdsProfile = async (
  token: string,
  profileId: string,
  amazonAdsProfileId: string,
  amazonAdsAccountId?: string,
): Promise<void> => {
  await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/amazon-ads/select-profile`,
    {
      method: "POST",
      body: JSON.stringify({
        amazon_ads_profile_id: amazonAdsProfileId,
        amazon_ads_account_id: amazonAdsAccountId ?? null,
      }),
    },
  );
};

export const listAmazonAdsSyncRuns = async (
  token: string,
  profileId: string,
): Promise<WbrSyncRun[]> => {
  const query = new URLSearchParams({ source_type: "amazon_ads" });
  const payload = await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/sync-runs?${query.toString()}`,
    { method: "GET" },
  );
  return parseSyncRunList(payload);
};

export const runAmazonAdsBackfill = async (
  token: string,
  profileId: string,
  request: RunAmazonAdsBackfillRequest,
): Promise<RunAmazonAdsBackfillResult> => {
  const payload = await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/sync-runs/amazon-ads/backfill`,
    {
      method: "POST",
      body: JSON.stringify(request),
    },
  );

  if (!isRecord(payload) || !Array.isArray(payload.chunks)) {
    throw new Error("Invalid Amazon Ads backfill response");
  }

  return {
    profile_id: asString(payload.profile_id),
    job_type: "backfill",
    chunk_days: asNumber(payload.chunk_days),
    date_from: asString(payload.date_from),
    date_to: asString(payload.date_to),
    chunks: payload.chunks.map(parseChunkResult),
  };
};

export const runAmazonAdsDailyRefresh = async (
  token: string,
  profileId: string,
): Promise<RunAmazonAdsDailyRefreshResult> => {
  const payload = await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/sync-runs/amazon-ads/daily-refresh`,
    { method: "POST" },
  );

  if (!isRecord(payload) || !isRecord(payload.chunk)) {
    throw new Error("Invalid Amazon Ads daily refresh response");
  }

  return {
    profile_id: asString(payload.profile_id),
    job_type: "daily_refresh",
    date_from: asString(payload.date_from),
    date_to: asString(payload.date_to),
    chunk: parseChunkResult(payload.chunk),
  };
};
