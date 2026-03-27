"use client";

import { useCallback, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import { updateWbrProfile, type WbrProfile } from "../wbr/_lib/wbrApi";
import { useSearchTermSync } from "../_lib/useSearchTermSync";
import type { ClientMarketplaceReportSurface } from "../_lib/reportSurfaceSummary";

const statusClasses: Record<string, string> = {
  running: "border-sky-200 bg-sky-50 text-sky-800",
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  error: "border-rose-200 bg-rose-50 text-rose-800",
};

const formatTimestamp = (value: string | null): string => {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "numeric",
    minute: "2-digit",
  }).format(parsed);
};

type CardProps = {
  profile: WbrProfile;
  onProfileUpdated: () => void;
};

function SearchTermSyncCard({ profile, onProfileUpdated }: CardProps) {
  const sync = useSearchTermSync(profile);
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [toggleSaving, setToggleSaving] = useState(false);
  const [toggleMessage, setToggleMessage] = useState<string | null>(null);
  const [toggleError, setToggleError] = useState<string | null>(null);

  const handleToggleNightlySync = useCallback(async () => {
    setToggleSaving(true);
    setToggleError(null);
    setToggleMessage(null);
    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.access_token) throw new Error("Please sign in again.");
      const nextEnabled = !profile.search_term_auto_sync_enabled;
      await updateWbrProfile(session.access_token, profile.id, {
        search_term_auto_sync_enabled: nextEnabled,
      });
      onProfileUpdated();
      setToggleMessage(
        nextEnabled ? "Nightly STR sync enabled." : "Nightly STR sync disabled.",
      );
    } catch (error) {
      setToggleError(
        error instanceof Error ? error.message : "Failed to update nightly STR sync",
      );
    } finally {
      setToggleSaving(false);
    }
  }, [profile, supabase, onProfileUpdated]);

  const hasAdsProfile = !!profile.amazon_ads_profile_id;
  const isBusy = sync.runningBackfill || sync.runningDailyRefresh || toggleSaving;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      {/* Card header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[#0f172a]">
            {profile.marketplace_code} Marketplace
          </p>
          <p className="mt-1 text-xs text-[#64748b]">
            {profile.display_name}
            {profile.amazon_ads_profile_id
              ? ` · Ads profile: ${profile.amazon_ads_profile_id}`
              : " · No Ads profile configured"}
          </p>
        </div>
        <span
          className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${
            profile.search_term_auto_sync_enabled
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-slate-200 bg-slate-50 text-slate-700"
          }`}
        >
          Nightly: {profile.search_term_auto_sync_enabled ? "On" : "Off"}
        </span>
      </div>

      {/* Warnings */}
      {!hasAdsProfile ? (
        <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Set up an Amazon Ads profile in WBR Sync / Ads API before running STR sync.
        </p>
      ) : null}

      {toggleError ? (
        <p className="mt-3 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
          {toggleError}
        </p>
      ) : null}

      {toggleMessage ? (
        <p className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {toggleMessage}
        </p>
      ) : null}

      {sync.errorMessage ? (
        <p className="mt-3 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
          {sync.errorMessage}
        </p>
      ) : null}

      {sync.successMessage ? (
        <p className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {sync.successMessage}
        </p>
      ) : null}

      {/* Latest run */}
      <div className="mt-4 rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">
          Latest STR Sync Run
        </p>
        {sync.loadingRuns ? (
          <p className="mt-2 text-sm text-[#64748b]">Loading...</p>
        ) : !sync.latestRun ? (
          <p className="mt-2 text-sm text-[#64748b]">No STR sync runs yet for this profile.</p>
        ) : (
          <div className="mt-2 flex flex-wrap items-center gap-3 text-sm">
            <span
              className={`inline-flex rounded-full border px-2 py-1 text-xs font-semibold ${statusClasses[sync.latestRun.status] ?? ""}`}
            >
              {sync.latestRun.status}
            </span>
            <span className="text-[#4c576f]">{formatTimestamp(sync.latestRun.started_at)}</span>
            {sync.latestRun.date_from && sync.latestRun.date_to ? (
              <span className="text-[#4c576f]">
                {sync.latestRun.date_from} to {sync.latestRun.date_to}
              </span>
            ) : null}
            <span className="text-[#64748b]">
              {sync.latestRun.rows_loaded.toLocaleString()} rows loaded
            </span>
            {sync.latestRun.error_message ? (
              <span className="text-rose-700">{sync.latestRun.error_message}</span>
            ) : null}
          </div>
        )}
      </div>

      {/* Backfill controls */}
      <div className="mt-4 rounded-2xl border border-slate-200 p-4">
        <p className="text-sm font-semibold text-[#0f172a]">Backfill</p>
        <p className="mt-1 text-sm text-[#4c576f]">
          Import STR data for a date range. Amazon Ads retains approximately{" "}
          {sync.observedRetentionDays} days.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-sm">
            <span className="mb-1 block font-semibold text-[#0f172a]">From</span>
            <input
              type="date"
              value={sync.backfillDateFrom}
              max={sync.todayIso}
              onChange={(e) => sync.setBackfillDateFrom(e.target.value)}
              className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block font-semibold text-[#0f172a]">To</span>
            <input
              type="date"
              value={sync.backfillDateTo}
              max={sync.todayIso}
              onChange={(e) => sync.setBackfillDateTo(e.target.value)}
              className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
            />
          </label>
        </div>
        <button
          onClick={() => void sync.handleRunBackfill()}
          disabled={!hasAdsProfile || isBusy}
          className="mt-3 rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-[#b7cbea]"
        >
          {sync.runningBackfill ? "Running Backfill..." : "Run Backfill"}
        </button>
      </div>

      {/* Daily refresh + nightly sync toggle */}
      <div className="mt-4 flex flex-wrap gap-3">
        <button
          onClick={() => void sync.handleRunDailyRefresh()}
          disabled={!hasAdsProfile || isBusy}
          className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
        >
          {sync.runningDailyRefresh ? "Running Refresh..." : "Run Daily Refresh Now"}
        </button>
        <button
          onClick={() => void handleToggleNightlySync()}
          disabled={(!hasAdsProfile && !profile.search_term_auto_sync_enabled) || isBusy}
          className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
        >
          {toggleSaving
            ? "Saving..."
            : profile.search_term_auto_sync_enabled
              ? "Disable Nightly Sync"
              : "Enable Nightly Sync"}
        </button>
      </div>
    </div>
  );
}

