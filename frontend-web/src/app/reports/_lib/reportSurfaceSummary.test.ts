import { describe, expect, it } from "vitest";
import { buildClientMarketplaceReportSurfaces } from "./reportSurfaceSummary";

describe("buildClientMarketplaceReportSurfaces", () => {
  it("merges WBR and Monthly P&L profiles by marketplace", () => {
    const surfaces = buildClientMarketplaceReportSurfaces(
      [
        {
          id: "wbr-us",
          client_id: "client-1",
          marketplace_code: "us",
          display_name: "US Ops",
          week_start_day: "monday",
          status: "active",
          windsor_account_id: null,
          amazon_ads_profile_id: null,
          amazon_ads_account_id: null,
          backfill_start_date: null,
          daily_rewrite_days: 14,
          sp_api_auto_sync_enabled: false,
          ads_api_auto_sync_enabled: false,
          created_at: null,
          updated_at: null,
        },
      ],
      [
        {
          id: "pnl-ca",
          client_id: "client-1",
          marketplace_code: "CA",
          currency_code: "USD",
          status: "active",
          notes: null,
          created_at: null,
          updated_at: null,
        },
        {
          id: "pnl-us",
          client_id: "client-1",
          marketplace_code: "US",
          currency_code: "USD",
          status: "active",
          notes: null,
          created_at: null,
          updated_at: null,
        },
      ],
    );

    expect(surfaces).toHaveLength(2);
    expect(surfaces[0]?.marketplace_code).toBe("CA");
    expect(surfaces[0]?.wbr_profile).toBeNull();
    expect(surfaces[0]?.pnl_profile?.id).toBe("pnl-ca");
    expect(surfaces[1]?.marketplace_code).toBe("US");
    expect(surfaces[1]?.wbr_profile?.id).toBe("wbr-us");
    expect(surfaces[1]?.pnl_profile?.id).toBe("pnl-us");
  });
});
