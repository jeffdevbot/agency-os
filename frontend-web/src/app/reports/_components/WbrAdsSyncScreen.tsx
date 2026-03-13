"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import { useResolvedWbrProfile } from "../_lib/useResolvedWbrProfile";
import { useWbrAdsSync } from "../_lib/useWbrAdsSync";
import { useWbrSection2Report } from "../_lib/useWbrSection2Report";
import {
  getAmazonAdsConnectUrl,
  getAmazonAdsConnectionStatus,
  listAmazonAdsProfiles,
  selectAmazonAdsProfile,
  type AmazonAdsAdvertiserProfile,
} from "../wbr/_lib/wbrAmazonAdsApi";

type Props = {
  clientSlug: string;
  marketplaceCode: string;
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

const statusClasses = {
  running: "border-sky-200 bg-sky-50 text-sky-800",
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  error: "border-rose-200 bg-rose-50 text-rose-800",
};

export default function WbrAdsSyncScreen({ clientSlug, marketplaceCode }: Props) {
  const resolved = useResolvedWbrProfile(clientSlug, marketplaceCode);
  const sync = useWbrAdsSync(resolved.profile);
  const section2ReportState = useWbrSection2Report(resolved.profile?.id ?? null, 4);
  const normalizedMarketplace = marketplaceCode.toLowerCase();

  // Amazon Ads connection state
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [adsConnected, setAdsConnected] = useState(false);
  const [adsConnectedAt, setAdsConnectedAt] = useState<string | null>(null);
  const [adsCheckingConnection, setAdsCheckingConnection] = useState(true);
  const [adsConnecting, setAdsConnecting] = useState(false);
  const [adsError, setAdsError] = useState<string | null>(null);
  const [adsProfiles, setAdsProfiles] = useState<AmazonAdsAdvertiserProfile[]>([]);
  const [adsLoadingProfiles, setAdsLoadingProfiles] = useState(false);
  const [adsSelectingProfile, setAdsSelectingProfile] = useState(false);

  const getToken = useCallback(async (): Promise<string> => {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session?.access_token) throw new Error("Please sign in again.");
    return session.access_token;
  }, [supabase]);

  // Check connection status on mount
  useEffect(() => {
    if (!resolved.profile?.id) {
      setAdsCheckingConnection(false);
      return;
    }
    let cancelled = false;
    const check = async () => {
      try {
        const token = await getToken();
        const status = await getAmazonAdsConnectionStatus(token, resolved.profile!.id);
        if (!cancelled) {
          setAdsConnected(status.connected);
          setAdsConnectedAt(status.connection?.connected_at ?? null);
        }
      } catch {
        // Silently fail on initial check
      } finally {
        if (!cancelled) setAdsCheckingConnection(false);
      }
    };
    void check();
    return () => { cancelled = true; };
  }, [getToken, resolved.profile?.id]);

  const handleConnectAmazonAds = useCallback(async () => {
    if (!resolved.profile?.id) return;
    setAdsConnecting(true);
    setAdsError(null);
    try {
      const token = await getToken();
      const returnPath = `/reports/${clientSlug}/${normalizedMarketplace}/wbr/sync/ads-api`;
      const url = await getAmazonAdsConnectUrl(token, resolved.profile.id, returnPath);
      window.location.href = url;
    } catch (error) {
      setAdsError(error instanceof Error ? error.message : "Failed to start Amazon Ads connection");
      setAdsConnecting(false);
    }
  }, [clientSlug, getToken, normalizedMarketplace, resolved.profile?.id]);

  const handleDiscoverProfiles = useCallback(async () => {
    if (!resolved.profile?.id) return;
    setAdsLoadingProfiles(true);
    setAdsError(null);
    try {
      const token = await getToken();
      const profiles = await listAmazonAdsProfiles(token, resolved.profile.id);
      setAdsProfiles(profiles);
    } catch (error) {
      setAdsError(error instanceof Error ? error.message : "Failed to load Amazon Ads profiles");
    } finally {
      setAdsLoadingProfiles(false);
    }
  }, [getToken, resolved.profile?.id]);

  const handleSelectProfile = useCallback(async (ap: AmazonAdsAdvertiserProfile) => {
    if (!resolved.profile?.id) return;
    setAdsSelectingProfile(true);
    setAdsError(null);
    try {
      const token = await getToken();
      await selectAmazonAdsProfile(
        token,
        resolved.profile.id,
        String(ap.profileId),
        ap.accountInfo?.id,
      );
      setAdsProfiles([]);
      window.location.reload();
    } catch (error) {
      setAdsError(error instanceof Error ? error.message : "Failed to save Amazon Ads profile");
      setAdsSelectingProfile(false);
    }
  }, [getToken, resolved.profile?.id]);

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
          Connect to Amazon Ads and sync campaign performance data for WBR Section 2.
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
      </div>

      {/* Amazon Ads Connection */}
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <p className="text-sm font-semibold text-[#0f172a]">Amazon Ads Connection</p>
        <p className="mt-1 text-sm text-[#4c576f]">
          Connect this WBR profile to Amazon Ads to pull campaign performance data.
        </p>

        {adsError ? (
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {adsError}
          </p>
        ) : null}

        {sync.errorMessage ? (
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {sync.errorMessage}
          </p>
        ) : null}

        {sync.successMessage ? (
          <p className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            {sync.successMessage}
          </p>
        ) : null}

        {adsCheckingConnection ? (
          <p className="mt-4 text-sm text-[#64748b]">Checking connection status...</p>
        ) : adsConnected ? (
          <div className="mt-4 space-y-4">
            <div className="flex items-center gap-3">
              <span className="inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800">
                Connected
              </span>
              {adsConnectedAt ? (
                <span className="text-xs text-[#64748b]">since {formatTimestamp(adsConnectedAt)}</span>
              ) : null}
            </div>

            {resolved.profile.amazon_ads_profile_id ? (
              <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-2xl border border-slate-200 bg-white p-5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Ads Profile ID</p>
                  <p className="mt-2 text-sm font-semibold text-[#0f172a]">{resolved.profile.amazon_ads_profile_id}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-white p-5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Ads Account ID</p>
                  <p className="mt-2 text-sm font-semibold text-[#0f172a]">{resolved.profile.amazon_ads_account_id ?? "—"}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-white p-5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Pacvue Mapping</p>
                  <p className="mt-2 text-sm font-semibold text-[#0f172a]">Campaign name exact-match</p>
                </div>
              </div>
            ) : (
              <div>
                <button
                  onClick={() => void handleDiscoverProfiles()}
                  disabled={adsLoadingProfiles}
                  className="rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-[#b7cbea]"
                >
                  {adsLoadingProfiles ? "Loading Profiles..." : "Discover Advertiser Profiles"}
                </button>
              </div>
            )}

            {adsProfiles.length > 0 ? (
              <div className="mt-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[#4c576f]">
                  Select an advertiser profile
                </p>
                <div className="space-y-2">
                  {adsProfiles.map((ap) => (
                    <div
                      key={ap.profileId}
                      className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white p-4"
                    >
                      <div>
                        <p className="text-sm font-semibold text-[#0f172a]">
                          {ap.accountInfo?.name ?? "Unknown"}{" "}
                          <span className="font-normal text-[#4c576f]">({ap.countryCode})</span>
                        </p>
                        <p className="text-xs text-[#64748b]">
                          Profile {ap.profileId} &middot; {ap.accountInfo?.type ?? "—"} &middot; {ap.currencyCode}
                        </p>
                      </div>
                      <button
                        onClick={() => void handleSelectProfile(ap)}
                        disabled={adsSelectingProfile}
                        className="rounded-xl bg-[#0a6fd6] px-3 py-2 text-xs font-semibold text-white transition hover:bg-[#0959ab] disabled:bg-[#b7cbea]"
                      >
                        {adsSelectingProfile ? "Saving..." : "Select"}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {resolved.profile.amazon_ads_profile_id ? (
              <button
                onClick={() => void handleDiscoverProfiles()}
                disabled={adsLoadingProfiles}
                className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
              >
                {adsLoadingProfiles ? "Loading..." : "Change Advertiser Profile"}
              </button>
            ) : null}
          </div>
        ) : (
          <button
            onClick={() => void handleConnectAmazonAds()}
            disabled={adsConnecting}
            className="mt-4 rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-[#b7cbea]"
          >
            {adsConnecting ? "Redirecting to Amazon..." : "Connect Amazon Ads"}
          </button>
        )}
      </div>

      {resolved.profile.amazon_ads_profile_id ? (
        <>
        <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-[#0f172a]">Pacvue Mapping Status</p>
              <p className="mt-1 text-sm text-[#4c576f]">
                This is admin-facing QA for row-level ads reporting over the current 4-week WBR window.
              </p>
            </div>
            <button
              onClick={() => void section2ReportState.loadReport(true)}
              disabled={section2ReportState.loading || section2ReportState.refreshing}
              className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
            >
              {section2ReportState.refreshing ? "Refreshing..." : "Refresh Mapping"}
            </button>
          </div>

          {section2ReportState.errorMessage ? (
            <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
              {section2ReportState.errorMessage}
            </p>
          ) : null}

          {section2ReportState.loading && !section2ReportState.report ? (
            <p className="mt-4 text-sm text-[#64748b]">Loading mapping status...</p>
          ) : null}

          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Mapped Campaigns</p>
              <p className="mt-2 text-2xl font-semibold text-[#0f172a]">
                {section2ReportState.report?.qa.mapped_campaign_count ?? 0}
              </p>
            </div>
            <div className="rounded-2xl border border-amber-200 bg-amber-50/70 p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-[#92400e]">Unmapped Campaigns</p>
              <p className="mt-2 text-2xl font-semibold text-[#92400e]">
                {section2ReportState.report?.qa.unmapped_campaign_count ?? 0}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Unmapped Fact Rows</p>
              <p className="mt-2 text-2xl font-semibold text-[#0f172a]">
                {section2ReportState.report?.qa.unmapped_fact_rows ?? 0}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Fact Rows In Window</p>
              <p className="mt-2 text-2xl font-semibold text-[#0f172a]">
                {section2ReportState.report?.qa.fact_row_count ?? 0}
              </p>
            </div>
          </div>

          {!section2ReportState.loading && (section2ReportState.report?.qa.unmapped_campaign_samples?.length ?? 0) > 0 ? (
            <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50/70 p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-[#92400e]">
                Sample Unmapped Campaigns
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {section2ReportState.report?.qa.unmapped_campaign_samples.map((campaignName) => (
                  <span
                    key={campaignName}
                    className="inline-flex rounded-full border border-amber-200 bg-white px-3 py-1 text-xs font-medium text-[#78350f]"
                  >
                    {campaignName}
                  </span>
                ))}
              </div>
            </div>
          ) : !section2ReportState.loading ? (
            <p className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
              All ads campaign facts in the current 4-week window are matching Pacvue campaign mappings.
            </p>
          ) : null}
        </div>

        <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          <p className="rounded-xl border border-slate-200 bg-[#f7faff] px-4 py-3 text-sm text-[#334155]">
            Row-level ads reporting requires Pacvue campaign mapping. Until that is configured, this sync still lets us validate marketplace-level totals.
          </p>

          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <p className="text-sm font-semibold text-[#0f172a]">Historical Backfill</p>
              <p className="mt-1 text-sm text-[#4c576f]">
                Backfill daily Sponsored Products campaign facts in date chunks so we can validate weekly ad totals.
              </p>
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <label className="text-sm">
                  <span className="mb-1 block font-semibold text-[#0f172a]">Start Date</span>
                  <input
                    type="date"
                    value={sync.backfillStartDate}
                    onChange={(event) => sync.setBackfillStartDate(event.target.value)}
                    className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
                  />
                </label>
                <label className="text-sm">
                  <span className="mb-1 block font-semibold text-[#0f172a]">End Date</span>
                  <input
                    type="date"
                    value={sync.backfillEndDate}
                    onChange={(event) => sync.setBackfillEndDate(event.target.value)}
                    className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
                  />
                </label>
                <label className="text-sm">
                  <span className="mb-1 block font-semibold text-[#0f172a]">Chunk Days</span>
                  <input
                    type="number"
                    min={1}
                    max={31}
                    value={sync.chunkDays}
                    onChange={(event) => sync.setChunkDays(event.target.value)}
                    className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
                  />
                </label>
              </div>
              <button
                onClick={() => void sync.handleRunBackfill()}
                disabled={sync.runningBackfill || sync.runningDailyRefresh}
                className="mt-4 rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-[#b7cbea]"
              >
                {sync.runningBackfill ? "Running Backfill..." : "Run Backfill"}
              </button>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <p className="text-sm font-semibold text-[#0f172a]">Daily Refresh</p>
              <p className="mt-1 text-sm text-[#4c576f]">
                Rewrite the profile&apos;s trailing {resolved.profile.daily_rewrite_days}-day Amazon Ads window to catch late attribution and report changes.
              </p>
              <button
                onClick={() => void sync.handleRunDailyRefresh()}
                disabled={sync.runningBackfill || sync.runningDailyRefresh}
                className="mt-4 rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-[#b7cbea]"
              >
                {sync.runningDailyRefresh ? "Running Daily Refresh..." : "Run Daily Refresh"}
              </button>
            </div>
          </div>
        </div>

        <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-[#0f172a]">Recent Runs</p>
            <button
              onClick={() => void sync.loadRuns(true)}
              disabled={sync.loadingRuns || sync.refreshingRuns || sync.runningBackfill || sync.runningDailyRefresh}
              className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
            >
              {sync.refreshingRuns ? "Refreshing..." : "Refresh Runs"}
            </button>
          </div>

          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-[#f7faff]">
                <tr className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">
                  <th className="px-3 py-2">Started</th>
                  <th className="px-3 py-2">Job</th>
                  <th className="px-3 py-2">Window</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Rows Fetched</th>
                  <th className="px-3 py-2">Rows Loaded</th>
                  <th className="px-3 py-2">Error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 bg-white">
                {sync.loadingRuns ? (
                  <tr>
                    <td colSpan={7} className="px-3 py-4 text-[#64748b]">
                      Loading sync runs...
                    </td>
                  </tr>
                ) : sync.runs.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-3 py-4 text-[#64748b]">
                      No Ads API sync runs yet.
                    </td>
                  </tr>
                ) : (
                  sync.runs.map((run) => (
                    <tr key={run.id} className="hover:bg-slate-50">
                      <td className="px-3 py-2 text-[#0f172a]">{formatTimestamp(run.started_at)}</td>
                      <td className="px-3 py-2 text-[#0f172a]">{run.job_type}</td>
                      <td className="px-3 py-2 text-[#4c576f]">
                        {run.date_from ?? "—"} to {run.date_to ?? "—"}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={`inline-flex rounded-full border px-2 py-1 text-xs font-semibold ${statusClasses[run.status]}`}
                        >
                          {run.status}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-[#0f172a]">{run.rows_fetched}</td>
                      <td className="px-3 py-2 text-[#0f172a]">{run.rows_loaded}</td>
                      <td className="px-3 py-2 text-[#64748b]">{run.error_message ?? "—"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
        </>
      ) : null}
    </main>
  );
}