type Props = {
  marketplaces: ClientMarketplaceReportSurface[];
  loading: boolean;
  onProfileUpdated: () => void;
};

export default function SearchTermSyncSection({ marketplaces, loading, onProfileUpdated }: Props) {
  const profiledMarketplaces = marketplaces.filter((m) => m.wbr_profile !== null);

  return (
    <section className="mt-8 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[#0a6fd6]">
            Search Term Automation
          </p>
          <p className="mt-2 max-w-2xl text-sm text-[#4c576f]">
            Setup and sync control surface for STR ingestion from Amazon Ads. This controls
            what data is collected — the Search Term Data inspection surface and action tools
            come in later stages. STR sync is separate from the existing Ads campaign sync.
          </p>
        </div>
        <span
          className="inline-flex cursor-not-allowed select-none rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-400"
          title="Search Term Data surface is coming in Stage 2"
        >
          Open Search Term Data
        </span>
      </div>

      {/* Guidance block */}
      <div className="rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-5">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#0a6fd6]">
          How This Works
        </p>
        <div className="mt-3 space-y-2 text-sm text-[#4c576f]">
          <p>
            <span className="font-semibold text-[#0f172a]">Backfill:</span> Imports STR data
            across a custom date range using the Amazon Ads API. Retention is approximately 60
            days — deeper history still requires a Pacvue export.
          </p>
          <p>
            <span className="font-semibold text-[#0f172a]">Daily Refresh:</span> Imports the
            trailing window for recent days. Use this to top-up after a gap without running a
            full backfill.
          </p>
          <p>
            <span className="font-semibold text-[#0f172a]">Nightly Sync:</span> Enables
            worker-sync to run a daily refresh automatically each night. This is independent of
            the WBR Ads campaign sync — both can be enabled without interfering.
          </p>
        </div>
      </div>

      {/* Per-marketplace cards */}
      {loading ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-[#64748b]">
          Loading marketplace setup...
        </div>
      ) : profiledMarketplaces.length === 0 ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-[#64748b]">
          No WBR profiles found. Configure a WBR profile before enabling search term sync.
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {profiledMarketplaces.map((marketplace) => (
            <SearchTermSyncCard
              key={marketplace.marketplace_code}
              profile={marketplace.wbr_profile!}
              onProfileUpdated={onProfileUpdated}
            />
          ))}
        </div>
      )}
    </section>
  );
}
