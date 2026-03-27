import { describe, expect, it } from "vitest";

import {
  buildNativeNgramClientOptions,
  buildNativeNgramDefaultDateRange,
  buildNativeNgramProfileOptions,
  countInclusiveDays,
  getNativeNgramRunState,
  getNativeNgramValidationChecklist,
} from "./ngram2Presentation";
import type { ClientProfileSummary } from "../reports/_lib/reportClientData";

const summaries: ClientProfileSummary[] = [
  {
    client: {
      id: "client-b",
      name: "Bravo",
      status: "active",
    },
    profiles: [
      {
        id: "profile-b-us",
        client_id: "client-b",
        marketplace_code: "US",
        display_name: "Bravo US",
        week_start_day: "sunday",
        status: "active",
        windsor_account_id: null,
        amazon_ads_profile_id: "ads-b-us",
        amazon_ads_account_id: null,
        amazon_ads_country_code: "US",
        amazon_ads_currency_code: "USD",
        amazon_ads_marketplace_string_id: null,
        backfill_start_date: null,
        daily_rewrite_days: 7,
        sp_api_auto_sync_enabled: false,
        ads_api_auto_sync_enabled: false,
        search_term_auto_sync_enabled: true,
        search_term_sb_auto_sync_enabled: false,
        search_term_sd_auto_sync_enabled: false,
        created_at: null,
        updated_at: null,
      },
    ],
  },
  {
    client: {
      id: "client-a",
      name: "Alpha",
      status: "active",
    },
    profiles: [
      {
        id: "profile-a-ca",
        client_id: "client-a",
        marketplace_code: "CA",
        display_name: "Alpha CA",
        week_start_day: "monday",
        status: "active",
        windsor_account_id: null,
        amazon_ads_profile_id: "ads-a-ca",
        amazon_ads_account_id: null,
        amazon_ads_country_code: "CA",
        amazon_ads_currency_code: "CAD",
        amazon_ads_marketplace_string_id: null,
        backfill_start_date: null,
        daily_rewrite_days: 7,
        sp_api_auto_sync_enabled: false,
        ads_api_auto_sync_enabled: false,
        search_term_auto_sync_enabled: false,
        search_term_sb_auto_sync_enabled: true,
        search_term_sd_auto_sync_enabled: false,
        created_at: null,
        updated_at: null,
      },
      {
        id: "profile-a-uk",
        client_id: "client-a",
        marketplace_code: "UK",
        display_name: "Alpha UK",
        week_start_day: "monday",
        status: "active",
        windsor_account_id: null,
        amazon_ads_profile_id: null,
        amazon_ads_account_id: null,
        amazon_ads_country_code: "UK",
        amazon_ads_currency_code: "GBP",
        amazon_ads_marketplace_string_id: null,
        backfill_start_date: null,
        daily_rewrite_days: 7,
        sp_api_auto_sync_enabled: false,
        ads_api_auto_sync_enabled: false,
        search_term_auto_sync_enabled: false,
        search_term_sb_auto_sync_enabled: false,
        search_term_sd_auto_sync_enabled: false,
        created_at: null,
        updated_at: null,
      },
    ],
  },
];

describe("ngram2Presentation", () => {
  it("builds sorted client options only for clients with Amazon Ads-backed profiles", () => {
    expect(buildNativeNgramClientOptions(summaries)).toEqual([
      { clientId: "client-a", clientName: "Alpha", profileCount: 1 },
      { clientId: "client-b", clientName: "Bravo", profileCount: 1 },
    ]);
  });

  it("filters marketplace options to the selected client and connected profiles", () => {
    expect(buildNativeNgramProfileOptions(summaries, "client-a")).toEqual([
      {
        profileId: "profile-a-ca",
        clientId: "client-a",
        clientName: "Alpha",
        displayName: "Alpha CA",
        marketplaceCode: "CA",
        profileStatus: "active",
        hasAmazonAdsConnection: true,
        hasSearchTermSync: true,
        nightlyByProduct: {
          sp: false,
          sb: true,
          sd: false,
        },
      },
    ]);
  });

  it("returns product-specific validation guidance", () => {
    expect(getNativeNgramValidationChecklist("sp")[0]).toContain("Sponsored Products");
    expect(getNativeNgramValidationChecklist("sb")[1]).toContain("beta");
    expect(getNativeNgramValidationChecklist("sd")[0]).toContain("Sponsored Display");
  });

  it("builds an ISO date range ending yesterday", () => {
    const range = buildNativeNgramDefaultDateRange();
    expect(range.from).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(range.to).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(range.from <= range.to).toBe(true);
  });

  it("counts inclusive date spans and returns null for invalid ranges", () => {
    expect(countInclusiveDays("2026-03-01", "2026-03-14")).toBe(14);
    expect(countInclusiveDays("2026-03-14", "2026-03-01")).toBeNull();
  });

  it("returns product-specific native run readiness states", () => {
    const profile = buildNativeNgramProfileOptions(summaries, "client-a")[0] ?? null;
    expect(getNativeNgramRunState(profile, "sp").tone).toBe("ready");
    expect(getNativeNgramRunState(profile, "sb").tone).toBe("caution");
    expect(getNativeNgramRunState(profile, "sd").tone).toBe("blocked");
  });
});
