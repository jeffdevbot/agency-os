export type PacvueCampaignMetrics = {
  campaign_name: string;
  fact_rows: number;
  impressions: number;
  clicks: number;
  spend: string;
  orders: number;
  sales: string;
  first_seen: string | null;
  last_seen: string | null;
};

export type PacvueMappingItem = PacvueCampaignMetrics & {
  id: string | null;
  row_id: string | null;
  leaf_row_label: string | null;
  goal_code: string | null;
  raw_tag: string | null;
  import_batch_id: string | null;
  is_manual: boolean;
  updated_at: string | null;
};

export type PacvueMappingWindow = {
  date_from: string | null;
  date_to: string | null;
};

export type PacvueLeafRow = {
  id: string;
  row_label: string | null;
  parent_row_id: string | null;
  sort_order: number | null;
};

export const PACVUE_GOAL_CODES = ["Perf", "Rsrch", "Comp", "Harv", "Def", "Rank"] as const;
export type PacvueGoalCode = (typeof PACVUE_GOAL_CODES)[number];

const getBackendUrl = (): string => {
  const url = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (!url) {
    throw new Error("NEXT_PUBLIC_BACKEND_URL is not configured");
  }
  return url.replace(/\/+$/, "");
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const asString = (value: unknown, fallback = ""): string =>
  typeof value === "string" ? value : fallback;

const asNullableString = (value: unknown): string | null =>
  typeof value === "string" ? value : null;

const asNumber = (value: unknown, fallback = 0): number =>
  typeof value === "number" && Number.isFinite(value) ? value : fallback;

const asNullableNumber = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

const asBoolean = (value: unknown, fallback = false): boolean =>
  typeof value === "boolean" ? value : fallback;

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

const requestJson = async <T>(
  token: string,
  path: string,
  init?: RequestInit
): Promise<T> => {
  const response = await fetch(`${getBackendUrl()}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new Error(detail);
  }

  return (await response.json()) as T;
};

const parseMetrics = (value: unknown): PacvueCampaignMetrics => {
  const record = isRecord(value) ? value : {};
  return {
    campaign_name: asString(record.campaign_name),
    fact_rows: asNumber(record.fact_rows),
    impressions: asNumber(record.impressions),
    clicks: asNumber(record.clicks),
    spend: asString(record.spend, "0"),
    orders: asNumber(record.orders),
    sales: asString(record.sales, "0"),
    first_seen: asNullableString(record.first_seen),
    last_seen: asNullableString(record.last_seen),
  };
};

const parseMappingItem = (value: unknown): PacvueMappingItem => {
  const record = isRecord(value) ? value : {};
  return {
    ...parseMetrics(record),
    id: asNullableString(record.id),
    row_id: asNullableString(record.row_id),
    leaf_row_label: asNullableString(record.leaf_row_label),
    goal_code: asNullableString(record.goal_code),
    raw_tag: asNullableString(record.raw_tag),
    import_batch_id: asNullableString(record.import_batch_id),
    is_manual: asBoolean(record.is_manual),
    updated_at: asNullableString(record.updated_at),
  };
};

export const listPacvueUnmapped = async (
  token: string,
  profileId: string,
  weeks = 4
): Promise<PacvueMappingWindow & { items: PacvueCampaignMetrics[] }> => {
  const payload = await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/pacvue/unmapped?weeks=${weeks}`,
    { method: "GET" }
  );
  const record = isRecord(payload) ? payload : {};
  const items = Array.isArray(record.items) ? record.items.map(parseMetrics) : [];
  return {
    date_from: asNullableString(record.date_from),
    date_to: asNullableString(record.date_to),
    items,
  };
};

export const listPacvueMappings = async (
  token: string,
  profileId: string,
  weeks = 4
): Promise<PacvueMappingWindow & { items: PacvueMappingItem[] }> => {
  const payload = await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/pacvue/mappings?weeks=${weeks}`,
    { method: "GET" }
  );
  const record = isRecord(payload) ? payload : {};
  const items = Array.isArray(record.items) ? record.items.map(parseMappingItem) : [];
  return {
    date_from: asNullableString(record.date_from),
    date_to: asNullableString(record.date_to),
    items,
  };
};

export const listPacvueLeafRows = async (
  token: string,
  profileId: string
): Promise<PacvueLeafRow[]> => {
  const payload = await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/pacvue/leaf-rows`,
    { method: "GET" }
  );
  const record = isRecord(payload) ? payload : {};
  if (!Array.isArray(record.items)) return [];
  return record.items.flatMap((item) => {
    if (!isRecord(item)) return [];
    const id = asString(item.id);
    if (!id) return [];
    return [
      {
        id,
        row_label: asNullableString(item.row_label),
        parent_row_id: asNullableString(item.parent_row_id),
        sort_order: asNullableNumber(item.sort_order),
      } satisfies PacvueLeafRow,
    ];
  });
};

export const upsertPacvueManualMap = async (
  token: string,
  profileId: string,
  payload: { campaign_name: string; row_id: string; goal_code: PacvueGoalCode }
): Promise<void> => {
  await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/pacvue/manual-map`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
};

export const deactivatePacvueMapping = async (
  token: string,
  profileId: string,
  campaignName: string
): Promise<void> => {
  await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/pacvue/deactivate-mapping`,
    {
      method: "POST",
      body: JSON.stringify({ campaign_name: campaignName }),
    }
  );
};

export const setPacvueExclusion = async (
  token: string,
  profileId: string,
  campaignName: string,
  excluded: boolean,
  reason?: string
): Promise<void> => {
  await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/pacvue/exclusion`,
    {
      method: "POST",
      body: JSON.stringify({
        campaign_name: campaignName,
        excluded,
        ...(reason ? { reason } : {}),
      }),
    }
  );
};
