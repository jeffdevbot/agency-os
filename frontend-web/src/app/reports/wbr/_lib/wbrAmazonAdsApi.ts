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
export type AmazonAdsReportJobStatus = "pending" | "processing" | "completed" | "failed";
export type AmazonAdsReportProgressPhase =
  | "queued"
  | "polling"
  | "ready_to_finalize"
  | "completed"
  | "failed"
  | "unknown";

export type AmazonAdsReportJob = {
  report_id: string;
  status: AmazonAdsReportJobStatus;
  poll_attempts: number;
  next_poll_at: string | null;
  location: string | null;
  status_detail: string | null;
  campaign_type: string;
  ad_product: string;
  report_type_id: string;
  columns: string[];
};

export type AmazonAdsReportProgress = {
  phase: AmazonAdsReportProgressPhase;
  summary: string;
  total_jobs: number;
  pending_jobs: number;
  processing_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  next_poll_at: string | null;
};

export type WbrSyncRunRequestMeta = {
  async_reports_v1: boolean;
  amazon_ads_profile_id: string | null;
  marketplace_code: string | null;
  queued_at: string | null;
  finalized_at: string | null;
  last_worker_error: string | null;
  last_worker_error_at: string | null;
  report_jobs: AmazonAdsReportJob[];
  report_progress: AmazonAdsReportProgress | null;
};

export type WbrSyncRun = {
  id: string;
  profile_id: string;
  source_type: string;
  ad_product: string | null;
  report_type_id: string | null;
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
  request_meta: WbrSyncRunRequestMeta | null;
};

export type WbrCoverageRange = {
  date_from: string;
  date_to: string;
};

