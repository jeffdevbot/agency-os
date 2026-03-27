"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import { updateWbrProfile, type WbrProfile } from "../wbr/_lib/wbrApi";
import type { WbrSyncRun } from "../wbr/_lib/wbrAmazonAdsApi";
import { useSearchTermSync } from "../_lib/useSearchTermSync";
import type { ClientMarketplaceReportSurface } from "../_lib/reportSurfaceSummary";
import {
  FUTURE_SEARCH_TERM_AD_PRODUCTS,
  LIVE_SEARCH_TERM_AD_PRODUCT,
} from "../_lib/searchTermProducts";

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

const runPhaseLabel = (run: WbrSyncRun): string => {
  const phase = run.request_meta?.report_progress?.phase;
  if (run.status === "success") return "completed";
  if (run.status === "error") return phase === "failed" ? "worker error" : "failed";
  if (phase === "queued") return "queued";
  if (phase === "polling") return "polling Amazon";
  if (phase === "ready_to_finalize") return "downloading reports";
  if (phase === "completed") return "completed";
  if (phase === "failed") return "failed";
  return "running";
};

const runProgressSummary = (run: WbrSyncRun): string => {
  const progress = run.request_meta?.report_progress;
  if (progress?.summary) return progress.summary;
  if (run.status === "running") return "Background worker is processing this STR sync run.";
  if (run.status === "success") return "Sponsored Products search-term sync finished successfully.";
  return "Sponsored Products search-term sync failed.";
};

const runNextPollText = (run: WbrSyncRun): string | null => {
  const nextPollAt = run.request_meta?.report_progress?.next_poll_at;
  if (!nextPollAt || run.status !== "running") return null;
  return `Next poll ${formatTimestamp(nextPollAt)}`;
};

type CardProps = {
  profile: WbrProfile;
  onProfileUpdated: () => void;
};

