"use client";

export type SalesMixAdTypeKey =
  | "sponsored_products"
  | "sponsored_brands"
  | "sponsored_display";

export const SALES_MIX_AD_TYPE_KEYS: SalesMixAdTypeKey[] = [
  "sponsored_products",
  "sponsored_brands",
  "sponsored_display",
];

export type SalesMixAdTypeBreakdown = {
  ad_type: SalesMixAdTypeKey | string;
  label: string;
  ad_sales: string;
  ad_spend: string;
  ad_orders: number;
};

export type SalesMixWeek = {
  week_index: number;
  start: string;
  end: string;
  label: string;
  ad_sales: string;
  ad_spend: string;
  ad_orders: number;
  brand_sales: string;
  category_sales: string;
  unmapped_ad_sales: string;
  unmapped_ad_spend: string;
  business_sales: string;
  organic_sales: string;
  ad_type_breakdown: SalesMixAdTypeBreakdown[];
  coverage: {
    data_present: boolean;
    mapping_coverage_pct: number | null;
    below_threshold: boolean;
  };
};

export type SalesMixTotals = {
  ad_sales: string;
  ad_spend: string;
  ad_orders: number;
  brand_sales: string;
  category_sales: string;
  unmapped_ad_sales: string;
  unmapped_ad_spend: string;
  business_sales: string;
  organic_sales: string;
  mapping_coverage_pct: number | null;
  ads_share_of_business_pct: number | null;
};

export type SalesMixCoverage = {
  first_low_coverage_week: string | null;
  first_no_data_week: string | null;
  warn_threshold_pct: number;
  warnings: string[];
};

export type SalesMixParentRowOption = {
  id: string;
  row_label: string | null;
  sort_order: number | null;
};

export type SalesMixAdTypeOption = {
  key: string;
  label: string;
};

export type SalesMixReport = {
  profile: {
    id: string | null;
    display_name: string | null;
    marketplace_code: string | null;
    week_start_day: string | null;
  };
  date_from: string;
  date_to: string;
  filters: {
    parent_row_ids: string[];
    ad_types: string[];
  };
  parent_row_options: SalesMixParentRowOption[];
  ad_type_options: SalesMixAdTypeOption[];
  weeks: { start: string; end: string; label: string }[];
  weekly: SalesMixWeek[];
  totals: SalesMixTotals;
  coverage: SalesMixCoverage;
};

export type SalesMixQuery = {
  dateFrom: string;
  dateTo: string;
  parentRowIds?: string[];
  adTypes?: string[];
};

export type SalesMixExportResult = {
  blob: Blob;
  filename: string;
};

const getBackendUrl = (): string => {
  const url = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (!url) throw new Error("NEXT_PUBLIC_BACKEND_URL is not configured");
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

const parseAttachmentFilename = (response: Response, fallback: string): string => {
  const disposition =
    response.headers.get("Content-Disposition") || response.headers.get("content-disposition");
  if (!disposition) return fallback;
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }
  const plainMatch = disposition.match(/filename="?([^"]+)"?/i);
  return plainMatch?.[1] || fallback;
};

const parseAdTypeBreakdown = (value: unknown): SalesMixAdTypeBreakdown => {
  const r = isRecord(value) ? value : {};
  return {
    ad_type: asString(r.ad_type, "sponsored_products"),
    label: asString(r.label, "Sponsored Products"),
    ad_sales: asString(r.ad_sales, "0"),
    ad_spend: asString(r.ad_spend, "0"),
    ad_orders: asNumber(r.ad_orders),
  };
};

const parseWeek = (value: unknown): SalesMixWeek => {
  const r = isRecord(value) ? value : {};
  const cov = isRecord(r.coverage) ? r.coverage : {};
  return {
    week_index: asNumber(r.week_index),
    start: asString(r.start),
    end: asString(r.end),
    label: asString(r.label),
    ad_sales: asString(r.ad_sales, "0"),
    ad_spend: asString(r.ad_spend, "0"),
    ad_orders: asNumber(r.ad_orders),
    brand_sales: asString(r.brand_sales, "0"),
    category_sales: asString(r.category_sales, "0"),
    unmapped_ad_sales: asString(r.unmapped_ad_sales, "0"),
    unmapped_ad_spend: asString(r.unmapped_ad_spend, "0"),
    business_sales: asString(r.business_sales, "0"),
    organic_sales: asString(r.organic_sales, "0"),
    ad_type_breakdown: Array.isArray(r.ad_type_breakdown)
      ? r.ad_type_breakdown.map(parseAdTypeBreakdown)
      : [],
    coverage: {
      data_present: asBoolean(cov.data_present),
      mapping_coverage_pct: asNullableNumber(cov.mapping_coverage_pct),
      below_threshold: asBoolean(cov.below_threshold),
    },
  };
};