export type WbrSyncCoverage = {
  source_type: string;
  ad_product: string | null;
  window_start: string;
  window_end: string;
  window_label: string;
  covered_day_count: number;
  in_flight_day_count: number;
  missing_day_count: number;
  covered_ranges: WbrCoverageRange[];
  in_flight_ranges: WbrCoverageRange[];
  missing_ranges: WbrCoverageRange[];
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
const asBoolean = (value: unknown): boolean => value === true;
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
    cache: "no-store",
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

const parseReportJob = (value: unknown): AmazonAdsReportJob => {
  if (!isRecord(value)) {
    throw new Error("Invalid Amazon Ads report job");
  }

  const status = asString(value.status);
  return {
    report_id: asString(value.report_id ?? value.reportId),
    status:
      status === "pending" || status === "processing" || status === "completed" || status === "failed"
        ? status
        : "pending",
    poll_attempts: asNumber(value.poll_attempts),
    next_poll_at: asNullableString(value.next_poll_at),
    location: asNullableString(value.location),
    status_detail: asNullableString(value.status_detail),
    campaign_type: asString(value.campaign_type),
    ad_product: asString(value.ad_product),
    report_type_id: asString(value.report_type_id),
    columns: Array.isArray(value.columns) ? value.columns.map(asString).filter(Boolean) : [],
  };
};

const parseReportProgress = (value: unknown): AmazonAdsReportProgress | null => {
  if (!isRecord(value)) {
    return null;
  }

  const phase = asString(value.phase);
  return {
    phase:
      phase === "queued" ||
      phase === "polling" ||
      phase === "ready_to_finalize" ||
      phase === "completed" ||
      phase === "failed"
        ? phase
        : "unknown",
    summary: asString(value.summary),
    total_jobs: asNumber(value.total_jobs),
    pending_jobs: asNumber(value.pending_jobs),
    processing_jobs: asNumber(value.processing_jobs),
    completed_jobs: asNumber(value.completed_jobs),
    failed_jobs: asNumber(value.failed_jobs),
    next_poll_at: asNullableString(value.next_poll_at),
  };
};

const parseRequestMeta = (value: unknown): WbrSyncRunRequestMeta | null => {
  if (!isRecord(value)) {
    return null;
  }

  return {
    async_reports_v1: asBoolean(value.async_reports_v1),
    amazon_ads_profile_id: asNullableString(value.amazon_ads_profile_id),
    marketplace_code: asNullableString(value.marketplace_code),
    queued_at: asNullableString(value.queued_at),
    finalized_at: asNullableString(value.finalized_at),
    last_worker_error: asNullableString(value.last_worker_error),
    last_worker_error_at: asNullableString(value.last_worker_error_at),
    report_jobs: Array.isArray(value.report_jobs) ? value.report_jobs.map(parseReportJob) : [],
    report_progress: parseReportProgress(value.report_progress),
  };
};

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
    ad_product: asNullableString(value.ad_product),
    report_type_id: asNullableString(value.report_type_id),
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
    request_meta: parseRequestMeta(value.request_meta),
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

const parseCoverageRange = (value: unknown): WbrCoverageRange => {
  if (!isRecord(value)) {
    throw new Error("Invalid Amazon Ads coverage range");
  }
  return {
    date_from: asString(value.date_from),
    date_to: asString(value.date_to),
  };
};

const parseSyncCoverage = (payload: unknown): WbrSyncCoverage => {
  if (!isRecord(payload)) {
    throw new Error("Invalid Amazon Ads coverage response");
  }
  return {
    source_type: asString(payload.source_type),
    ad_product: asNullableString(payload.ad_product),
    window_start: asString(payload.window_start),
    window_end: asString(payload.window_end),
    window_label: asString(payload.window_label),
    covered_day_count: asNumber(payload.covered_day_count),
    in_flight_day_count: asNumber(payload.in_flight_day_count),
    missing_day_count: asNumber(payload.missing_day_count),
    covered_ranges: Array.isArray(payload.covered_ranges) ? payload.covered_ranges.map(parseCoverageRange) : [],
    in_flight_ranges: Array.isArray(payload.in_flight_ranges) ? payload.in_flight_ranges.map(parseCoverageRange) : [],
    missing_ranges: Array.isArray(payload.missing_ranges) ? payload.missing_ranges.map(parseCoverageRange) : [],
  };
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
  amazonAdsCountryCode?: string,
  amazonAdsCurrencyCode?: string,
  amazonAdsMarketplaceStringId?: string,
): Promise<void> => {
  await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/amazon-ads/select-profile`,
    {
      method: "POST",
      body: JSON.stringify({
        amazon_ads_profile_id: amazonAdsProfileId,
        amazon_ads_account_id: amazonAdsAccountId ?? null,
        amazon_ads_country_code: amazonAdsCountryCode ?? null,
        amazon_ads_currency_code: amazonAdsCurrencyCode ?? null,
        amazon_ads_marketplace_string_id: amazonAdsMarketplaceStringId ?? null,
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

export const getAmazonAdsSyncCoverage = async (
  token: string,
  profileId: string,
): Promise<WbrSyncCoverage> => {
  const query = new URLSearchParams({ source_type: "amazon_ads" });
  const payload = await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/sync-coverage?${query.toString()}`,
    { method: "GET" },
  );
  return parseSyncCoverage(payload);
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

export const listSearchTermSyncRuns = async (
  token: string,
  profileId: string,
  adProduct?: string | null,
): Promise<WbrSyncRun[]> => {
  const query = new URLSearchParams({ source_type: "amazon_ads_search_terms" });
  if (adProduct) query.set("ad_product", adProduct);
  const payload = await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/sync-runs?${query.toString()}`,
    { method: "GET" },
  );
  return parseSyncRunList(payload);
};

export const runSearchTermBackfill = async (
  token: string,
  profileId: string,
  request: RunAmazonAdsBackfillRequest,
): Promise<RunAmazonAdsBackfillResult> => {
  const payload = await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/sync-runs/search-terms/backfill`,
    {
      method: "POST",
      body: JSON.stringify(request),
    },
  );

  if (!isRecord(payload) || !Array.isArray(payload.chunks)) {
    throw new Error("Invalid search term backfill response");
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

export const runSearchTermDailyRefresh = async (
  token: string,
  profileId: string,
): Promise<RunAmazonAdsDailyRefreshResult> => {
  const payload = await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/sync-runs/search-terms/daily-refresh`,
    { method: "POST" },
  );

  if (!isRecord(payload) || !isRecord(payload.chunk)) {
    throw new Error("Invalid search term daily refresh response");
  }

  return {
    profile_id: asString(payload.profile_id),
    job_type: "daily_refresh",
    date_from: asString(payload.date_from),
    date_to: asString(payload.date_to),
    chunk: parseChunkResult(payload.chunk),
  };
};

export const getSearchTermSyncCoverage = async (
  token: string,
  profileId: string,
  adProduct?: string | null,
): Promise<WbrSyncCoverage> => {
  const query = new URLSearchParams({ source_type: "amazon_ads_search_terms" });
  if (adProduct) query.set("ad_product", adProduct);
  const payload = await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/sync-coverage?${query.toString()}`,
    { method: "GET" },
  );
  return parseSyncCoverage(payload);
};
