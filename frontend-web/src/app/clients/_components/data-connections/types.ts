import type { SpApiRegionCode } from "@/app/reports/_lib/reportApiAccessApi";

export type MarketplaceCode =
  | "CA"
  | "US"
  | "MX"
  | "UK"
  | "DE"
  | "FR"
  | "IT"
  | "ES"
  | "NL"
  | "SE"
  | "PL"
  | "TR"
  | "BE"
  | "EG"
  | "SA"
  | "ZA"
  | "AE"
  | "AU"
  | "JP"
  | "SG"
  | "IN";

export type WBRProfileSummary = {
  id: string;
  marketplace_code: string;
  display_name: string;
};

export type DomainKey = "business" | "ads" | "listings" | "inventory" | "returns";

export type DomainCoverage = {
  earliest: string | null;
  latest: string | null;
};

export type PerDomainCoverage = Record<DomainKey, DomainCoverage>;

export type BackfillRange = {
  dateFrom: string;
  dateTo: string;
};

export type BackfillRowState = {
  running: boolean;
  successMessage?: string | null;
  errorMessage?: string | null;
  lastRange?: BackfillRange | null;
};

export type RegionDefinition = {
  code: SpApiRegionCode;
  unlockedMarketplaces: string;
  marketplaceCodes: MarketplaceCode[];
};

export const MARKETPLACE_IDS_BY_CODE: Record<string, string> = {
  AE: "A2VIGQ35RCS4UG",
  AU: "A39IBJ37TRP1C6",
  BE: "AMEN7PMS3EDWL",
  CA: "A2EUQ1WTGCTBG2",
  DE: "A1PA6795UKMFR9",
  EG: "ARBP9OOSHTCHU",
  ES: "A1RKKUPIHCS9HS",
  FR: "A13V1IB3VIYZZH",
  IN: "A21TJRUUN4KGV",
  IT: "APJ6JRA9NG5V4",
  JP: "A1VC38T7YXB528",
  MX: "A1AM78C64UM0Y8",
  NL: "A1805IZSGTT6HS",
  PL: "A1C3SOZRARQ6R3",
  SA: "A17E79C6D8DWNP",
  SE: "A2NODRKZP88ZB9",
  SG: "A19VAU5U5O7RUS",
  TR: "A33AVAJ2PDY3EV",
  UK: "A1F83G8C2ARO7P",
  US: "ATVPDKIKX0DER",
  ZA: "AE08WJ6YKNBMC",
};

export const EMPTY_COVERAGE: DomainCoverage = {
  earliest: null,
  latest: null,
};

export const EMPTY_PROFILE_COVERAGE: PerDomainCoverage = {
  business: EMPTY_COVERAGE,
  ads: EMPTY_COVERAGE,
  listings: EMPTY_COVERAGE,
  inventory: EMPTY_COVERAGE,
  returns: EMPTY_COVERAGE,
};
