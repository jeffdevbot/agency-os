export type WbrCampaignExclusionItem = {
  id: string;
  profile_id: string;
  campaign_name: string;
  exclusion_source: string | null;
  exclusion_reason: string | null;
  active: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type ImportWbrCampaignExclusionSummary = {
  rows_read: number;
  rows_excluded: number;
  rows_cleared: number;
  rows_unchanged: number;
};

const CAMPAIGN_EXCLUSION_IMPORT_TIMEOUT_MS = 60_000;

const getBackendUrl = (): string => {
  const url = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (!url) {
    throw new Error("NEXT_PUBLIC_BACKEND_URL is not configured");
  }
  return url.replace(/\/+$/, "");
};

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

const requestJson = async <T>(token: string, path: string, init?: RequestInit): Promise<T> => {
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

const parseCampaignExclusionItem = (value: unknown): WbrCampaignExclusionItem => {
  if (!isRecord(value)) {
    throw new Error("Invalid campaign exclusion response");
  }

  return {
    id: asString(value.id),
    profile_id: asString(value.profile_id),
    campaign_name: asString(value.campaign_name),
    exclusion_source: asNullableString(value.exclusion_source),
    exclusion_reason: asNullableString(value.exclusion_reason),
    active: asBoolean(value.active),
    created_at: asNullableString(value.created_at),
    updated_at: asNullableString(value.updated_at),
  };
};

export const listWbrCampaignExclusions = async (
  token: string,
  profileId: string
): Promise<WbrCampaignExclusionItem[]> => {
  const payload = await requestJson<unknown>(token, `/admin/wbr/profiles/${profileId}/campaign-exclusions`, {
    method: "GET",
  });

  if (Array.isArray(payload)) return payload.map(parseCampaignExclusionItem);
  if (!isRecord(payload)) return [];
  if (Array.isArray(payload.items)) return payload.items.map(parseCampaignExclusionItem);
  return [];
};

export const exportWbrCampaignExclusionsCsv = async (
  token: string,
  profileId: string
): Promise<Blob> => {
  const response = await fetch(
    `${getBackendUrl()}/admin/wbr/profiles/${profileId}/campaign-exclusions/export`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );

  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new Error(detail);
  }

  return await response.blob();
};

export const importWbrCampaignExclusionsCsv = async (
  token: string,
  profileId: string,
  file: File
): Promise<ImportWbrCampaignExclusionSummary> => {
  const formData = new FormData();
  formData.append("file", file);
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), CAMPAIGN_EXCLUSION_IMPORT_TIMEOUT_MS);

  try {
    const response = await fetch(
      `${getBackendUrl()}/admin/wbr/profiles/${profileId}/campaign-exclusions/import`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
        signal: controller.signal,
      }
    );

    if (!response.ok) {
      const detail = await parseErrorDetail(response);
      throw new Error(detail);
    }

    const payload = (await response.json()) as unknown;
    const summary = isRecord(payload) && isRecord(payload.summary) ? payload.summary : payload;
    if (!isRecord(summary)) {
      throw new Error("Invalid campaign exclusion import response");
    }

    return {
      rows_read: typeof summary.rows_read === "number" ? summary.rows_read : 0,
      rows_excluded: typeof summary.rows_excluded === "number" ? summary.rows_excluded : 0,
      rows_cleared: typeof summary.rows_cleared === "number" ? summary.rows_cleared : 0,
      rows_unchanged: typeof summary.rows_unchanged === "number" ? summary.rows_unchanged : 0,
    };
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("Campaign exclusion import timed out. Please try again.");
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
};
