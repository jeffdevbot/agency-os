import type { NgramListingRow } from "./aiPrefill";

export type CatalogSourceProfile = {
  profileId: string;
  clientId: string | null;
  displayName: string | null;
  marketplaceCode: string | null;
};

export type CatalogSourceCandidate = CatalogSourceProfile & {
  listings: NgramListingRow[];
};

export type ResolvedCatalogSource = {
  listings: NgramListingRow[];
  sourceProfileId: string;
  sourceDisplayName: string | null;
  sourceMarketplaceCode: string | null;
  usedFallback: boolean;
  warning: string | null;
};

const normalizeKey = (value: string | null | undefined): string =>
  String(value || "").trim().toLowerCase();

const displayProfileLabel = (profile: CatalogSourceProfile): string => {
  const displayName = String(profile.displayName || "").trim();
  const marketplaceCode = String(profile.marketplaceCode || "").trim().toUpperCase();
  if (displayName && marketplaceCode) return `${displayName} ${marketplaceCode}`;
  return displayName || marketplaceCode || profile.profileId;
};

export const resolveCatalogSource = (
  requestedProfile: CatalogSourceProfile,
  requestedListings: NgramListingRow[],
  siblingCandidates: CatalogSourceCandidate[],
): ResolvedCatalogSource => {
  if (requestedListings.length > 0) {
    return {
      listings: requestedListings,
      sourceProfileId: requestedProfile.profileId,
      sourceDisplayName: requestedProfile.displayName,
      sourceMarketplaceCode: requestedProfile.marketplaceCode,
      usedFallback: false,
      warning: null,
    };
  }

  const requestedDisplayKey = normalizeKey(requestedProfile.displayName);
  const rankedCandidates = siblingCandidates
    .filter((candidate) => candidate.listings.length > 0)
    .sort((left, right) => {
      const leftSameDisplay = normalizeKey(left.displayName) === requestedDisplayKey ? 1 : 0;
      const rightSameDisplay = normalizeKey(right.displayName) === requestedDisplayKey ? 1 : 0;
      if (leftSameDisplay !== rightSameDisplay) return rightSameDisplay - leftSameDisplay;
      if (left.listings.length !== right.listings.length) return right.listings.length - left.listings.length;
      return displayProfileLabel(left).localeCompare(displayProfileLabel(right));
    });

  const fallback = rankedCandidates[0];
  if (!fallback) {
    throw new Error(
      "No active Windsor child ASIN catalog rows were found for this profile. Import Windsor listings for this marketplace before running AI preview.",
    );
  }

  const fallbackDisplayKey = normalizeKey(fallback.displayName);
  const sameDisplayName =
    Boolean(requestedDisplayKey) && Boolean(fallbackDisplayKey) && requestedDisplayKey === fallbackDisplayKey;

  if (!sameDisplayName) {
    throw new Error(
      "No active Windsor child ASIN catalog rows were found for this profile. Import Windsor listings for this marketplace before running AI preview.",
    );
  }

  return {
    listings: fallback.listings,
    sourceProfileId: fallback.profileId,
    sourceDisplayName: fallback.displayName,
    sourceMarketplaceCode: fallback.marketplaceCode,
    usedFallback: true,
    warning: `Using Windsor catalog context from ${displayProfileLabel(fallback)} because ${displayProfileLabel(requestedProfile)} has no active catalog rows.`,
  };
};
