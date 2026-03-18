"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import {
  createAmazonAdsAuthorizationUrl,
  createSpApiAuthorizationUrl,
  listAmazonAdsApiAccess,
  listSpApiConnections,
  validateSpApiConnection,
  type AmazonAdsApiAccessSummary,
  type SpApiConnectionSummary,
  type SpApiValidateResult,
} from "../_lib/reportApiAccessApi";

const formatTimestamp = (value: string | null): string => {
  if (!value) return "Not recorded";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Intl.DateTimeFormat("en-CA", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(parsed));
};

export default function ReportApiAccessScreen() {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [loading, setLoading] = useState(true);
  const [launchingProfileId, setLaunchingProfileId] = useState<string | null>(null);
  const [launchingSpApiClientId, setLaunchingSpApiClientId] = useState<string | null>(null);
  const [validatingClientId, setValidatingClientId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [summaries, setSummaries] = useState<AmazonAdsApiAccessSummary[]>([]);
  const [spApiSummaries, setSpApiSummaries] = useState<SpApiConnectionSummary[]>([]);
  const [lastValidation, setLastValidation] = useState<SpApiValidateResult | null>(null);

  const loadSummaries = useCallback(async () => {
    setLoading(true);
    setErrorMessage(null);

    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session?.access_token) {
        throw new Error("Please sign in again.");
      }

      const [adsData, spApiData] = await Promise.all([
        listAmazonAdsApiAccess(session.access_token),
        listSpApiConnections(session.access_token),
      ]);
      setSummaries(adsData);
      setSpApiSummaries(spApiData);
    } catch (error) {
      setSummaries([]);
      setSpApiSummaries([]);
      setErrorMessage(error instanceof Error ? error.message : "Unable to load API access");
    } finally {
      setLoading(false);
    }
  }, [supabase]);

  useEffect(() => {
    void loadSummaries();
  }, [loadSummaries]);

  const handleConnect = useCallback(
    async (profileId: string) => {
      setLaunchingProfileId(profileId);
      setErrorMessage(null);
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();

        if (!session?.access_token) {
          throw new Error("Please sign in again.");
        }

        const url = await createAmazonAdsAuthorizationUrl(session.access_token, profileId);
        window.location.assign(url);
      } catch (error) {
        setLaunchingProfileId(null);
        setErrorMessage(error instanceof Error ? error.message : "Unable to start Amazon Ads connection");
      }
    },
    [supabase],
  );

  const handleSpApiConnect = useCallback(
    async (clientId: string) => {
      setLaunchingSpApiClientId(clientId);
      setErrorMessage(null);
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();

        if (!session?.access_token) {
          throw new Error("Please sign in again.");
        }

        const url = await createSpApiAuthorizationUrl(session.access_token, clientId);
        window.location.assign(url);
      } catch (error) {
        setLaunchingSpApiClientId(null);
        setErrorMessage(
          error instanceof Error ? error.message : "Unable to start Seller API connection",
        );
      }
    },
    [supabase],
  );

  const handleSpApiValidate = useCallback(
    async (clientId: string) => {
      setValidatingClientId(clientId);
      setLastValidation(null);
      setErrorMessage(null);
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();

        if (!session?.access_token) {
          throw new Error("Please sign in again.");
        }

        const result = await validateSpApiConnection(session.access_token, clientId);
        setLastValidation(result);
        void loadSummaries();
      } catch (error) {
        setErrorMessage(
          error instanceof Error ? error.message : "Validation request failed",
        );
      } finally {
        setValidatingClientId(null);
      }
    },
    [supabase, loadSummaries],
  );

  return (
    <main className="space-y-4">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-2xl font-semibold text-[#0f172a]">Reports / API Access</h1>
        <p className="mt-2 max-w-4xl text-sm text-[#4c576f]">
          Shared connection management for reporting surfaces. This first pass adds a shared Amazon
          Ads view while WBR profile selection and sync execution remain inside WBR.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            onClick={() => void loadSummaries()}
            disabled={loading}
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
          <Link
            href="/reports"
            className="rounded-2xl bg-[#e8eefc] px-4 py-3 text-sm font-semibold text-[#0f172a] transition hover:bg-[#d7e1fb]"
          >
            Back to Reports
          </Link>
        </div>

        {errorMessage ? (
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {errorMessage}
          </p>
        ) : null}

        <section className="mt-8 space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[#0a6fd6]">
                Amazon Ads
              </p>
              <p className="mt-2 text-sm text-[#4c576f]">
                Shared visibility over current auth state, with connection launches still anchored to
                an existing WBR profile during this non-breaking pass.
              </p>
            </div>
          </div>

          {loading ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-[#64748b]">
              Loading Amazon Ads connections...
            </div>
          ) : summaries.length === 0 ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-[#64748b]">
              No clients found for API access.
            </div>
          ) : (
            summaries.map((summary) => {
              const statusLabel = summary.connected ? "Connected" : "Not connected";
              const statusClasses = summary.connected
                ? "bg-[#e8f7ee] text-[#166534]"
                : "bg-[#f8fafc] text-[#475569]";
              const sourceLabel =
                summary.source === "shared"
                  ? "Shared table"
                  : summary.source === "legacy"
                    ? "Legacy WBR row"
                    : "No stored connection";
              const connection = summary.shared_connection ?? summary.legacy_connection;

              return (
                <div
                  key={summary.client_id}
                  className="rounded-3xl border border-slate-200 bg-white p-5 shadow transition hover:-translate-y-0.5 hover:shadow-lg md:p-6"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-lg font-semibold text-[#0f172a]">{summary.client_name}</p>
                      <p className="mt-1 text-sm text-[#4c576f]">
                        Client status: {summary.client_status} • Source: {sourceLabel}
                      </p>
                    </div>
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusClasses}`}>
                      {statusLabel}
                    </span>
                  </div>

                  <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
                    <div className="rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-4">
                      <p className="text-sm font-semibold text-[#0f172a]">Connection Summary</p>
                      <dl className="mt-3 grid gap-3 text-sm text-[#4c576f] sm:grid-cols-2">
                        <div>
                          <dt className="font-medium text-[#0f172a]">Connected at</dt>
                          <dd>{formatTimestamp(connection?.connected_at ?? null)}</dd>
                        </div>
                        <div>
                          <dt className="font-medium text-[#0f172a]">Last updated</dt>
                          <dd>{formatTimestamp(connection?.updated_at ?? null)}</dd>
                        </div>
                        <div>
                          <dt className="font-medium text-[#0f172a]">Account hint</dt>
                          <dd>{connection?.lwa_account_hint ?? "Not recorded"}</dd>
                        </div>
                        <div>
                          <dt className="font-medium text-[#0f172a]">Last validation</dt>
                          <dd>
                            {"last_validated_at" in (summary.shared_connection ?? {})
                              ? formatTimestamp(summary.shared_connection?.last_validated_at ?? null)
                              : "Not run yet"}
                          </dd>
                        </div>
                      </dl>
                      {summary.shared_connection?.last_error ? (
                        <p className="mt-4 rounded-xl border border-[#fecaca] bg-[#fff1f2] px-3 py-2 text-sm text-[#991b1b]">
                          {summary.shared_connection.last_error}
                        </p>
                      ) : null}
                    </div>

                    <div className="rounded-2xl border border-[#eadfcb] bg-[#fff8ed] p-4">
                      <p className="text-sm font-semibold text-[#0f172a]">Connect / Reauthorize</p>
                      <p className="mt-2 text-sm text-[#4c576f]">
                        Launch the existing OAuth flow from a WBR profile. This keeps the current WBR
                        sync path stable while writing shared connection state for the new surface.
                      </p>

                      {summary.connect_profiles.length === 0 ? (
                        <p className="mt-4 rounded-xl border border-[#e2e8f0] bg-white px-3 py-3 text-sm text-[#64748b]">
                          No WBR profile exists for this client yet. Create one before connecting Amazon Ads.
                        </p>
                      ) : (
                        <div className="mt-4 space-y-3">
                          {summary.connect_profiles.map((profile) => {
                            const isLaunching = launchingProfileId === profile.profile_id;
                            return (
                              <div
                                key={profile.profile_id}
                                className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#f2ddbb] bg-white px-4 py-3"
                              >
                                <div>
                                  <p className="text-sm font-semibold text-[#0f172a]">
                                    {profile.display_name} ({profile.marketplace_code})
                                  </p>
                                  <p className="mt-1 text-xs text-[#6b7280]">
                                    Status: {profile.status} • Ads profile: {profile.amazon_ads_profile_id ?? "Not selected"}
                                  </p>
                                </div>
                                <button
                                  onClick={() => void handleConnect(profile.profile_id)}
                                  disabled={Boolean(launchingProfileId)}
                                  className="rounded-xl bg-[#0a6fd6] px-4 py-2 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.2)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-slate-300"
                                >
                                  {isLaunching
                                    ? "Opening..."
                                    : summary.connected
                                      ? "Reauthorize"
                                      : "Connect"}
                                </button>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </section>

        <section className="mt-10 space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[#0a6fd6]">
                Amazon Seller API
              </p>
              <p className="mt-2 text-sm text-[#4c576f]">
                Seller-authorized SP-API connection for direct financial data access. Used by
                Monthly P&amp;L for payment/disbursement visibility.
              </p>
            </div>
          </div>

          {lastValidation ? (
            <div
              className={`rounded-xl border px-4 py-3 text-sm ${
                lastValidation.ok
                  ? "border-[#86efac] bg-[#f0fdf4] text-[#166534]"
                  : "border-[#fecaca] bg-[#fff1f2] text-[#991b1b]"
              }`}
            >
              {lastValidation.ok
                ? `Validation passed — ${lastValidation.marketplace_count} marketplace(s) visible`
                : `Validation failed at ${lastValidation.step}: ${lastValidation.error}`}
            </div>
          ) : null}

          {loading ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-[#64748b]">
              Loading Seller API connections...
            </div>
          ) : spApiSummaries.length === 0 ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-[#64748b]">
              No clients found for API access.
            </div>
          ) : (
            spApiSummaries.map((summary) => {
              const statusLabel = summary.connected ? "Connected" : "Not connected";
              const statusClasses = summary.connected
                ? "bg-[#e8f7ee] text-[#166534]"
                : "bg-[#f8fafc] text-[#475569]";
              const conn = summary.connection;
              const isLaunching = launchingSpApiClientId === summary.client_id;
              const isValidating = validatingClientId === summary.client_id;

              return (
                <div
                  key={summary.client_id}
                  className="rounded-3xl border border-slate-200 bg-white p-5 shadow transition hover:-translate-y-0.5 hover:shadow-lg md:p-6"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-lg font-semibold text-[#0f172a]">
                        {summary.client_name}
                      </p>
                      <p className="mt-1 text-sm text-[#4c576f]">
                        Client status: {summary.client_status}
                      </p>
                    </div>
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-semibold ${statusClasses}`}
                    >
                      {statusLabel}
                    </span>
                  </div>

                  <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
                    <div className="rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-4">
                      <p className="text-sm font-semibold text-[#0f172a]">Connection Summary</p>
                      <dl className="mt-3 grid gap-3 text-sm text-[#4c576f] sm:grid-cols-2">
                        <div>
                          <dt className="font-medium text-[#0f172a]">Connected at</dt>
                          <dd>{formatTimestamp(conn?.connected_at ?? null)}</dd>
                        </div>
                        <div>
                          <dt className="font-medium text-[#0f172a]">Last updated</dt>
                          <dd>{formatTimestamp(conn?.updated_at ?? null)}</dd>
                        </div>
                        <div>
                          <dt className="font-medium text-[#0f172a]">Selling Partner ID</dt>
                          <dd>{conn?.external_account_id ?? "Not recorded"}</dd>
                        </div>
                        <div>
                          <dt className="font-medium text-[#0f172a]">Last validation</dt>
                          <dd>{formatTimestamp(conn?.last_validated_at ?? null)}</dd>
                        </div>
                      </dl>
                      {conn?.last_error ? (
                        <p className="mt-4 rounded-xl border border-[#fecaca] bg-[#fff1f2] px-3 py-2 text-sm text-[#991b1b]">
                          {conn.last_error}
                        </p>
                      ) : null}
                    </div>

                    <div className="rounded-2xl border border-[#eadfcb] bg-[#fff8ed] p-4">
                      <p className="text-sm font-semibold text-[#0f172a]">
                        Connect / Validate
                      </p>
                      <p className="mt-2 text-sm text-[#4c576f]">
                        Launch the Seller Central OAuth flow to authorize this app, or validate
                        an existing connection.
                      </p>

                      <div className="mt-4 flex flex-wrap gap-3">
                        <button
                          onClick={() => void handleSpApiConnect(summary.client_id)}
                          disabled={Boolean(launchingSpApiClientId)}
                          className="rounded-xl bg-[#0a6fd6] px-4 py-2 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.2)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-slate-300"
                        >
                          {isLaunching
                            ? "Opening..."
                            : summary.connected
                              ? "Reauthorize"
                              : "Connect"}
                        </button>
                        {summary.connected ? (
                          <button
                            onClick={() => void handleSpApiValidate(summary.client_id)}
                            disabled={Boolean(validatingClientId)}
                            className="rounded-xl bg-white px-4 py-2 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
                          >
                            {isValidating ? "Validating..." : "Validate"}
                          </button>
                        ) : null}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </section>
      </div>
    </main>
  );
}