function FutureAdProductCard({
  label,
  summary,
  availabilityNote,
}: {
  label: string;
  summary: string;
  availabilityNote: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[#0f172a]">{label}</p>
          <p className="mt-1 text-sm text-[#4c576f]">{summary}</p>
        </div>
        <span className="inline-flex rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600">
          Not Yet Verified
        </span>
      </div>
      <p className="mt-3 text-sm text-[#64748b]">{availabilityNote}</p>
      <p className="mt-2 text-xs text-[#64748b]">
        Separate latest-run, backfill, daily refresh, and nightly-sync controls will appear here
        after the native report contract is validated.
      </p>
    </div>
  );
}

function SearchTermSyncCard({ profile, onProfileUpdated }: CardProps) {
  const sync = useSearchTermSync(profile, LIVE_SEARCH_TERM_AD_PRODUCT.amazonAdsAdProduct);
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
          {LIVE_SEARCH_TERM_AD_PRODUCT.shortLabel} Nightly:{" "}
          {profile.search_term_auto_sync_enabled ? "On" : "Off"}
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
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-[#0f172a]">{LIVE_SEARCH_TERM_AD_PRODUCT.label}</p>
            <p className="mt-1 text-sm text-[#4c576f]">
              Validated Amazon-native search-term ingestion path for the current rollout.
            </p>
          </div>
          <span className="inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800">
            Live
          </span>
        </div>

        <div className="mt-4 rounded-2xl border border-[#dbe4f0] bg-white/70 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">
            Latest {LIVE_SEARCH_TERM_AD_PRODUCT.label} Sync Run
          </p>
          {sync.loadingRuns ? (
            <p className="mt-2 text-sm text-[#64748b]">Loading...</p>
          ) : !sync.latestRun ? (
            <p className="mt-2 text-sm text-[#64748b]">
              No {LIVE_SEARCH_TERM_AD_PRODUCT.shortLabel} sync runs yet for this profile.
            </p>
          ) : (
            <div className="mt-2 space-y-2 text-sm">
              <div className="flex flex-wrap items-center gap-3">
                <span
                  className={`inline-flex rounded-full border px-2 py-1 text-xs font-semibold ${statusClasses[sync.latestRun.status] ?? ""}`}
                >
                  {runPhaseLabel(sync.latestRun)}
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
              </div>
              <p className="text-[#4c576f]">{runProgressSummary(sync.latestRun)}</p>
              {runNextPollText(sync.latestRun) ? (
                <p className="text-xs text-[#64748b]">{runNextPollText(sync.latestRun)}</p>
              ) : null}
              {sync.latestRun.error_message ? (
                <p className="text-sm text-rose-700">{sync.latestRun.error_message}</p>
              ) : null}
            </div>
          )}
        </div>
      </div>

      {sync.hasRunningRuns ? (
        <p className="mt-3 text-xs font-medium text-[#4c576f]">
          Auto-refreshing every 15 seconds while {LIVE_SEARCH_TERM_AD_PRODUCT.shortLabel} STR jobs
          are still running.
        </p>
      ) : null}

      {/* Backfill controls */}
      <div className="mt-4 rounded-2xl border border-slate-200 p-4">
        <p className="text-sm font-semibold text-[#0f172a]">
          {LIVE_SEARCH_TERM_AD_PRODUCT.label} Backfill
        </p>
        <p className="mt-1 text-sm text-[#4c576f]">
          Import {LIVE_SEARCH_TERM_AD_PRODUCT.label} STR data for a date range. Amazon Ads retains
          approximately {sync.observedRetentionDays} days.
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
          {sync.runningBackfill
            ? `Running ${LIVE_SEARCH_TERM_AD_PRODUCT.shortLabel} Backfill...`
            : `Run ${LIVE_SEARCH_TERM_AD_PRODUCT.shortLabel} Backfill`}
        </button>
      </div>

      {/* Daily refresh + nightly sync toggle */}
      <div className="mt-4 flex flex-wrap gap-3">
        <button
          onClick={() => void sync.handleRunDailyRefresh()}
          disabled={!hasAdsProfile || isBusy}
          className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
        >
          {sync.runningDailyRefresh
            ? `Running ${LIVE_SEARCH_TERM_AD_PRODUCT.shortLabel} Refresh...`
            : `Run ${LIVE_SEARCH_TERM_AD_PRODUCT.shortLabel} Daily Refresh`}
        </button>
        <button
          onClick={() => void handleToggleNightlySync()}
          disabled={(!hasAdsProfile && !profile.search_term_auto_sync_enabled) || isBusy}
          className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
        >
          {toggleSaving
            ? "Saving..."
            : profile.search_term_auto_sync_enabled
              ? `Disable ${LIVE_SEARCH_TERM_AD_PRODUCT.shortLabel} Nightly Sync`
              : `Enable ${LIVE_SEARCH_TERM_AD_PRODUCT.shortLabel} Nightly Sync`}
        </button>
      </div>

      <div className="mt-5 grid gap-3 lg:grid-cols-2">
        {FUTURE_SEARCH_TERM_AD_PRODUCTS.map((product) => (
          <FutureAdProductCard
            key={product.key}
            label={product.label}
            summary={product.summary}
            availabilityNote={product.availabilityNote}
          />
        ))}
      </div>
    </div>
  );
}

type Props = {
  clientSlug: string;
  marketplaces: ClientMarketplaceReportSurface[];
  loading: boolean;
  onProfileUpdated: () => void;
};

export default function SearchTermSyncSection({ clientSlug, marketplaces, loading, onProfileUpdated }: Props) {
  const profiledMarketplaces = marketplaces.filter((m) => m.wbr_profile !== null);

  return (
    <section className="mt-8 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[#0a6fd6]">
            Search Term Automation
          </p>
          <p className="mt-2 max-w-2xl text-sm text-[#4c576f]">
            Setup and sync control surface for Amazon Ads search-term ingestion by ad product.
            Sponsored Products is the current validated live path. Sponsored Brands and
            Sponsored Display remain separate future lanes until their native contracts are
            verified. STR sync is separate from the existing Ads campaign sync.
          </p>
        </div>
        <Link
          href={`/reports/search-term-data/${clientSlug}`}
          className="rounded-2xl border border-[#c7d8f5] bg-white px-4 py-2 text-sm font-semibold text-[#0a6fd6] transition hover:bg-[#f7faff]"
        >
          Open Search Term Data
        </Link>
      </div>

      {/* Guidance block */}
      <div className="rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-5">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#0a6fd6]">
          How This Works
        </p>
        <div className="mt-3 space-y-2 text-sm text-[#4c576f]">
          <p>
            <span className="font-semibold text-[#0f172a]">Sponsored Products:</span> The
            current live controls below are for the validated SP search-term path only.
          </p>
          <p>
            <span className="font-semibold text-[#0f172a]">Backfill:</span> Imports SP
            search-term data across a custom date range using the Amazon Ads API. Observed
            retention is approximately 60 days — deeper history still requires a Pacvue export.
          </p>
          <p>
            <span className="font-semibold text-[#0f172a]">Daily Refresh / Nightly Sync:</span>{" "}
            The current refresh controls are SP-only. Future SB and SD controls will appear as
            separate operational sections once their native report contracts are validated.
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
