export type SearchTermAdProductKey = "sp" | "sb" | "sd";

export type SearchTermAdProductConfig = {
  key: SearchTermAdProductKey;
  label: string;
  shortLabel: string;
  amazonAdsAdProduct: string | null;
  status: "live" | "planned";
  summary: string;
  availabilityNote: string;
};

export const SEARCH_TERM_AD_PRODUCTS: SearchTermAdProductConfig[] = [
  {
    key: "sp",
    label: "Sponsored Products",
    shortLabel: "SP",
    amazonAdsAdProduct: "SPONSORED_PRODUCTS",
    status: "live",
    summary: "Validated Amazon-native search-term sync path.",
    availabilityNote: "Live and validated against a real Amazon search-term export.",
  },
  {
    key: "sb",
    label: "Sponsored Brands",
    shortLabel: "SB",
    amazonAdsAdProduct: "SPONSORED_BRANDS",
    status: "planned",
    summary: "Next planned native search-term sync validation slice.",
    availabilityNote: "Report contract not yet verified. Controls stay disabled until live validation.",
  },
  {
    key: "sd",
    label: "Sponsored Display",
    shortLabel: "SD",
    amazonAdsAdProduct: "SPONSORED_DISPLAY",
    status: "planned",
    summary: "Likely requires adjacent native report families rather than SP-style search terms.",
    availabilityNote: "Not yet modeled as a native search-term sync. Validation still pending.",
  },
];

export const LIVE_SEARCH_TERM_AD_PRODUCT =
  SEARCH_TERM_AD_PRODUCTS.find((product) => product.status === "live") ?? SEARCH_TERM_AD_PRODUCTS[0];

export const FUTURE_SEARCH_TERM_AD_PRODUCTS = SEARCH_TERM_AD_PRODUCTS.filter(
  (product) => product.status !== "live",
);
