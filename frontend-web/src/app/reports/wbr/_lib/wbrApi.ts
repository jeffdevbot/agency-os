export type WeekStartDay = "sunday" | "monday";
export type WbrRowKind = "parent" | "leaf";

export type WbrProfile = {
  id: string;
  client_id: string;
  marketplace_code: string;
  display_name: string;
  week_start_day: WeekStartDay;
  status: string;
  windsor_account_id: string | null;
  amazon_ads_profile_id: string | null;
  amazon_ads_account_id: string | null;
  amazon_ads_country_code: string | null;
  amazon_ads_currency_code: string | null;
  amazon_ads_marketplace_string_id: string | null;
  backfill_start_date: string | null;
  daily_rewrite_days: number;
  sp_api_auto_sync_enabled: boolean;
  ads_api_auto_sync_enabled: boolean;
  search_term_auto_sync_enabled: boolean;
  search_term_sb_auto_sync_enabled: boolean;
  search_term_sd_auto_sync_enabled: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type WbrRow = {
  id: string;
  profile_id: string;
  row_label: string;
  row_kind: WbrRowKind;
  parent_row_id: string | null;
  sort_order: number;
  active: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type WbrPacvueImportBatchStatus = "running" | "success" | "error";

export type WbrPacvueImportBatch = {
  id: string;
  profile_id: string;
  source_filename: string | null;
  import_status: WbrPacvueImportBatchStatus;
  rows_read: number;
  rows_loaded: number;
  error_message: string | null;
  initiated_by: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type WbrPacvueImportSummary = {
  header_row_index: number;
  rows_read: number;
  rows_loaded: number;
  duplicate_rows_skipped: number;
  unmapped_rows_skipped: number;
  invalid_rows_skipped: number;
  created_leaf_rows: number;
  reactivated_leaf_rows: number;
  warnings: string[];
};

export type WbrPacvueImportResult = {
  batch: WbrPacvueImportBatch;
  summary: WbrPacvueImportSummary;
};

export type WbrSnapshot = {
  id: string;
  profile_id: string;
  snapshot_kind: string;
  week_ending: string | null;
  window_start: string | null;
  window_end: string | null;
  digest_version: string;
  created_at: string | null;
};

export type WbrListingImportBatchStatus = "running" | "success" | "error";

export type WbrListingImportBatch = {
  id: string;
  profile_id: string;
  source_filename: string | null;
  source_provider: "windsor" | "file_upload" | "amazon_spapi";
  import_status: WbrListingImportBatchStatus;
  rows_read: number;
  rows_loaded: number;
  error_message: string | null;
  initiated_by: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type WbrListingImportSummary = {
  source_type: string;
  source_provider?: string | null;
  sheet_title: string | null;
  header_row_index: number;
  rows_read: number;
  rows_loaded: number;
  duplicate_rows_merged: number;
  windsor_account_id?: string | null;
};

export type WbrListingImportResult = {
  batch: WbrListingImportBatch;
  summary: WbrListingImportSummary;
};

export type CreateWbrProfileRequest = {
  client_id: string;
  marketplace_code: string;
  display_name: string;
  week_start_day: WeekStartDay;
  windsor_account_id?: string | null;
  amazon_ads_profile_id?: string | null;
  amazon_ads_account_id?: string | null;
  amazon_ads_country_code?: string | null;
  amazon_ads_currency_code?: string | null;
  amazon_ads_marketplace_string_id?: string | null;
  backfill_start_date?: string | null;
  daily_rewrite_days: number;
  sp_api_auto_sync_enabled?: boolean;
  ads_api_auto_sync_enabled?: boolean;
  search_term_auto_sync_enabled?: boolean;
  search_term_sb_auto_sync_enabled?: boolean;
  search_term_sd_auto_sync_enabled?: boolean;
};

export type UpdateWbrProfileRequest = {
  display_name?: string | null;
  week_start_day?: WeekStartDay | null;
  status?: string | null;
  windsor_account_id?: string | null;
  amazon_ads_profile_id?: string | null;
  amazon_ads_account_id?: string | null;
  amazon_ads_country_code?: string | null;
  amazon_ads_currency_code?: string | null;
  amazon_ads_marketplace_string_id?: string | null;
  backfill_start_date?: string | null;
  daily_rewrite_days?: number | null;
  sp_api_auto_sync_enabled?: boolean | null;
  ads_api_auto_sync_enabled?: boolean | null;
  search_term_auto_sync_enabled?: boolean | null;
  search_term_sb_auto_sync_enabled?: boolean | null;
  search_term_sd_auto_sync_enabled?: boolean | null;
};

export type CreateWbrRowRequest = {
  row_label: string;
  row_kind: WbrRowKind;
  parent_row_id?: string | null;
  sort_order: number;
};

export type UpdateWbrRowRequest = {
  row_label: string;
  parent_row_id: string | null;
  sort_order: number;
  active: boolean;
};

const getBackendUrl = (): string => {
  const url = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (!url) {
    throw new Error("NEXT_PUBLIC_BACKEND_URL is not configured");
  }
  return url.replace(/\/+$/, "");
};

const authHeaders = (token: string): Record<string, string> => ({
  Authorization: `Bearer ${token}`,
});

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
    const n = Number(value);
    if (!Number.isNaN(n)) return n;
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

const parseProfile = (value: unknown): WbrProfile => {
  if (!isRecord(value)) {
    throw new Error("Invalid WBR profile response");
  }

  return {
    id: asString(value.id),
    client_id: asString(value.client_id),
    marketplace_code: asString(value.marketplace_code),
    display_name: asString(value.display_name),
    week_start_day: (asString(value.week_start_day).toLowerCase() === "monday" ? "monday" : "sunday"),
    status: asString(value.status),
    windsor_account_id: asNullableString(value.windsor_account_id),
    amazon_ads_profile_id: asNullableString(value.amazon_ads_profile_id),
    amazon_ads_account_id: asNullableString(value.amazon_ads_account_id),
    amazon_ads_country_code: asNullableString(value.amazon_ads_country_code),
    amazon_ads_currency_code: asNullableString(value.amazon_ads_currency_code),
    amazon_ads_marketplace_string_id: asNullableString(value.amazon_ads_marketplace_string_id),
    backfill_start_date: asNullableString(value.backfill_start_date),
    daily_rewrite_days: asNumber(value.daily_rewrite_days),
    sp_api_auto_sync_enabled: asBoolean(value.sp_api_auto_sync_enabled),
    ads_api_auto_sync_enabled: asBoolean(value.ads_api_auto_sync_enabled),
    search_term_auto_sync_enabled: asBoolean(value.search_term_auto_sync_enabled),
    search_term_sb_auto_sync_enabled: asBoolean(value.search_term_sb_auto_sync_enabled),
    search_term_sd_auto_sync_enabled: asBoolean(value.search_term_sd_auto_sync_enabled),
    created_at: asNullableString(value.created_at),
    updated_at: asNullableString(value.updated_at),
  };
};

const parseRow = (value: unknown): WbrRow => {
  if (!isRecord(value)) {
    throw new Error("Invalid WBR row response");
  }

  return {
    id: asString(value.id),
    profile_id: asString(value.profile_id),
    row_label: asString(value.row_label),
    row_kind: asString(value.row_kind) === "parent" ? "parent" : "leaf",
    parent_row_id: asNullableString(value.parent_row_id),
    sort_order: asNumber(value.sort_order),
    active: asBoolean(value.active),
    created_at: asNullableString(value.created_at),
    updated_at: asNullableString(value.updated_at),
  };
};

const parsePacvueImportBatch = (value: unknown): WbrPacvueImportBatch => {
  if (!isRecord(value)) {
    throw new Error("Invalid Pacvue import batch response");
  }

  const importStatus = asString(value.import_status);
  return {
    id: asString(value.id),
    profile_id: asString(value.profile_id),
    source_filename: asNullableString(value.source_filename),
    import_status:
      importStatus === "running" || importStatus === "error" ? importStatus : "success",
    rows_read: asNumber(value.rows_read),
    rows_loaded: asNumber(value.rows_loaded),
    error_message: asNullableString(value.error_message),
    initiated_by: asNullableString(value.initiated_by),
    started_at: asNullableString(value.started_at),
    finished_at: asNullableString(value.finished_at),
    created_at: asNullableString(value.created_at),
    updated_at: asNullableString(value.updated_at),
  };
};

const parsePacvueImportSummary = (value: unknown): WbrPacvueImportSummary => {
  if (!isRecord(value)) {
    throw new Error("Invalid Pacvue import summary response");
  }

  return {
    header_row_index: asNumber(value.header_row_index),
    rows_read: asNumber(value.rows_read),
    rows_loaded: asNumber(value.rows_loaded),
    duplicate_rows_skipped: asNumber(value.duplicate_rows_skipped),
    unmapped_rows_skipped: asNumber(value.unmapped_rows_skipped),
    invalid_rows_skipped: asNumber(value.invalid_rows_skipped),
    created_leaf_rows: asNumber(value.created_leaf_rows),
    reactivated_leaf_rows: asNumber(value.reactivated_leaf_rows),
    warnings: Array.isArray(value.warnings) ? value.warnings.map(asString).filter(Boolean) : [],
  };
};

const parseListingImportBatch = (value: unknown): WbrListingImportBatch => {
  if (!isRecord(value)) {
    throw new Error("Invalid listings import batch response");
  }

  const importStatus = asString(value.import_status);
  return {
    id: asString(value.id),
    profile_id: asString(value.profile_id),
    source_filename: asNullableString(value.source_filename),
    source_provider:
      value.source_provider === "file_upload" || value.source_provider === "amazon_spapi"
        ? value.source_provider
        : "windsor",
    import_status:
      importStatus === "running" || importStatus === "error" ? importStatus : "success",
    rows_read: asNumber(value.rows_read),
    rows_loaded: asNumber(value.rows_loaded),
    error_message: asNullableString(value.error_message),
    initiated_by: asNullableString(value.initiated_by),
    started_at: asNullableString(value.started_at),
    finished_at: asNullableString(value.finished_at),
    created_at: asNullableString(value.created_at),
    updated_at: asNullableString(value.updated_at),
  };
};

const parseListingImportSummary = (value: unknown): WbrListingImportSummary => {
  if (!isRecord(value)) {
    throw new Error("Invalid listings import summary response");
  }

  return {
    source_type: asString(value.source_type),
    source_provider: asNullableString(value.source_provider),
    sheet_title: asNullableString(value.sheet_title),
    header_row_index: asNumber(value.header_row_index),
    rows_read: asNumber(value.rows_read),
    rows_loaded: asNumber(value.rows_loaded),
    duplicate_rows_merged: asNumber(value.duplicate_rows_merged),
    windsor_account_id: asNullableString(value.windsor_account_id),
  };
};

const parseProfileList = (payload: unknown): WbrProfile[] => {
  if (Array.isArray(payload)) {
    return payload.map(parseProfile);
  }

  if (!isRecord(payload)) return [];
  if (Array.isArray(payload.profiles)) return payload.profiles.map(parseProfile);
  if (Array.isArray(payload.items)) return payload.items.map(parseProfile);
  return [];
};

const parseRowList = (payload: unknown): WbrRow[] => {
  if (Array.isArray(payload)) {
    return payload.map(parseRow);
  }

  if (!isRecord(payload)) return [];
  if (Array.isArray(payload.rows)) return payload.rows.map(parseRow);
  if (Array.isArray(payload.items)) return payload.items.map(parseRow);
  return [];
};

const parseProfileItem = (payload: unknown): WbrProfile => {
  if (isRecord(payload) && isRecord(payload.profile)) {
    return parseProfile(payload.profile);
  }
  return parseProfile(payload);
};

const parseRowItem = (payload: unknown): WbrRow => {
  if (isRecord(payload) && isRecord(payload.row)) {
    return parseRow(payload.row);
  }
  return parseRow(payload);
};

const parsePacvueImportBatchList = (payload: unknown): WbrPacvueImportBatch[] => {
  if (Array.isArray(payload)) {
    return payload.map(parsePacvueImportBatch);
  }

  if (!isRecord(payload)) return [];
  if (Array.isArray(payload.batches)) return payload.batches.map(parsePacvueImportBatch);
  if (Array.isArray(payload.items)) return payload.items.map(parsePacvueImportBatch);
  return [];
};

const parsePacvueImportResult = (payload: unknown): WbrPacvueImportResult => {
  if (!isRecord(payload) || !isRecord(payload.batch) || !isRecord(payload.summary)) {
    throw new Error("Invalid Pacvue import response");
  }

  return {
    batch: parsePacvueImportBatch(payload.batch),
    summary: parsePacvueImportSummary(payload.summary),
  };
};

const parseListingImportBatchList = (payload: unknown): WbrListingImportBatch[] => {
  if (Array.isArray(payload)) {
    return payload.map(parseListingImportBatch);
  }

  if (!isRecord(payload)) return [];
  if (Array.isArray(payload.batches)) return payload.batches.map(parseListingImportBatch);
  if (Array.isArray(payload.items)) return payload.items.map(parseListingImportBatch);
  return [];
};

const parseListingImportResult = (payload: unknown): WbrListingImportResult => {
  if (!isRecord(payload) || !isRecord(payload.batch) || !isRecord(payload.summary)) {
    throw new Error("Invalid listings import response");
  }

  return {
    batch: parseListingImportBatch(payload.batch),
    summary: parseListingImportSummary(payload.summary),
  };
};

const parseSnapshot = (value: unknown): WbrSnapshot => {
  if (!isRecord(value)) {
    throw new Error("Invalid WBR snapshot response");
  }

  return {
    id: asString(value.id),
    profile_id: asString(value.profile_id),
    snapshot_kind: asString(value.snapshot_kind),
    week_ending: asNullableString(value.week_ending),
    window_start: asNullableString(value.window_start),
    window_end: asNullableString(value.window_end),
    digest_version: asString(value.digest_version),
    created_at: asNullableString(value.created_at),
  };
};

export const listWbrProfiles = async (token: string, clientId: string): Promise<WbrProfile[]> => {
  const query = new URLSearchParams({ client_id: clientId });
  const payload = await requestJson<unknown>(token, `/admin/wbr/profiles?${query.toString()}`, {
    method: "GET",
  });
  return parseProfileList(payload);
};

export const createWbrProfile = async (
  token: string,
  request: CreateWbrProfileRequest
): Promise<WbrProfile> => {
  const payload = await requestJson<unknown>(token, "/admin/wbr/profiles", {
    method: "POST",
    body: JSON.stringify(request),
  });
  return parseProfileItem(payload);
};

export const getWbrProfile = async (token: string, profileId: string): Promise<WbrProfile> => {
  const payload = await requestJson<unknown>(token, `/admin/wbr/profiles/${profileId}`, {
    method: "GET",
  });
  return parseProfileItem(payload);
};

export const updateWbrProfile = async (
  token: string,
  profileId: string,
  request: UpdateWbrProfileRequest
): Promise<WbrProfile> => {
  const payload = await requestJson<unknown>(token, `/admin/wbr/profiles/${profileId}`, {
    method: "PATCH",
    body: JSON.stringify(request),
  });
  return parseProfileItem(payload);
};

export const listWbrRows = async (token: string, profileId: string): Promise<WbrRow[]> => {
  const query = new URLSearchParams({ include_inactive: "true" });
  const payload = await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/rows?${query.toString()}`,
    {
    method: "GET",
    }
  );
  return parseRowList(payload);
};

export const createWbrRow = async (
  token: string,
  profileId: string,
  request: CreateWbrRowRequest
): Promise<WbrRow> => {
  const payload = await requestJson<unknown>(token, `/admin/wbr/profiles/${profileId}/rows`, {
    method: "POST",
    body: JSON.stringify(request),
  });
  return parseRowItem(payload);
};

export const updateWbrRow = async (
  token: string,
  rowId: string,
  request: UpdateWbrRowRequest
): Promise<WbrRow> => {
  const payload = await requestJson<unknown>(token, `/admin/wbr/rows/${rowId}`, {
    method: "PATCH",
    body: JSON.stringify(request),
  });
  return parseRowItem(payload);
};

export const deleteWbrRow = async (
  token: string,
  rowId: string,
  options?: { permanent?: boolean }
): Promise<void> => {
  const query = new URLSearchParams();
  if (options?.permanent) {
    query.set("permanent", "true");
  }
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  await requestJson<unknown>(token, `/admin/wbr/rows/${rowId}${suffix}`, {
    method: "DELETE",
  });
};

export const listPacvueImportBatches = async (
  token: string,
  profileId: string
): Promise<WbrPacvueImportBatch[]> => {
  const payload = await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/pacvue/import-batches`,
    {
      method: "GET",
    }
  );
  return parsePacvueImportBatchList(payload);
};

export const importPacvueWorkbook = async (
  token: string,
  profileId: string,
  file: File
): Promise<WbrPacvueImportResult> => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${getBackendUrl()}/admin/wbr/profiles/${profileId}/pacvue/import`, {
    method: "POST",
    headers: authHeaders(token),
    body: formData,
  });

  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new Error(detail);
  }

  const payload = (await response.json()) as unknown;
  return parsePacvueImportResult(payload);
};

export const createWbrSnapshot = async (
  token: string,
  profileId: string,
  request?: {
    weeks?: number;
    snapshot_kind?: "manual";
    include_raw?: boolean;
  }
): Promise<WbrSnapshot> => {
  const payload = await requestJson<unknown>(token, `/admin/wbr/profiles/${profileId}/snapshots`, {
    method: "POST",
    body: JSON.stringify({
      weeks: request?.weeks ?? 4,
      snapshot_kind: request?.snapshot_kind ?? "manual",
      include_raw: request?.include_raw ?? false,
    }),
  });

  if (!isRecord(payload) || !isRecord(payload.snapshot)) {
    throw new Error("Invalid WBR snapshot response");
  }

  return parseSnapshot(payload.snapshot);
};

export const listListingImportBatches = async (
  token: string,
  profileId: string
): Promise<WbrListingImportBatch[]> => {
  const payload = await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/listings/import-batches`,
    {
      method: "GET",
    }
  );
  return parseListingImportBatchList(payload);
};

export const importListingFile = async (
  token: string,
  profileId: string,
  file: File
): Promise<WbrListingImportResult> => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${getBackendUrl()}/admin/wbr/profiles/${profileId}/listings/import`, {
    method: "POST",
    headers: authHeaders(token),
    body: formData,
  });

  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new Error(detail);
  }

  const payload = (await response.json()) as unknown;
  return parseListingImportResult(payload);
};

export const importListingFileFromWindsor = async (
  token: string,
  profileId: string
): Promise<WbrListingImportResult> => {
  const payload = await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/listings/import-windsor`,
    {
      method: "POST",
    }
  );
  return parseListingImportResult(payload);
};