const parseReport = (value: unknown): SalesMixReport => {
  const r = isRecord(value) ? value : {};
  const profile = isRecord(r.profile) ? r.profile : {};
  const filters = isRecord(r.filters) ? r.filters : {};
  const totals = isRecord(r.totals) ? r.totals : {};
  const coverage = isRecord(r.coverage) ? r.coverage : {};
  return {
    profile: {
      id: asNullableString(profile.id),
      display_name: asNullableString(profile.display_name),
      marketplace_code: asNullableString(profile.marketplace_code),
      week_start_day: asNullableString(profile.week_start_day),
    },
    date_from: asString(r.date_from),
    date_to: asString(r.date_to),
    filters: {
      parent_row_ids: Array.isArray(filters.parent_row_ids)
        ? filters.parent_row_ids.filter((value) => typeof value === "string") as string[]
        : [],
      ad_types: Array.isArray(filters.ad_types)
        ? filters.ad_types.filter((value) => typeof value === "string") as string[]
        : [],
    },
    parent_row_options: Array.isArray(r.parent_row_options)
      ? r.parent_row_options.flatMap((entry) => {
          if (!isRecord(entry) || typeof entry.id !== "string") return [];
          return [
            {
              id: entry.id,
              row_label: asNullableString(entry.row_label),
              sort_order: asNullableNumber(entry.sort_order),
            },
          ];
        })
      : [],
    ad_type_options: Array.isArray(r.ad_type_options)
      ? r.ad_type_options.flatMap((entry) => {
          if (!isRecord(entry) || typeof entry.key !== "string") return [];
          return [{ key: entry.key, label: asString(entry.label, entry.key) }];
        })
      : [],
    weeks: Array.isArray(r.weeks)
      ? r.weeks.flatMap((entry) => {
          if (!isRecord(entry)) return [];
          return [
            {
              start: asString(entry.start),
              end: asString(entry.end),
              label: asString(entry.label),
            },
          ];
        })
      : [],
    weekly: Array.isArray(r.weekly) ? r.weekly.map(parseWeek) : [],
    totals: {
      ad_sales: asString(totals.ad_sales, "0"),
      ad_spend: asString(totals.ad_spend, "0"),
      ad_orders: asNumber(totals.ad_orders),
      brand_sales: asString(totals.brand_sales, "0"),
      category_sales: asString(totals.category_sales, "0"),
      unmapped_ad_sales: asString(totals.unmapped_ad_sales, "0"),
      unmapped_ad_spend: asString(totals.unmapped_ad_spend, "0"),
      business_sales: asString(totals.business_sales, "0"),
      organic_sales: asString(totals.organic_sales, "0"),
      mapping_coverage_pct: asNullableNumber(totals.mapping_coverage_pct),
      ads_share_of_business_pct: asNullableNumber(totals.ads_share_of_business_pct),
    },
    coverage: {
      first_low_coverage_week: asNullableString(coverage.first_low_coverage_week),
      first_no_data_week: asNullableString(coverage.first_no_data_week),
      warn_threshold_pct: asNumber(coverage.warn_threshold_pct, 0.8),
      warnings: Array.isArray(coverage.warnings)
        ? coverage.warnings.filter((value) => typeof value === "string") as string[]
        : [],
    },
  };
};

const buildQuery = (query: SalesMixQuery): URLSearchParams => {
  const params = new URLSearchParams({
    date_from: query.dateFrom,
    date_to: query.dateTo,
  });
  if (query.parentRowIds && query.parentRowIds.length) {
    params.set("parent_row_ids", query.parentRowIds.join(","));
  }
  if (query.adTypes && query.adTypes.length) {
    params.set("ad_types", query.adTypes.join(","));
  }
  return params;
};

export const getSalesMixReport = async (
  token: string,
  profileId: string,
  query: SalesMixQuery
): Promise<SalesMixReport> => {
  const params = buildQuery(query);
  const response = await fetch(
    `${getBackendUrl()}/admin/wbr/profiles/${profileId}/sales-mix?${params.toString()}`,
    { method: "GET", headers: { Authorization: `Bearer ${token}` } }
  );
  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new Error(detail);
  }
  return parseReport(await response.json());
};

export const exportSalesMixWorkbook = async (
  token: string,
  profileId: string,
  query: SalesMixQuery
): Promise<SalesMixExportResult> => {
  const params = buildQuery(query);
  const response = await fetch(
    `${getBackendUrl()}/admin/wbr/profiles/${profileId}/sales-mix/export.xlsx?${params.toString()}`,
    { method: "GET", headers: { Authorization: `Bearer ${token}` } }
  );
  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new Error(detail);
  }
  return {
    blob: await response.blob(),
    filename: parseAttachmentFilename(response, "sales-mix.xlsx"),
  };
};
