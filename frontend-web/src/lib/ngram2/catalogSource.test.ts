import { describe, expect, it } from "vitest";

import { resolveCatalogSource, type CatalogSourceCandidate, type CatalogSourceProfile } from "./catalogSource";

const requestedProfile: CatalogSourceProfile = {
  profileId: "profile-ca",
  clientId: "client-1",
  displayName: "Whoosh",
  marketplaceCode: "CA",
};

const listingRow = {
  child_asin: "B000TEST01",
  child_sku: "SKU-1",
  child_product_name: "Whoosh Screen Shine Pro",
  parent_title: null,
  category: "Cleaners",
  item_description: null,
};

describe("resolveCatalogSource", () => {
  it("uses the requested profile when active catalog rows exist", () => {
    const result = resolveCatalogSource(requestedProfile, [listingRow], []);

    expect(result.usedFallback).toBe(false);
    expect(result.sourceProfileId).toBe("profile-ca");
    expect(result.listings).toEqual([listingRow]);
    expect(result.warning).toBeNull();
  });

  it("falls back to a same-client sibling with the same display name", () => {
    const sibling: CatalogSourceCandidate = {
      profileId: "profile-us",
      clientId: "client-1",
      displayName: "Whoosh",
      marketplaceCode: "US",
      listings: [listingRow],
    };

    const result = resolveCatalogSource(requestedProfile, [], [sibling]);

    expect(result.usedFallback).toBe(true);
    expect(result.sourceProfileId).toBe("profile-us");
    expect(result.sourceMarketplaceCode).toBe("US");
    expect(result.warning).toContain("Whoosh US");
    expect(result.warning).toContain("Whoosh CA");
  });

  it("does not fall back to a different display name", () => {
    const sibling: CatalogSourceCandidate = {
      profileId: "profile-us",
      clientId: "client-1",
      displayName: "Another Brand",
      marketplaceCode: "US",
      listings: [listingRow],
    };

    expect(() => resolveCatalogSource(requestedProfile, [], [sibling])).toThrow(
      "No active Windsor child ASIN catalog rows were found for this profile. Import Windsor listings for this marketplace before running AI preview.",
    );
  });

  it("fails clearly when no catalog rows exist anywhere relevant", () => {
    expect(() => resolveCatalogSource(requestedProfile, [], [])).toThrow(
      "No active Windsor child ASIN catalog rows were found for this profile. Import Windsor listings for this marketplace before running AI preview.",
    );
  });
});
