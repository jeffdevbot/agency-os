"use client";

import type { SpApiRegionCode } from "@/app/reports/_lib/reportApiAccessApi";
import DomainBackfillRow, { type DomainBackfillVariant } from "./DomainBackfillRow";
import type { ProviderConnectionState } from "./ProviderConnectionCard";
import {
  EMPTY_COVERAGE,
  MARKETPLACE_IDS_BY_CODE,
  type BackfillRange,
  type BackfillRowState,
  type PerDomainCoverage,
  type WBRProfileSummary,
} from "./types";

type Props = {
  profile: WBRProfileSummary;
  region: SpApiRegionCode;
  spApiConnectionState: ProviderConnectionState;
  backfillCoverage: PerDomainCoverage;
  businessState?: BackfillRowState;
  listingsState?: BackfillRowState;
  onRunBusinessBackfill(profileId: string, range: BackfillRange): void;
  onRunListingsBackfill(profileId: string, range: BackfillRange): void;
  onRetryBusinessBackfill(profileId: string): void;
  onRetryListingsBackfill(profileId: string): void;
};

export default function MarketplaceCard({
  profile,
  spApiConnectionState,
  backfillCoverage,
  businessState,
  listingsState,
  onRunBusinessBackfill,
  onRunListingsBackfill,
  onRetryBusinessBackfill,
  onRetryListingsBackfill,
}: Props) {
  const marketplaceCode = profile.marketplace_code.toUpperCase();
  const marketplaceId = MARKETPLACE_IDS_BY_CODE[marketplaceCode] ?? "unmapped";
  const liveVariant: DomainBackfillVariant =
    spApiConnectionState === "connected" ? "active" : "needs_connection";

  return (
    <article className="rounded-3xl border border-slate-200/80 bg-white/75 p-5 shadow-inner">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-baseline gap-3">
            <h3 className="text-xl font-semibold text-slate-950">{marketplaceCode}</h3>
            <p className="text-sm font-medium text-slate-500">{profile.display_name}</p>
          </div>
        </div>
        <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-500">
          Marketplace {marketplaceId}
        </span>
      </div>

      <div className="mt-4 space-y-3">
        <DomainBackfillRow
          domain="Business"
          variant={liveVariant}
          coverage={backfillCoverage.business ?? EMPTY_COVERAGE}
          rowState={businessState}
          onRun={(range) => onRunBusinessBackfill(profile.id, range)}
          onRetry={() => onRetryBusinessBackfill(profile.id)}
        />
        <DomainBackfillRow
          domain="Ads"
          variant="read_only"
          coverage={backfillCoverage.ads ?? EMPTY_COVERAGE}
        />
        <DomainBackfillRow
          domain="Listings"
          variant={liveVariant}
          coverage={backfillCoverage.listings ?? EMPTY_COVERAGE}
          rowState={listingsState}
          onRun={(range) => onRunListingsBackfill(profile.id, range)}
          onRetry={() => onRetryListingsBackfill(profile.id)}
        />
        <DomainBackfillRow
          domain="Inventory"
          variant="coming_soon"
          coverage={backfillCoverage.inventory ?? EMPTY_COVERAGE}
        />
        <DomainBackfillRow
          domain="Returns"
          variant="coming_soon"
          coverage={backfillCoverage.returns ?? EMPTY_COVERAGE}
        />
      </div>
    </article>
  );
}
