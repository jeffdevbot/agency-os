"use client";

import Link from "next/link";
import { useEffect, useState, startTransition } from "react";

import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import {
  buildNativeNgramClientOptions,
  buildNativeNgramDefaultDateRange,
  buildNativeNgramProfileOptions,
  countInclusiveDays,
  getNativeNgramRunState,
  getNativeNgramValidationChecklist,
} from "./ngram2Presentation";
import { loadClientProfileSummaries, type ClientProfileSummary } from "../reports/_lib/reportClientData";
import {
  ACTIVE_SEARCH_TERM_AD_PRODUCTS,
  FUTURE_SEARCH_TERM_AD_PRODUCTS,
  type SearchTermAdProductKey,
} from "../reports/_lib/searchTermProducts";

const defaultDates = buildNativeNgramDefaultDateRange();
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

if (!BACKEND_URL) {
  throw new Error("NEXT_PUBLIC_BACKEND_URL is not configured");
}

export default function NgramTwoPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [failures, setFailures] = useState<string[]>([]);
  const [summaries, setSummaries] = useState<ClientProfileSummary[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<string>("");
  const [selectedProfileId, setSelectedProfileId] = useState<string>("");
  const [selectedProduct, setSelectedProduct] = useState<SearchTermAdProductKey>("sp");
  const [dateFrom, setDateFrom] = useState(defaultDates.from);
  const [dateTo, setDateTo] = useState(defaultDates.to);
  const [legacyExclusions, setLegacyExclusions] = useState(true);
  const [preferWorkbook, setPreferWorkbook] = useState(true);
  const [workbookGenerating, setWorkbookGenerating] = useState(false);
  const [workbookError, setWorkbookError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    const supabase = getBrowserSupabaseClient();

    const load = async () => {
      setLoading(true);
      setError(null);

      try {
        const { data } = await supabase.auth.getSession();
        const accessToken = data.session?.access_token;

        if (!accessToken) {
          setError("Sign in first to preview native N-Gram setup.");
          setLoading(false);
          return;
        }

        const result = await loadClientProfileSummaries(accessToken);
        const sortedSummaries = [...result.summaries].sort((left, right) =>
          left.client.name.localeCompare(right.client.name),
        );

        startTransition(() => {
          setSummaries(sortedSummaries);
          setFailures(result.failures);

          const clientOptions = buildNativeNgramClientOptions(sortedSummaries);
          const nextClientId = clientOptions[0]?.clientId ?? "";
          const profileOptions = buildNativeNgramProfileOptions(sortedSummaries, nextClientId);

          setSelectedClientId(nextClientId);
          setSelectedProfileId(profileOptions[0]?.profileId ?? "");
        });
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load native N-Gram setup.");
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, []);

  const clientOptions = buildNativeNgramClientOptions(summaries);
  const activeClientId = selectedClientId || clientOptions[0]?.clientId || "";
  const profileOptions = buildNativeNgramProfileOptions(summaries, activeClientId);
  const activeProfileId = selectedProfileId || profileOptions[0]?.profileId || "";
  const selectedProfile = profileOptions.find((profile) => profile.profileId === activeProfileId) ?? null;
  const validationChecklist = getNativeNgramValidationChecklist(selectedProduct);
  const dayCount = countInclusiveDays(dateFrom, dateTo);
  const runState = getNativeNgramRunState(selectedProfile, selectedProduct);
  const selectedProductConfig =
    [...ACTIVE_SEARCH_TERM_AD_PRODUCTS, ...FUTURE_SEARCH_TERM_AD_PRODUCTS].find(
      (product) => product.key === selectedProduct,
    ) ?? null;
  const canGenerateWorkbook =
    !loading &&
    !workbookGenerating &&
    selectedProduct === "sp" &&
    runState.tone === "ready" &&
    Boolean(selectedProfile?.profileId) &&
    dayCount !== null;

  const runStateClasses =
    runState.tone === "ready"
      ? "border-[#c7ebd4] bg-[#edf9f1] text-[#1f6b37]"
      : runState.tone === "caution"
        ? "border-[#f1dfbe] bg-[#fff7eb] text-[#8a5a15]"
        : "border-[#e2d7d7] bg-[#fff6f6] text-[#8f1d1d]";

  const handleGenerateWorkbook = async () => {
    if (!canGenerateWorkbook || !selectedProfile) return;

    setWorkbookGenerating(true);
    setWorkbookError(null);

    try {
      const supabase = getBrowserSupabaseClient();
      const { data } = await supabase.auth.getSession();
      const accessToken = data.session?.access_token;

      if (!accessToken) {
        setWorkbookError("Please sign in again.");
        setWorkbookGenerating(false);
        return;
      }

      const response = await fetch(`${BACKEND_URL}/ngram/native-workbook`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          profile_id: selectedProfile.profileId,
          ad_product: selectedProductConfig?.amazonAdsAdProduct,
          date_from: dateFrom,
          date_to: dateTo,
          respect_legacy_exclusions: legacyExclusions,
        }),
      });

      if (!response.ok) {
        const detail = await response.json().catch(() => undefined);
        throw new Error(detail?.detail || "Native workbook generation failed");
      }

      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const disposition = response.headers.get("content-disposition") || "";
      const match = disposition.match(/filename=\"?([^\";]+)\"?/i);
      const filename = match?.[1] || `${selectedProfile.displayName.replace(/\s+/g, "_")}_native_ngrams.xlsx`;

      const anchor = document.createElement("a");
      anchor.href = downloadUrl;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(downloadUrl);

      setToast("Native workbook download started.");
      window.setTimeout(() => setToast(null), 3200);
    } catch (generateError) {
      setWorkbookError(
        generateError instanceof Error ? generateError.message : "Native workbook generation failed",
      );
    } finally {
      setWorkbookGenerating(false);
    }
  };

  useEffect(() => {
    if (!activeClientId) return;
    if (selectedClientId === activeClientId) return;
    setSelectedClientId(activeClientId);
  }, [activeClientId, selectedClientId]);

  useEffect(() => {
    if (!selectedClientId) return;
    const nextProfiles = buildNativeNgramProfileOptions(summaries, selectedClientId);
    if (nextProfiles.length === 0) {
      if (selectedProfileId) setSelectedProfileId("");
      return;
    }
    if (!nextProfiles.some((profile) => profile.profileId === selectedProfileId)) {
      setSelectedProfileId(nextProfiles[0]?.profileId ?? "");
    }
  }, [selectedClientId, selectedProfileId, summaries]);

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(255,216,155,0.35),_transparent_28%),radial-gradient(circle_at_top_right,_rgba(126,180,255,0.28),_transparent_34%),linear-gradient(180deg,_#f6efe4_0%,_#f7f8fb_52%,_#edf3ff_100%)]">
      <header className="border-b border-black/5 bg-white/70 px-6 py-5 backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <span className="rounded-full border border-[#d8c4a4] bg-[#fff7eb] px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-[#8a5a15]">
                Experimental
              </span>
              <span className="rounded-full border border-[#cad8f7] bg-[#eff5ff] px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-[#2453a6]">
                Workbook First
              </span>
            </div>
            <div>
              <h1 className="text-4xl font-black tracking-tight text-[#1b2430]">N-Gram 2.0</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-[#526074]">
                Native Amazon search-term ingestion on the front end of the current N-Gram process.
                The legacy <Link href="/ngram" className="font-semibold text-[#0a6fd6] underline decoration-[#9abfff] underline-offset-4">N-Gram Processor</Link> remains untouched while this workflow is being built.
              </p>
            </div>
          </div>

          <div className="rounded-[28px] border border-white/70 bg-white/75 px-5 py-4 shadow-[0_20px_60px_rgba(25,36,54,0.12)] backdrop-blur">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[#8c97aa]">Current Plan</p>
            <p className="mt-2 text-sm font-semibold text-[#1b2430]">Generate native workbook input first.</p>
            <p className="mt-1 max-w-sm text-sm leading-6 text-[#526074]">
              Mirror today’s workbook-driven team flow now. Keep AI and direct-publish paths visible, but secondary.
            </p>
          </div>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-7xl flex-col gap-8 px-6 py-8">
        <section className="grid gap-8 xl:grid-cols-[1.15fr_0.85fr]">
          <div className="rounded-[32px] border border-white/70 bg-white/80 p-7 shadow-[0_30px_80px_rgba(28,44,79,0.12)] backdrop-blur">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[#9c6b1f]">Step 1</p>
                <h2 className="mt-2 text-2xl font-bold text-[#1b2430]">Create Native Run</h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-[#526074]">
                  Pick the client, marketplace, ad product, and date range that should feed the next
                  workbook. This route stays separate from the live legacy uploader until the native path earns trust.
                </p>
              </div>
              <Link
                href="/ngram"
                className="rounded-full border border-[#c9d8f8] bg-[#eff5ff] px-4 py-2 text-sm font-semibold text-[#2453a6] transition hover:bg-[#e1ecff]"
              >
                Open Classic N-Gram
              </Link>
            </div>

            <div className="mt-8 grid gap-5 md:grid-cols-2">
              <label className="space-y-2">
                <span className="text-sm font-semibold text-[#1b2430]">Client</span>
                <select
                  value={activeClientId}
                  onChange={(event) => setSelectedClientId(event.target.value)}
                  className="w-full rounded-2xl border border-[#d4ddea] bg-white px-4 py-3 text-sm text-[#1b2430] shadow-sm outline-none transition focus:border-[#8bb6ff] focus:ring-4 focus:ring-[#d8e8ff]"
                >
                  {clientOptions.length === 0 ? <option value="">No connected clients found</option> : null}
                  {clientOptions.map((client) => (
                    <option key={client.clientId} value={client.clientId}>
                      {client.clientName} ({client.profileCount})
                    </option>
                  ))}
                </select>
              </label>

              <label className="space-y-2">
                <span className="text-sm font-semibold text-[#1b2430]">Marketplace</span>
                <select
                  value={activeProfileId}
                  onChange={(event) => setSelectedProfileId(event.target.value)}
                  className="w-full rounded-2xl border border-[#d4ddea] bg-white px-4 py-3 text-sm text-[#1b2430] shadow-sm outline-none transition focus:border-[#8bb6ff] focus:ring-4 focus:ring-[#d8e8ff]"
                >
                  {profileOptions.length === 0 ? <option value="">No connected marketplace found</option> : null}
                  {profileOptions.map((profile) => (
                    <option key={profile.profileId} value={profile.profileId}>
                      {profile.displayName} ({profile.marketplaceCode})
                    </option>
                  ))}
                </select>
              </label>

              <label className="space-y-2">
                <span className="text-sm font-semibold text-[#1b2430]">Date from</span>
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(event) => setDateFrom(event.target.value)}
                  className="w-full rounded-2xl border border-[#d4ddea] bg-white px-4 py-3 text-sm text-[#1b2430] shadow-sm outline-none transition focus:border-[#8bb6ff] focus:ring-4 focus:ring-[#d8e8ff]"
                />
              </label>

              <label className="space-y-2">
                <span className="text-sm font-semibold text-[#1b2430]">Date to</span>
                <input
                  type="date"
                  value={dateTo}
                  onChange={(event) => setDateTo(event.target.value)}
                  className="w-full rounded-2xl border border-[#d4ddea] bg-white px-4 py-3 text-sm text-[#1b2430] shadow-sm outline-none transition focus:border-[#8bb6ff] focus:ring-4 focus:ring-[#d8e8ff]"
                />
              </label>
            </div>

            <div className="mt-8">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-sm font-semibold text-[#1b2430]">Ad product</span>
                  <p className="mt-1 text-sm text-[#526074]">
                    Keep the first release anchored to the real native contract per ad product.
                  </p>
                </div>
                <span className="rounded-full bg-[#f5efe1] px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-[#9c6b1f]">
                  Select one
                </span>
              </div>

              <div className="mt-4 grid gap-4 lg:grid-cols-3">
                {ACTIVE_SEARCH_TERM_AD_PRODUCTS.map((product) => {
                  const selected = selectedProduct === product.key;
                  return (
                    <button
                      key={product.key}
                      type="button"
                      onClick={() => setSelectedProduct(product.key)}
                      className={`rounded-[26px] border p-5 text-left transition ${
                        selected
                          ? "border-[#8ab5ff] bg-[#eef5ff] shadow-[0_15px_35px_rgba(47,102,198,0.18)]"
                          : "border-[#d7dfec] bg-white hover:border-[#b9caea] hover:bg-[#fbfcff]"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-lg font-bold text-[#1b2430]">{product.label}</p>
                          <p className="mt-1 text-xs font-semibold uppercase tracking-[0.22em] text-[#6f7e95]">
                            {product.shortLabel}
                          </p>
                        </div>
                        <span
                          className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] ${
                            product.status === "live"
                              ? "bg-[#eaf7ee] text-[#1c7a3b]"
                              : "bg-[#fff2df] text-[#9c6b1f]"
                          }`}
                        >
                          {product.status}
                        </span>
                      </div>
                      <p className="mt-4 text-sm leading-6 text-[#526074]">{product.summary}</p>
                      <p className="mt-3 text-xs leading-5 text-[#7a879b]">{product.availabilityNote}</p>
                    </button>
                  );
                })}

                {FUTURE_SEARCH_TERM_AD_PRODUCTS.map((product) => (
                  <div
                    key={product.key}
                    className="rounded-[26px] border border-dashed border-[#d7dfec] bg-white/70 p-5 text-left opacity-80"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-lg font-bold text-[#1b2430]">{product.label}</p>
                        <p className="mt-1 text-xs font-semibold uppercase tracking-[0.22em] text-[#6f7e95]">
                          {product.shortLabel}
                        </p>
                      </div>
                      <span className="rounded-full bg-[#f2f4f8] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-[#65748a]">
                        planned
                      </span>
                    </div>
                    <p className="mt-4 text-sm leading-6 text-[#526074]">{product.summary}</p>
                    <p className="mt-3 text-xs leading-5 text-[#7a879b]">{product.availabilityNote}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-8 grid gap-3 md:grid-cols-2">
              <button
                type="button"
                onClick={() => setLegacyExclusions((current) => !current)}
                className={`rounded-2xl border px-4 py-4 text-left transition ${
                  legacyExclusions
                    ? "border-[#c7d9ff] bg-[#eef5ff]"
                    : "border-[#d7dfec] bg-white"
                }`}
              >
                <p className="text-sm font-semibold text-[#1b2430]">Respect legacy exclusions</p>
                <p className="mt-1 text-sm text-[#526074]">
                  Start with the current N-Gram exclusions for campaign names containing
                  <span className="font-semibold text-[#1b2430]"> Ex.</span>,
                  <span className="font-semibold text-[#1b2430]"> SDI</span>, or
                  <span className="font-semibold text-[#1b2430]"> SDV</span>.
                </p>
              </button>

              <button
                type="button"
                onClick={() => setPreferWorkbook((current) => !current)}
                className={`rounded-2xl border px-4 py-4 text-left transition ${
                  preferWorkbook
                    ? "border-[#f0d0a5] bg-[#fff6ea]"
                    : "border-[#d7dfec] bg-white"
                }`}
              >
                <p className="text-sm font-semibold text-[#1b2430]">Keep workbook as the first output</p>
                <p className="mt-1 text-sm text-[#526074]">
                  Preserve the current analyst-manager review rhythm while the native path earns trust.
                </p>
              </button>
            </div>

            <div className="mt-8 rounded-[26px] border border-[#e4e8f2] bg-[#fbfcff] p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-[#1b2430]">Run readiness</p>
                  <p className="mt-1 text-sm text-[#526074]">{runState.note}</p>
                </div>
                <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${runStateClasses}`}>
                  {runState.label}
                </span>
              </div>

              <div className="mt-4 grid gap-4 md:grid-cols-3">
                <div className="rounded-2xl border border-[#e7ebf3] bg-white px-4 py-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7d8ba1]">Range span</p>
                  <p className="mt-2 text-lg font-bold text-[#1b2430]">
                    {dayCount === null ? "Invalid dates" : `${dayCount} day${dayCount === 1 ? "" : "s"}`}
                  </p>
                </div>
                <div className="rounded-2xl border border-[#e7ebf3] bg-white px-4 py-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7d8ba1]">Selected lane</p>
                  <p className="mt-2 text-lg font-bold text-[#1b2430]">
                    {selectedProductConfig?.label ?? "Unknown"}
                  </p>
                </div>
                <div className="rounded-2xl border border-[#e7ebf3] bg-white px-4 py-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7d8ba1]">Nightly sync</p>
                  <p className="mt-2 text-lg font-bold text-[#1b2430]">
                    {selectedProfile?.nightlyByProduct[selectedProduct] ? "Enabled" : "Manual / on demand"}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="rounded-[32px] border border-white/70 bg-[#1f2d44] p-6 text-white shadow-[0_30px_80px_rgba(18,28,44,0.22)]">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[#c7d5ef]">Run Blueprint</p>
              <div className="mt-5 space-y-4">
                <div>
                  <p className="text-sm text-[#b6c5df]">Client / Marketplace</p>
                  <p className="mt-1 text-lg font-semibold">
                    {selectedProfile ? `${selectedProfile.clientName} · ${selectedProfile.displayName}` : "Select a connected marketplace"}
                  </p>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <p className="text-sm text-[#b6c5df]">Ad product</p>
                    <p className="mt-1 text-base font-semibold">
                      {ACTIVE_SEARCH_TERM_AD_PRODUCTS.find((product) => product.key === selectedProduct)?.label ?? "Not selected"}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-[#b6c5df]">Window</p>
                    <p className="mt-1 text-base font-semibold">
                      {dateFrom} to {dateTo}
                    </p>
                  </div>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="rounded-2xl bg-white/8 px-4 py-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#b6c5df]">Connection</p>
                    <p className="mt-2 text-sm font-semibold">
                      {selectedProfile?.hasAmazonAdsConnection ? "Amazon Ads connected" : "Connection required"}
                    </p>
                  </div>
                  <div className="rounded-2xl bg-white/8 px-4 py-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#b6c5df]">Native sync</p>
                    <p className="mt-2 text-sm font-semibold">
                      {selectedProfile?.hasSearchTermSync ? "Sync is enabled on this profile" : "Sync can be run on demand"}
                    </p>
                  </div>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="rounded-2xl bg-white/8 px-4 py-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#b6c5df]">Profile status</p>
                    <p className="mt-2 text-sm font-semibold">
                      {selectedProfile?.profileStatus ? selectedProfile.profileStatus : "Unknown"}
                    </p>
                  </div>
                  <div className="rounded-2xl bg-white/8 px-4 py-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#b6c5df]">Validation posture</p>
                    <p className="mt-2 text-sm font-semibold">{runState.label}</p>
                  </div>
                </div>
                <div className="rounded-[26px] border border-white/12 bg-white/6 p-4">
                  <p className="text-sm font-semibold">Why this route exists</p>
                  <p className="mt-2 text-sm leading-6 text-[#c7d5ef]">
                    Replace the old Pacvue upload step first. Do not force a new analyst workflow until native
                    workbook generation and export validation are stable.
                  </p>
                </div>
              </div>
            </div>

            {error ? (
              <div className="rounded-[28px] border border-[#f3c3c3] bg-[#fff5f5] p-5 text-sm text-[#8f1d1d] shadow-sm">
                {error}
              </div>
            ) : null}

            {workbookError ? (
              <div className="rounded-[28px] border border-[#f3c3c3] bg-[#fff5f5] p-5 text-sm text-[#8f1d1d] shadow-sm">
                {workbookError}
              </div>
            ) : null}

            {failures.length > 0 ? (
              <div className="rounded-[28px] border border-[#f0d9b1] bg-[#fff8ee] p-5 text-sm text-[#7d5a1d] shadow-sm">
                <p className="font-semibold">Some client summaries failed to load.</p>
                <p className="mt-2">{failures[0]}</p>
              </div>
            ) : null}
          </div>
        </section>

        <section className="grid gap-8 lg:grid-cols-[0.95fr_1.05fr]">
          <div className="rounded-[32px] border border-white/70 bg-white/80 p-7 shadow-[0_30px_80px_rgba(28,44,79,0.12)] backdrop-blur">
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[#9c6b1f]">Step 2</p>
            <h2 className="mt-2 text-2xl font-bold text-[#1b2430]">Validate the Data</h2>
            <p className="mt-2 text-sm leading-6 text-[#526074]">
              Trust first. The native route should tell the operator exactly what to compare before a workbook is generated.
            </p>

            <div className="mt-6 space-y-4">
              {validationChecklist.map((item) => (
                <div key={item} className="flex gap-3 rounded-2xl border border-[#e4e8f2] bg-[#fbfcff] px-4 py-4">
                  <div className="mt-0.5 flex h-6 w-6 items-center justify-center rounded-full bg-[#eff5ff] text-sm font-bold text-[#2453a6]">
                    ✓
                  </div>
                  <p className="text-sm leading-6 text-[#445165]">{item}</p>
                </div>
              ))}
            </div>

            <div className="mt-6 rounded-[26px] border border-[#e5ecfb] bg-[linear-gradient(135deg,_rgba(233,242,255,0.92),_rgba(255,250,242,0.92))] p-5">
              <p className="text-sm font-semibold text-[#1b2430]">Validation UX direction</p>
              <p className="mt-2 text-sm leading-6 text-[#526074]">
                Show selected window totals here once the native workbook endpoint exists, then prompt the user to
                compare them directly to the matching Amazon export before proceeding.
              </p>
              <button
                type="button"
                disabled
                className="mt-4 rounded-2xl border border-[#d2ddf7] bg-white px-4 py-3 text-sm font-semibold text-[#5d6f91] opacity-75"
              >
                Imported totals preview coming next
              </button>
            </div>
          </div>

          <div className="rounded-[32px] border border-white/70 bg-white/80 p-7 shadow-[0_30px_80px_rgba(28,44,79,0.12)] backdrop-blur">
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[#9c6b1f]">Step 3</p>
            <h2 className="mt-2 text-2xl font-bold text-[#1b2430]">Choose Output Path</h2>
            <p className="mt-2 text-sm leading-6 text-[#526074]">
              The default release should mirror how the team already works: workbook first, AI second.
            </p>

            <div className="mt-6 grid gap-5 xl:grid-cols-2">
              <div className="rounded-[28px] border border-[#cfe0ff] bg-[#eff5ff] p-5 shadow-[0_18px_40px_rgba(55,105,196,0.12)]">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-lg font-bold text-[#1b2430]">Generate workbook</p>
                  <span className="rounded-full bg-white px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#2453a6]">
                    first ship
                  </span>
                </div>
                <p className="mt-3 text-sm leading-6 text-[#445165]">
                  Produce the familiar mono/bi/tri workbook from native data so analysts can stay in the current review
                  loop and managers can keep their approval step.
                </p>
                <button
                  type="button"
                  disabled={!canGenerateWorkbook}
                  onClick={handleGenerateWorkbook}
                  className="mt-5 w-full rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-[#b7cbea]"
                >
                  {workbookGenerating ? "Generating workbook…" : "Generate native workbook"}
                </button>
                <p className="mt-3 text-xs leading-5 text-[#64748b]">
                  {selectedProduct === "sp"
                    ? "Uses native Sponsored Products search-term facts for the selected window and keeps the legacy exclusion rules."
                    : "Workbook generation is currently enabled for Sponsored Products first."}
                </p>
              </div>

              <div className="rounded-[28px] border border-[#eadfcf] bg-[#fff8ee] p-5">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-lg font-bold text-[#1b2430]">AI-assisted analysis</p>
                  <span className="rounded-full bg-white px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#9c6b1f]">
                    later
                  </span>
                </div>
                <p className="mt-3 text-sm leading-6 text-[#5a6170]">
                  Offer a side-by-side acceleration path once the native workbook output is trusted. Same structure, less
                  manual filling, no forced process change.
                </p>
                <button
                  type="button"
                  disabled
                  className="mt-5 w-full rounded-2xl border border-[#dbcfbc] bg-white px-4 py-3 text-sm font-semibold text-[#6d747f] opacity-75"
                >
                  AI path intentionally deferred
                </button>
              </div>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-2">
              <div className="rounded-2xl border border-[#e4e8f2] bg-[#fbfcff] px-4 py-4">
                <p className="text-sm font-semibold text-[#1b2430]">Legacy path stays live</p>
                <p className="mt-2 text-sm leading-6 text-[#526074]">
                  The current uploader remains available in parallel so the team can ignore this route until it proves
                  itself.
                </p>
              </div>
              <div className="rounded-2xl border border-[#e4e8f2] bg-[#fbfcff] px-4 py-4">
                <p className="text-sm font-semibold text-[#1b2430]">First backend target</p>
                <p className="mt-2 text-sm leading-6 text-[#526074]">
                  Wire a native workbook-generation endpoint for selected SP data, then let SB join only after the
                  export parity question is resolved.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-[32px] border border-white/70 bg-white/80 p-7 shadow-[0_30px_80px_rgba(28,44,79,0.12)] backdrop-blur">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[#9c6b1f]">Old vs New</p>
              <h2 className="mt-2 text-2xl font-bold text-[#1b2430]">Native replacement, not process replacement</h2>
            </div>
            <span className="rounded-full border border-[#d9e4fa] bg-[#f6f9ff] px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-[#5a6f9d]">
              First pass UI
            </span>
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            <div className="rounded-[26px] border border-[#e4e8f2] bg-[#fbfcff] p-5">
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#7d8ba1]">Today</p>
              <ul className="mt-4 space-y-3 text-sm leading-6 text-[#445165]">
                <li>Upload Pacvue-style search-term file.</li>
                <li>Download workbook and fill grams manually.</li>
                <li>Manager reviews.</li>
                <li>Re-upload workbook to clean outputs.</li>
                <li>Copy or upload negatives into Pacvue.</li>
              </ul>
            </div>
            <div className="rounded-[26px] border border-[#d7e4ff] bg-[linear-gradient(135deg,_rgba(237,245,255,0.92),_rgba(255,250,242,0.92))] p-5">
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#2453a6]">N-Gram 2.0</p>
              <ul className="mt-4 space-y-3 text-sm leading-6 text-[#445165]">
                <li>Select native client, marketplace, ad product, and dates.</li>
                <li>Validate totals against Amazon export on the same window.</li>
                <li>Generate the familiar workbook from native data.</li>
                <li>Keep manual review and manager approval intact.</li>
                <li>Add AI and direct publish only after trust is earned.</li>
              </ul>
            </div>
          </div>

          {loading ? (
            <p className="mt-6 text-sm text-[#6c7a8f]">Loading client and marketplace options…</p>
          ) : null}
        </section>
      </div>

      {toast ? (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-full bg-[#0a6fd6] px-6 py-3 text-sm font-semibold text-white shadow-lg">
          {toast}
        </div>
      ) : null}
    </main>
  );
}
