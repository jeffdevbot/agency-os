"use client";

import Link from "next/link";
import { useResolvedWbrProfile } from "../_lib/useResolvedWbrProfile";

type Props = {
  clientSlug: string;
  marketplaceCode: string;
};

export default function WbrAdsSyncScreen({ clientSlug, marketplaceCode }: Props) {
  const resolved = useResolvedWbrProfile(clientSlug, marketplaceCode);
  const normalizedMarketplace = marketplaceCode.toLowerCase();

  if (resolved.loading) {
    return (
      <main className="space-y-4">
        <div className="rounded-3xl bg-white/95 p-8 text-sm text-[#64748b] shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          Loading Ads API sync...
        </div>
      </main>
    );
  }

  if (!resolved.profile || !resolved.summary) {
    return (
      <main className="space-y-4">
        <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          <h1 className="text-2xl font-semibold text-[#0f172a]">Ads API Sync</h1>
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
        <h1 className="text-2xl font-semibold text-[#0f172a]">
          {resolved.summary.client.name} {resolved.profile.marketplace_code} Ads API Sync
        </h1>
        <p className="mt-2 text-sm text-[#4c576f]">
          Section 2 sync surface for Amazon Ads campaign performance. This route is scaffolded now so the product flow is ready before the backend ingest lands.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href={`/reports/${clientSlug}/${normalizedMarketplace}/wbr/sync`}
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            Sync Sources
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

        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Ads Profile ID</p>
            <p className="mt-2 text-sm font-semibold text-[#0f172a]">
              {resolved.profile.amazon_ads_profile_id ?? "—"}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Ads Account ID</p>
            <p className="mt-2 text-sm font-semibold text-[#0f172a]">
              {resolved.profile.amazon_ads_account_id ?? "—"}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Pacvue Mapping</p>
            <p className="mt-2 text-sm font-semibold text-[#0f172a]">Campaign name exact-match</p>
          </div>
        </div>

        <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Ads API backfill and daily refresh are not wired yet. This page is the planned destination for that workflow.
        </p>

        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 opacity-70">
            <p className="text-sm font-semibold text-[#0f172a]">Historical Backfill</p>
            <p className="mt-1 text-sm text-[#4c576f]">
              Backfill daily campaign facts in date chunks, then map them into WBR rows through Pacvue.
            </p>
            <button
              disabled
              className="mt-4 rounded-2xl bg-[#b7cbea] px-4 py-3 text-sm font-semibold text-white"
            >
              Run Backfill
            </button>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 opacity-70">
            <p className="text-sm font-semibold text-[#0f172a]">Daily Refresh</p>
            <p className="mt-1 text-sm text-[#4c576f]">
              Rewrite the trailing daily window to catch late attribution and report updates from Amazon Ads.
            </p>
            <button
              disabled
              className="mt-4 rounded-2xl bg-[#b7cbea] px-4 py-3 text-sm font-semibold text-white"
            >
              Run Daily Refresh
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
