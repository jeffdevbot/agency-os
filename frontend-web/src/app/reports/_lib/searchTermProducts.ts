import type { WbrProfile } from "../wbr/_lib/wbrApi";

export type SearchTermAdProductKey = "sp" | "sb" | "sd";
type SearchTermAutoSyncField =
  | "search_term_auto_sync_enabled"
  | "search_term_sb_auto_sync_enabled"
  | "search_term_sd_auto_sync_enabled";

export type SearchTermAdProductConfig = {
  key: SearchTermAdProductKey;
  label: string;
  shortLabel: string;
  amazonAdsAdProduct: string | null;
  campaignType: string | null;
  reportTypeId: string | null;
  autoSyncField: SearchTermAutoSyncField;
  status: "live" | "beta" | "planned";
  summary: string;
  availabilityNote: string;
};

export const SEARCH_TERM_AD_PRODUCTS: SearchTermAdProductConfig[] = [
  {
    key: "sp",
    label: "Sponsored Products",
    shortLabel: "SP",
    amazonAdsAdProduct: "SPONSORED_PRODUCTS",
    campaignType: "sponsored_products",
    reportTypeId: "spSearchTerm",
    autoSyncField: "search_term_auto_sync_enabled",
    status: "live",
    summary: "Validated Amazon-native search-term sync path.",
    availabilityNote: "Live and validated against a real Amazon search-term export.",
  },
  {
    key: "sb",
    label: "Sponsored Brands",
    shortLabel: "SB",
    amazonAdsAdProduct: "SPONSORED_BRANDS",
    campaignType: "sponsored_brands",
    reportTypeId: "sbSearchTerm",
    autoSyncField: "search_term_sb_auto_sync_enabled",
    status: "beta",
    summary: "Native SB search-term sync path with live contract verification completed.",
    availabilityNote: "Ready for controlled live backfills and export parity validation.",
  },
  {
    key: "sd",
    label: "Sponsored Display",
    shortLabel: "SD",
    amazonAdsAdProduct: "SPONSORED_DISPLAY",
    campaignType: null,
    reportTypeId: null,
    autoSyncField: "search_term_sd_auto_sync_enabled",
    status: "planned",
    summary: "Likely requires adjacent native report families rather than SP-style search terms.",
    availabilityNote: "Not yet modeled as a native search-term sync. Validation still pending.",
  },
];

export const LIVE_SEARCH_TERM_AD_PRODUCT =
  SEARCH_TERM_AD_PRODUCTS.find((product) => product.status === "live") ?? SEARCH_TERM_AD_PRODUCTS[0];

export const ACTIVE_SEARCH_TERM_AD_PRODUCTS = SEARCH_TERM_AD_PRODUCTS.filter(
  (product) => product.status === "live" || product.status === "beta",
);

export const FUTURE_SEARCH_TERM_AD_PRODUCTS = SEARCH_TERM_AD_PRODUCTS.filter(
  (product) => product.status === "planned",
);

export const getSearchTermAutoSyncEnabled = (
  profile: WbrProfile,
  product: SearchTermAdProductConfig,
): boolean => profile[product.autoSyncField];
