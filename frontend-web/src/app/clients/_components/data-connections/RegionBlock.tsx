"use client";

import type { SpApiRegionCode } from "@/app/reports/_lib/reportApiAccessApi";
import ConnectionsStrip, { type ConnectionCardModel } from "./ConnectionsStrip";
import MarketplaceCard from "./MarketplaceCard";
import type { ProviderKind } from "./ProviderConnectionCard";
import {
  EMPTY_PROFILE_COVERAGE,
  type BackfillRange,
  type BackfillRowState,
  type PerDomainCoverage,
  type WBRProfileSummary,
} from "./types";

type Props = {
  region: SpApiRegionCode;
  unlockedMarketplaces: string;
  adsConnection: ConnectionCardModel;
  spApiConnection: ConnectionCardModel;
  profiles: WBRProfileSummary[];
  coverageByProfileId: Record<string, PerDomainCoverage>;
  businessBackfillStates: Record<string, BackfillRowState>;
  listingsBackfillStates: Record<string, BackfillRowState>;
  hasAnyConnection: boolean;
  pendingAction?: string | null;
  onConnect(provider: ProviderKind, region: SpApiRegionCode): void;
  onValidate(provider: ProviderKind, region: SpApiRegionCode): void;
  onDisconnect(provider: ProviderKind, region: SpApiRegionCode): void;
  onRunBusinessBackfill(profileId: string, range: BackfillRange): void;
  onRunListingsBackfill(profileId: string, range: BackfillRange): void;
  onRetryBusinessBackfill(profileId: string): void;
  onRetryListingsBackfill(profileId: string): void;
};

export default function RegionBlock({
  region,
  unlockedMarketplaces,
  adsConnection,
  spApiConnection,
  profiles,
  coverageByProfileId,
  businessBackfillStates,
  listingsBackfillStates,
  hasAnyConnection,
  pendingAction,
  onConnect,
  onValidate,
  onDisconnect,
  onRunBusinessBackfill,
  onRunListingsBackfill,
  onRetryBusinessBackfill,
  onRetryListingsBackfill,
}: Props) {
  if (!hasAnyConnection) {
    return (
      <section className="rounded-3xl border border-white/70 bg-white/55 p-5 shadow-sm backdrop-blur">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="flex items-baseline gap-3">
              <h2 className="text-xl font-semibold text-slate-950">{region}</h2>
              <p className="text-sm font-medium text-slate-500">{unlockedMarketplaces}</p>
            </div>
            <p className="mt-2 text-sm text-slate-600">
              No connections in {region} yet. Authorize to unlock {unlockedMarketplaces.replace("Unlocks ", "")}.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => onConnect("amazon-ads", region)}
              disabled={pendingAction === `${region}:amazon-ads`}
              className="rounded-xl border border-slate-300 bg-white/70 px-4 py-2.5 text-sm font-semibold text-slate-800 transition hover:border-slate-500 hover:bg-white disabled:cursor-not-allowed disabled:text-slate-400"
            >
              + Connect Amazon Ads
            </button>
            <button
              type="button"
              onClick={() => onConnect("sp-api", region)}
              disabled={pendingAction === `${region}:sp-api`}
              className="rounded-xl border border-slate-300 bg-white/70 px-4 py-2.5 text-sm font-semibold text-slate-800 transition hover:border-slate-500 hover:bg-white disabled:cursor-not-allowed disabled:text-slate-400"
            >
              + Connect SP-API
            </button>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-3xl border border-white/80 bg-white/80 p-6 shadow-[0_18px_55px_rgba(15,23,42,0.08)] backdrop-blur">
      <div className="mb-5">
        <div className="flex items-baseline gap-3">
          <h2 className="text-xl font-semibold text-slate-950">{region}</h2>
          <p className="text-sm font-medium text-slate-500">{unlockedMarketplaces}</p>
        </div>
      </div>
      <ConnectionsStrip
        region={region}
        adsConnection={adsConnection}
        spApiConnection={spApiConnection}
        pendingAction={pendingAction}
        onConnect={(provider) => onConnect(provider, region)}
        onValidate={(provider) => onValidate(provider, region)}
        onDisconnect={(provider) => onDisconnect(provider, region)}
      />
      <div className="mt-5 space-y-4 border-t border-slate-200/80 pt-5">
        {profiles.length > 0 ? (
          profiles.map((profile) => (
            <MarketplaceCard
              key={profile.id}
              profile={profile}
              region={region}
              spApiConnectionState={spApiConnection.state}
              backfillCoverage={coverageByProfileId[profile.id] ?? EMPTY_PROFILE_COVERAGE}
              businessState={businessBackfillStates[profile.id]}
              listingsState={listingsBackfillStates[profile.id]}
              onRunBusinessBackfill={onRunBusinessBackfill}
              onRunListingsBackfill={onRunListingsBackfill}
              onRetryBusinessBackfill={onRetryBusinessBackfill}
              onRetryListingsBackfill={onRetryListingsBackfill}
            />
          ))
        ) : (
          <p className="rounded-2xl border border-slate-200 bg-white/70 px-4 py-3 text-sm text-slate-500">
            No marketplaces in {region} yet. Add a WBR profile to start pulling data.
          </p>
        )}
      </div>
    </section>
  );
}
