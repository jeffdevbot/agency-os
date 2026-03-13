import type { WbrRow } from "./wbrApi";

export type WbrChildAsinItem = {
  id: string;
  profile_id: string;
  listing_batch_id: string | null;
  child_asin: string;
  child_sku: string | null;
  child_product_name: string | null;
  category: string | null;
  fulfillment_method: string | null;
  source_item_style: string | null;
  active: boolean;
  mapped_row_id: string | null;
  mapped_row_label: string | null;
  mapped_row_active: boolean | null;
  created_at: string | null;
  updated_at: string | null;
};

export type SetWbrChildAsinMappingResult = {
  child_asin: string;
  mapped_row_id: string | null;
  mapped_row_label: string | null;
  mapped_row_active: boolean | null;
};

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

const parseChildAsinItem = (value: unknown): WbrChildAsinItem => {
  if (!isRecord(value)) {
    throw new Error("Invalid child ASIN response");
  }

  return {
    id: asString(value.id),
    profile_id: asString(value.profile_id),
    listing_batch_id: asNullableString(value.listing_batch_id),
    child_asin: asString(value.child_asin),
    child_sku: asNullableString(value.child_sku),
    child_product_name: asNullableString(value.child_product_name),
    category: asNullableString(value.category),
    fulfillment_method: asNullableString(value.fulfillment_method),
    source_item_style: asNullableString(value.source_item_style),
    active: asBoolean(value.active),
    mapped_row_id: asNullableString(value.mapped_row_id),
    mapped_row_label: asNullableString(value.mapped_row_label),
    mapped_row_active: typeof value.mapped_row_active === "boolean" ? value.mapped_row_active : null,
    created_at: asNullableString(value.created_at),
    updated_at: asNullableString(value.updated_at),
  };
};

const parseMappingResult = (value: unknown): SetWbrChildAsinMappingResult => {
  if (isRecord(value) && isRecord(value.mapping)) {
    return parseMappingResult(value.mapping);
  }
  if (!isRecord(value)) {
    throw new Error("Invalid ASIN mapping response");
  }
  return {
    child_asin: asString(value.child_asin),
    mapped_row_id: asNullableString(value.mapped_row_id),
    mapped_row_label: asNullableString(value.mapped_row_label),
    mapped_row_active: typeof value.mapped_row_active === "boolean" ? value.mapped_row_active : null,
  };
};

export const listWbrChildAsins = async (token: string, profileId: string): Promise<WbrChildAsinItem[]> => {
  const payload = await requestJson<unknown>(token, `/admin/wbr/profiles/${profileId}/child-asins`, {
    method: "GET",
  });

  if (Array.isArray(payload)) {
    return payload.map(parseChildAsinItem);
  }
  if (!isRecord(payload)) return [];
  if (Array.isArray(payload.items)) return payload.items.map(parseChildAsinItem);
  return [];
};

export const setWbrChildAsinMapping = async (
  token: string,
  profileId: string,
  childAsin: string,
  rowId: string | null
): Promise<SetWbrChildAsinMappingResult> => {
  const payload = await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/child-asins/${encodeURIComponent(childAsin)}/mapping`,
    {
      method: "PUT",
      body: JSON.stringify({ row_id: rowId }),
    }
  );
  return parseMappingResult(payload);
};

export const buildActiveLeafRowOptions = (leafRows: WbrRow[]) => {
  const active = leafRows.filter((row) => row.active);
  const byId = Object.fromEntries(leafRows.map((row) => [row.id, row]));
  return { activeLeafRows: active, leafRowById: byId };
};
