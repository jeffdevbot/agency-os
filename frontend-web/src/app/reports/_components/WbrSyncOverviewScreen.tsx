"use client";

import Link from "next/link";
import { useResolvedWbrProfile } from "../_lib/useResolvedWbrProfile";

type Props = {
  clientSlug: string;
  marketplaceCode: string;
};

export default function WbrSyncOverviewScreen({ clientSlug, marketplaceCode }: Props) {
  const resolved = useResolvedWbrProfile(clientSlug, marketplaceCode);
  const normalizedMarketplace = marketplaceCode.toLowerCase();

  if (resolved.loading) {
    return (
      <main className="space-y-4">
        <div className="rounded-3xl bg-white/95 p-8 text-sm text-[#64748b] shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          Loading WBR sync...
        </div>
      </main>
    );
  }

  if (!resolved.profile || !resolved.summary) {
    return (
      <main className="space-y-4">
        <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          <h1 className="text-2xl font-semibold text-[#0f172a]">WBR Sync</h1>
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {resolved.errorMessage ?? "Unable to resolve WBR profile"}
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="space-y-4">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-2xl font-semibold text-[#0f172a]">WBR Sync</h1>
        <p className="mt-2 text-sm text-[#4c576f]">
          Choose the source workflow for {resolved.summary.client.name} {resolved.profile.marketplace_code}.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/reports/api-access"
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            Client Data Access
          </Link>
          <Link
            href={`/reports/${clientSlug}/${normalizedMarketplace}/wbr`}
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            Back to WBR
          </Link>
          <Link
            href={`/reports/${clientSlug}/${normalizedMarketplace}/wbr/settings`}
            className="rounded-2xl bg-[#e8eefc] px-4 py-3 text-sm font-semibold text-[#0f172a] transition hover:bg-[#d7e1fb]"
          >
            Settings
          </Link>
        </div>

        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          <Link
            href={`/reports/${clientSlug}/${normalizedMarketplace}/wbr/sync/sp-api`}
            className="rounded-2xl border border-slate-200 bg-white p-6 shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            <p className="text-lg font-semibold text-[#0f172a]">SP-API</p>
            <p className="mt-2 text-sm text-[#4c576f]">Business data via Windsor.ai.</p>
            <p className="mt-4 text-sm text-[#4c576f]">
              Windsor account: <span className="font-semibold text-[#0f172a]">{resolved.profile.windsor_account_id ?? "Not set"}</span>
            </p>
            <p className="mt-4 text-sm font-semibold text-[#0a6fd6]">Open SP-API Sync</p>
          </Link>

          <Link
            href={`/reports/${clientSlug}/${normalizedMarketplace}/wbr/sync/ads-api`}
            className="rounded-2xl border border-slate-200 bg-white p-6 shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            <p className="text-lg font-semibold text-[#0f172a]">Ads API</p>
            <p className="mt-2 text-sm text-[#4c576f]">Campaign performance sync for Section 2.</p>
            <p className="mt-4 text-sm text-[#4c576f]">
              Ads profile: <span className="font-semibold text-[#0f172a]">{resolved.profile.amazon_ads_profile_id ?? "Not set"}</span>
            </p>
            <p className="mt-4 text-sm font-semibold text-[#0a6fd6]">Open Ads API Sync</p>
          </Link>
        </div>
      </div>
    </main>
  );
}
