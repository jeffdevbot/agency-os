"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import { useResolvedWbrProfile } from "../_lib/useResolvedWbrProfile";
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

export default function WbrAdsSyncScreen({ clientSlug, marketplaceCode }: Props) {
  const resolved = useResolvedWbrProfile(clientSlug, marketplaceCode);
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

      {/* Ads sync controls (not wired yet) */}
      {resolved.profile.amazon_ads_profile_id ? (
        <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
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
      ) : null}
    </main>
  );
}
