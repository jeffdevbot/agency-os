"use client";

const getBackendUrl = (): string => {
  const url = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (!url) throw new Error("NEXT_PUBLIC_BACKEND_URL is not configured");
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

const requestJson = async <T>(token: string, path: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(`${getBackendUrl()}${path}`, {
    ...init,
    cache: "no-store",
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

// ------------------------------------------------------------------
// Types
// ------------------------------------------------------------------

export type SearchTermFact = {
  id: string;
  report_date: string;
  campaign_type: string;
  campaign_name: string;
  campaign_name_head: string | null;
  ad_group_name: string | null;
  search_term: string;
  match_type: string | null;
  impressions: number;
  clicks: number;
  spend: string;
  orders: number;
  sales: string;
  currency_code: string | null;
};

export type SearchTermFactsParams = {
  date_from?: string;
  date_to?: string;
  campaign_type?: string;
  campaign_name_contains?: string;
  search_term_contains?: string;
  limit?: number;
  offset?: number;
};

export type SearchTermFactsResult = {
  facts: SearchTermFact[];
  limit: number;
  offset: number;
  has_more: boolean;
};

// ------------------------------------------------------------------
// API function
// ------------------------------------------------------------------

export const listSearchTermFacts = async (
  token: string,
  profileId: string,
  params: SearchTermFactsParams = {},
): Promise<SearchTermFactsResult> => {
  const query = new URLSearchParams();
  if (params.date_from) query.set("date_from", params.date_from);
  if (params.date_to) query.set("date_to", params.date_to);
  if (params.campaign_type) query.set("campaign_type", params.campaign_type);
  if (params.campaign_name_contains) query.set("campaign_name_contains", params.campaign_name_contains);
  if (params.search_term_contains) query.set("search_term_contains", params.search_term_contains);
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.offset !== undefined) query.set("offset", String(params.offset));

  const qs = query.toString();
  const payload = await requestJson<SearchTermFactsResult>(
    token,
    `/admin/wbr/profiles/${profileId}/search-term-facts${qs ? `?${qs}` : ""}`,
    { method: "GET" },
  );
  return payload;
};
