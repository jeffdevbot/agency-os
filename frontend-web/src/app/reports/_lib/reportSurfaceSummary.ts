import type { PnlProfile } from "../pnl/_lib/pnlApi";
import type { WbrProfile } from "../wbr/_lib/wbrApi";

export type ClientMarketplaceReportSurface = {
  marketplace_code: string;
  wbr_profile: WbrProfile | null;
  pnl_profile: PnlProfile | null;
};

const normalizeMarketplaceCode = (value: string): string => value.trim().toUpperCase();

export function buildClientMarketplaceReportSurfaces(
  wbrProfiles: WbrProfile[],
  pnlProfiles: PnlProfile[],
): ClientMarketplaceReportSurface[] {
  const surfaces = new Map<string, ClientMarketplaceReportSurface>();

  for (const profile of wbrProfiles) {
    const marketplaceCode = normalizeMarketplaceCode(profile.marketplace_code);
    const current = surfaces.get(marketplaceCode);
    surfaces.set(marketplaceCode, {
      marketplace_code: marketplaceCode,
      wbr_profile: profile,
      pnl_profile: current?.pnl_profile ?? null,
    });
  }

  for (const profile of pnlProfiles) {
    const marketplaceCode = normalizeMarketplaceCode(profile.marketplace_code);
    const current = surfaces.get(marketplaceCode);
    surfaces.set(marketplaceCode, {
      marketplace_code: marketplaceCode,
      wbr_profile: current?.wbr_profile ?? null,
      pnl_profile: profile,
    });
  }

  return Array.from(surfaces.values()).sort((a, b) =>
    a.marketplace_code.localeCompare(b.marketplace_code),
  );
}
