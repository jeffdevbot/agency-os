"use server";

import { unstable_cache } from "next/cache";

export type OpenAIDailyCost = {
  date: string; // YYYY-MM-DD
  amount: number;
  currency: string; // e.g. "usd"
};

type OpenAICostBucket = {
  start_time_iso?: string;
  results?: Array<{
    amount?: { value?: string | number; currency?: string } | number;
  }>;
};

type OpenAICostsResponse = {
  object?: string;
  data?: OpenAICostBucket[];
  has_more?: boolean;
  next_page?: string | null;
};

const getAdminApiKey = (): string => {
  const key = process.env.OPENAI_ADMIN_API_KEY;
  if (!key) throw new Error("OPENAI_ADMIN_API_KEY is not configured");
  return key;
};

const getOrgId = (): string | null => {
  const orgId = process.env.OPENAI_ORG_ID;
  return orgId ? String(orgId).trim() : null;
};

const parseAmount = (raw: unknown): { amount: number; currency: string | null } => {
  if (typeof raw === "number") return { amount: raw, currency: null };

  if (raw && typeof raw === "object") {
    const maybe = raw as { value?: unknown; currency?: unknown };
    const value = maybe.value;
    const currency = typeof maybe.currency === "string" ? maybe.currency : null;
    if (typeof value === "number") return { amount: value, currency };
    if (typeof value === "string") {
      const parsed = Number.parseFloat(value);
      return { amount: Number.isFinite(parsed) ? parsed : 0, currency };
    }
  }

  return { amount: 0, currency: null };
};

const fetchCostsUncached = async (days: number): Promise<OpenAIDailyCost[]> => {
  // Use complete days only: [start_time, end_time) where end_time is start of today UTC.
  const now = new Date();
  const endTime = Math.floor(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()) / 1000);
  const startTime = endTime - days * 24 * 60 * 60;

  const headers: Record<string, string> = {
    Authorization: `Bearer ${getAdminApiKey()}`,
  };
  const orgId = getOrgId();
  if (orgId) headers["OpenAI-Organization"] = orgId;

  const endpointCandidates = [
    // Prompt requested this path, but OpenAI may return 404 depending on account/API version.
    "https://api.openai.com/v1/organization/usage/costs",
    // This is the endpoint that currently responds for org-level costs.
    "https://api.openai.com/v1/organization/costs",
  ];

  let lastError: Error | null = null;

  for (const endpoint of endpointCandidates) {
    try {
      const buckets: OpenAICostBucket[] = [];
      let pageToken: string | null = null;

      for (let page = 0; page < 20; page += 1) {
        const url = new URL(endpoint);
        url.searchParams.set("start_time", String(startTime));
        url.searchParams.set("end_time", String(endTime));
        url.searchParams.set("group_by", "line_item");
        if (pageToken) url.searchParams.set("page", pageToken);

        const response = await fetch(url.toString(), {
          headers,
          next: { revalidate: 3600 },
        });

        if (!response.ok) {
          const text = await response.text().catch(() => "");
          // If the first endpoint is missing, try the fallback endpoint.
          if (response.status === 404) throw new Error(`Not found: ${endpoint}`);
          throw new Error(`OpenAI costs error (${response.status}): ${text || response.statusText}`);
        }

        const json = (await response.json()) as OpenAICostsResponse;
        buckets.push(...(Array.isArray(json.data) ? json.data : []));

        if (json.has_more && json.next_page) {
          pageToken = json.next_page;
          continue;
        }

        break;
      }

      const daily = new Map<string, { amount: number; currency: string }>();

      for (const bucket of buckets) {
        const iso = bucket.start_time_iso;
        if (!iso) continue;
        const date = iso.slice(0, 10);

        let sum = 0;
        let currency: string | null = null;
        for (const r of bucket.results ?? []) {
          const parsed = parseAmount(r.amount);
          sum += parsed.amount;
          currency = currency ?? parsed.currency;
        }

        const existing = daily.get(date);
        if (existing) {
          existing.amount += sum;
        } else {
          daily.set(date, { amount: sum, currency: currency ?? "usd" });
        }
      }

      const fallbackCurrency = Array.from(daily.values())[0]?.currency ?? "usd";

      const filled: OpenAIDailyCost[] = Array.from({ length: days }, (_, idx) => {
        const date = new Date((startTime + idx * 24 * 60 * 60) * 1000).toISOString().slice(0, 10);
        const entry = daily.get(date);
        return { date, amount: entry?.amount ?? 0, currency: entry?.currency ?? fallbackCurrency };
      });

      return filled;
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
    }
  }

  throw lastError ?? new Error("Unable to fetch OpenAI costs");
};

export const getOpenAICosts = async (days: number = 30): Promise<OpenAIDailyCost[]> => {
  const safeDays = Number.isFinite(days) && days > 0 ? Math.min(Math.floor(days), 90) : 30;
  const cached = unstable_cache(
    async () => fetchCostsUncached(safeDays),
    ["openai-org-costs", String(safeDays)],
    { revalidate: 3600 },
  );
  return cached();
};
