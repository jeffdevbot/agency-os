import type { ClientProfileSummary } from "../reports/_lib/reportClientData";
import type { SearchTermAdProductKey } from "../reports/_lib/searchTermProducts";
import type { WbrProfile } from "../reports/wbr/_lib/wbrApi";

export type NativeNgramClientOption = {
  clientId: string;
  clientName: string;
  profileCount: number;
};

export type NativeNgramProfileOption = {
  profileId: string;
  clientId: string;
  clientName: string;
  displayName: string;
  marketplaceCode: string;
  currencyCode: string | null;
  profileStatus: string;
  hasAmazonAdsConnection: boolean;
  hasSearchTermSync: boolean;
  nightlyByProduct: Record<SearchTermAdProductKey, boolean>;
};

const hasSearchTermCapability = (profile: WbrProfile): boolean => Boolean(profile.amazon_ads_profile_id);

export const buildNativeNgramClientOptions = (
  summaries: ClientProfileSummary[],
): NativeNgramClientOption[] =>
  summaries
    .filter((summary) => summary.profiles.some(hasSearchTermCapability))
    .map((summary) => ({
      clientId: summary.client.id,
      clientName: summary.client.name,
      profileCount: summary.profiles.filter(hasSearchTermCapability).length,
    }))
    .sort((left, right) => left.clientName.localeCompare(right.clientName));

export const buildNativeNgramProfileOptions = (
  summaries: ClientProfileSummary[],
  clientId: string | null,
): NativeNgramProfileOption[] => {
  const summary = summaries.find((item) => item.client.id === clientId);
  if (!summary) return [];

  return summary.profiles
    .filter(hasSearchTermCapability)
    .map((profile) => ({
      profileId: profile.id,
      clientId: summary.client.id,
      clientName: summary.client.name,
      displayName: profile.display_name,
      marketplaceCode: profile.marketplace_code,
      currencyCode: profile.amazon_ads_currency_code,
      profileStatus: profile.status,
      hasAmazonAdsConnection: Boolean(profile.amazon_ads_profile_id),
      hasSearchTermSync:
        profile.search_term_auto_sync_enabled ||
        profile.search_term_sb_auto_sync_enabled ||
        profile.search_term_sd_auto_sync_enabled,
      nightlyByProduct: {
        sp: profile.search_term_auto_sync_enabled,
        sb: profile.search_term_sb_auto_sync_enabled,
        sd: profile.search_term_sd_auto_sync_enabled,
      },
    }))
    .sort((left, right) =>
      left.marketplaceCode.localeCompare(right.marketplaceCode) ||
      left.displayName.localeCompare(right.displayName),
    );
};

export const getNativeNgramValidationChecklist = (
  productKey: SearchTermAdProductKey,
): string[] => {
  if (productKey === "sp") {
    return [
      "Compare clicks, spend, orders, and sales against the matching Amazon Sponsored Products Search term export.",
      "Do not compare against broader Campaign Manager totals for impressions; the search-term export is narrower.",
      "If the selected window matches the export on clicks/spend/sales, the native workbook input is trustworthy.",
    ];
  }

  if (productKey === "sb") {
    return [
      "Compare the selected window against the Amazon Sponsored Brands Search term export, not the Keyword report.",
      "Sponsored Brands is still in beta here because at least one branded defensive campaign family is present in export but absent from native sbSearchTerm API rows.",
      "Treat workbook output as controlled validation until the export parity gap is closed or proven to be Amazon-side.",
    ];
  }

  return [
    "Sponsored Display is not yet modeled as a native search-term source.",
    "Use the legacy tool or a manual export path until the right native report family is confirmed.",
  ];
};

export const buildNativeNgramDefaultDateRange = (): { from: string; to: string } => {
  const today = new Date();
  const to = new Date(today);
  to.setDate(today.getDate() - 1);
  const from = new Date(to);
  from.setDate(to.getDate() - 13);

  const format = (value: Date) => {
    const year = value.getFullYear();
    const month = `${value.getMonth() + 1}`.padStart(2, "0");
    const day = `${value.getDate()}`.padStart(2, "0");
    return `${year}-${month}-${day}`;
  };

  return {
    from: format(from),
    to: format(to),
  };
};

export const countInclusiveDays = (from: string, to: string): number | null => {
  if (!from || !to) return null;
  const [startYear, startMonth, startDay] = from.split("-").map(Number);
  const [endYear, endMonth, endDay] = to.split("-").map(Number);
  if (
    [startYear, startMonth, startDay, endYear, endMonth, endDay].some((value) => !Number.isFinite(value))
  ) {
    return null;
  }

  const start = Date.UTC(startYear, startMonth - 1, startDay);
  const end = Date.UTC(endYear, endMonth - 1, endDay);
  if (start > end) {
    return null;
  }

  const millisecondsPerDay = 24 * 60 * 60 * 1000;
  return Math.floor((end - start) / millisecondsPerDay) + 1;
};

export const getNativeNgramRunState = (
  profile: NativeNgramProfileOption | null,
  productKey: SearchTermAdProductKey,
): {
  label: string;
  tone: "ready" | "caution" | "blocked";
  note: string;
} => {
  if (!profile) {
    return {
      label: "Choose a marketplace",
      tone: "blocked",
      note: "Pick a connected marketplace before creating a native run.",
    };
  }

  if (!profile.hasAmazonAdsConnection) {
    return {
      label: "Connection required",
      tone: "blocked",
      note: "This marketplace needs an Amazon Ads connection before native data can be used.",
    };
  }

  if (productKey === "sp") {
    return {
      label: "Ready now",
      tone: "ready",
      note: "Sponsored Products is validated against real exports and is the safest first workbook source.",
    };
  }

  if (productKey === "sb") {
    return {
      label: "Controlled validation",
      tone: "caution",
      note: "Sponsored Brands is live but still has an unresolved export parity gap on at least one branded defensive campaign family.",
    };
  }

  return {
    label: "Not ready",
    tone: "blocked",
    note: "Sponsored Display should stay on the legacy/manual path until its native report family is modeled correctly.",
  };
};
