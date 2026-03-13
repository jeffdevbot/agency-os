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

export type RunWbrWindsorBusinessBackfillRequest = {
  date_from: string;
  date_to: string;
  chunk_days: number;
};

export type RunWbrWindsorBusinessChunkResult = {
  run: WbrSyncRun;
  rows_fetched: number;
  rows_loaded: number;
};

export type RunWbrWindsorBusinessBackfillResult = {
  profile_id: string;
  job_type: "backfill";
  chunk_days: number;
  date_from: string;
  date_to: string;
  chunks: RunWbrWindsorBusinessChunkResult[];
};

export type RunWbrWindsorBusinessDailyRefreshResult = {
  profile_id: string;
  job_type: "daily_refresh";
  date_from: string;
  date_to: string;
  chunk: RunWbrWindsorBusinessChunkResult;
};

export type WbrSection1Week = {
  start: string;
  end: string;
  label: string;
};

export type WbrSection1RowWeek = {
  page_views: number;
  unit_sales: number;
  sales: string;
  conversion_rate: number;
};

export type WbrSection1Row = {
  id: string;
  row_label: string;
  row_kind: "parent" | "leaf";
  parent_row_id: string | null;
  sort_order: number;
  weeks: WbrSection1RowWeek[];
};

export type WbrSection1ReportQa = {
  active_row_count: number;
  mapped_asin_count: number;
  unmapped_asin_count: number;
  unmapped_fact_rows: number;
  fact_row_count: number;
};

export type WbrSection1Report = {
  weeks: WbrSection1Week[];
  rows: WbrSection1Row[];
  qa: WbrSection1ReportQa;
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

const parseChunkResult = (value: unknown): RunWbrWindsorBusinessChunkResult => {
  if (!isRecord(value) || !isRecord(value.run)) {
    throw new Error("Invalid Windsor business sync chunk response");
  }
  return {
    run: parseSyncRun(value.run),
    rows_fetched: asNumber(value.rows_fetched),
    rows_loaded: asNumber(value.rows_loaded),
  };
};

const parseSection1Week = (value: unknown): WbrSection1Week => {
  if (!isRecord(value)) {
    throw new Error("Invalid Section 1 week response");
  }
  return {
    start: asString(value.start),
    end: asString(value.end),
    label: asString(value.label),
  };
};

const parseSection1RowWeek = (value: unknown): WbrSection1RowWeek => {
  if (!isRecord(value)) {
    throw new Error("Invalid Section 1 row week response");
  }
  return {
    page_views: asNumber(value.page_views),
    unit_sales: asNumber(value.unit_sales),
    sales: asString(value.sales),
    conversion_rate: asNumber(value.conversion_rate),
  };
};

const parseSection1Row = (value: unknown): WbrSection1Row => {
  if (!isRecord(value) || !Array.isArray(value.weeks)) {
    throw new Error("Invalid Section 1 row response");
  }
  return {
    id: asString(value.id),
    row_label: asString(value.row_label),
    row_kind: asString(value.row_kind) === "parent" ? "parent" : "leaf",
    parent_row_id: asNullableString(value.parent_row_id),
    sort_order: asNumber(value.sort_order),
    weeks: value.weeks.map(parseSection1RowWeek),
  };
};

const parseSection1Report = (payload: unknown): WbrSection1Report => {
  if (!isRecord(payload)) {
    throw new Error("Invalid Section 1 report response");
  }
  return {
    weeks: Array.isArray(payload.weeks) ? payload.weeks.map(parseSection1Week) : [],
    rows: Array.isArray(payload.rows) ? payload.rows.map(parseSection1Row) : [],
    qa: isRecord(payload.qa)
      ? {
          active_row_count: asNumber(payload.qa.active_row_count),
          mapped_asin_count: asNumber(payload.qa.mapped_asin_count),
          unmapped_asin_count: asNumber(payload.qa.unmapped_asin_count),
          unmapped_fact_rows: asNumber(payload.qa.unmapped_fact_rows),
          fact_row_count: asNumber(payload.qa.fact_row_count),
        }
      : {
          active_row_count: 0,
          mapped_asin_count: 0,
          unmapped_asin_count: 0,
          unmapped_fact_rows: 0,
          fact_row_count: 0,
        },
  };
};

export const listWbrSyncRuns = async (token: string, profileId: string): Promise<WbrSyncRun[]> => {
  const query = new URLSearchParams({ source_type: "windsor_business" });
  const payload = await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/sync-runs?${query.toString()}`,
    { method: "GET" }
  );
  return parseSyncRunList(payload);
};

export const runWbrWindsorBusinessBackfill = async (
  token: string,
  profileId: string,
  request: RunWbrWindsorBusinessBackfillRequest
): Promise<RunWbrWindsorBusinessBackfillResult> => {
  const payload = await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/sync-runs/windsor-business/backfill`,
    {
      method: "POST",
      body: JSON.stringify(request),
    }
  );

  if (!isRecord(payload) || !Array.isArray(payload.chunks)) {
    throw new Error("Invalid Windsor business backfill response");
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

export const runWbrWindsorBusinessDailyRefresh = async (
  token: string,
  profileId: string
): Promise<RunWbrWindsorBusinessDailyRefreshResult> => {
  const payload = await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/sync-runs/windsor-business/daily-refresh`,
    { method: "POST" }
  );

  if (!isRecord(payload) || !isRecord(payload.chunk)) {
    throw new Error("Invalid Windsor business daily refresh response");
  }

  return {
    profile_id: asString(payload.profile_id),
    job_type: "daily_refresh",
    date_from: asString(payload.date_from),
    date_to: asString(payload.date_to),
    chunk: parseChunkResult(payload.chunk),
  };
};

export const getWbrSection1Report = async (
  token: string,
  profileId: string,
  weeks = 4
): Promise<WbrSection1Report> => {
  const query = new URLSearchParams({ weeks: String(weeks) });
  const payload = await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/section1-report?${query.toString()}`,
    { method: "GET" }
  );
  return parseSection1Report(payload);
};
