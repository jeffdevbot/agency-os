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
import {
  loadClientProfileSummaries,
  slugifyClientName,
  type ClientProfileSummary,
} from "../reports/_lib/reportClientData";
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

type NativeNgramTotals = {
  impressions: number;
  clicks: number;
  spend: number;
  orders: number;
  sales: number;
};

type NativeNgramCampaignSummary = {
  campaign_name: string;
  search_terms: number;
  spend: number;
};

type NativeNgramSummary = {
  ad_product: string;
  profile_id: string;
  profile_display_name: string;
  marketplace_code: string | null;
  date_from: string;
  date_to: string;
  raw_rows: number;
  eligible_rows: number;
  excluded_asin_rows: number;
  excluded_incomplete_rows: number;
  unique_campaigns: number;
  unique_search_terms: number;
  campaigns_included: number;
  campaigns_skipped: number;
  report_dates_present: number;
  coverage_start: string | null;
  coverage_end: string | null;
  imported_totals: NativeNgramTotals;
  workbook_input_totals: NativeNgramTotals;
  campaigns: NativeNgramCampaignSummary[];
  warnings: string[];
};

type AIPrefillRecommendation = {
  search_term: string;
  recommendation: "KEEP" | "NEGATE" | "REVIEW";
  confidence: "HIGH" | "MEDIUM" | "LOW";
  reason_tag: string;
  rationale: string | null;
  spend: number;
  clicks: number;
  orders: number;
  sales: number;
  keyword: string | null;
  keywordType: string | null;
  targeting: string | null;
  matchType: string | null;
};

type AIPrefillStrategy = "heuristic_synthesis" | "pure_model_single_campaign";

type PureModelPhraseNegative = {
  phrase: string;
  bucket: "mono" | "bi" | "tri";
  confidence: "HIGH" | "MEDIUM" | "LOW";
  sourceTerms: string[];
  rationale: string | null;
};

type AIPrefillCampaignPreview = {
  prefillStrategy: AIPrefillStrategy;
  campaignName: string;
  totalSpend: number;
  eligibleSpend: number;
  totalTerms: number;
  eligibleTerms: number;
  skippedBelowThresholdTerms: number;
  productIdentifier: string | null;
  theme: string | null;
  matchStatus: "matched" | "ambiguous" | "intentionally_skipped";
  matchSource: "ai_combined" | "none";
  skipReason: "brand_mix_defensive" | "missing_identifier" | null;
  matchedTitle: string | null;
  category: string | null;
  itemDescription: string | null;
  matchScore: number | null;
  synthesizedPrefills: {
    mono: Array<{ gram: string; supportTerms: string[]; negateCount: number; keepCount: number; reviewCount: number; negateSpend: number; weightedScore: number }>;
    bi: Array<{ gram: string; supportTerms: string[]; negateCount: number; keepCount: number; reviewCount: number; negateSpend: number; weightedScore: number }>;
    tri: Array<{ gram: string; supportTerms: string[]; negateCount: number; keepCount: number; reviewCount: number; negateSpend: number; weightedScore: number }>;
  };
  modelPrefills: {
    exact: string[];
    mono: string[];
    bi: string[];
    tri: string[];
  };
  phraseNegatives: PureModelPhraseNegative[];
  evaluations: AIPrefillRecommendation[];
};

type AIPrefillPreview = {
  run_mode?: "preview" | "full";
  prefill_strategy?: AIPrefillStrategy;
  ad_product: string;
  profile_id: string;
  date_from: string;
  date_to: string;
  spend_threshold: number;
  max_campaigns: number | null;
  max_terms_per_campaign: number | null;
  raw_rows: number;
  eligible_rows: number;
  candidate_campaigns: number;
  runnable_campaigns?: number;
  preview_campaigns: number;
  selected_campaigns?: string[];
  ambiguous_campaigns: number;
  intentionally_skipped_campaigns: number;
  recommendation_counts: {
    keep: number;
    negate: number;
    review: number;
  };
  model: string | null;
  campaigns: AIPrefillCampaignPreview[];
  warnings: string[];
};

const formatNumber = (value: number): string => value.toLocaleString();

const formatCurrency = (value: number, currencyCode: string | null | undefined): string =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currencyCode ?? "USD",
    minimumFractionDigits: 2,
  }).format(value);

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
  const [workbookGenerating, setWorkbookGenerating] = useState(false);
  const [workbookError, setWorkbookError] = useState<string | null>(null);
  const [aiWorkbookGenerating, setAiWorkbookGenerating] = useState(false);
  const [aiWorkbookError, setAiWorkbookError] = useState<string | null>(null);
  const [aiPreviewWorkbookGenerating, setAiPreviewWorkbookGenerating] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [summary, setSummary] = useState<NativeNgramSummary | null>(null);
  const [spendThreshold, setSpendThreshold] = useState("3");
  const [aiCampaignQuery, setAiCampaignQuery] = useState("");
  const [selectedAiCampaignNames, setSelectedAiCampaignNames] = useState<string[]>([]);
  const [aiPreviewLoading, setAiPreviewLoading] = useState(false);
  const [aiPreviewError, setAiPreviewError] = useState<string | null>(null);
  const [aiPreview, setAiPreview] = useState<AIPrefillPreview | null>(null);
  const [aiPreviewRunId, setAiPreviewRunId] = useState<string | null>(null);
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
  const activeClientSummary = summaries.find((summary) => summary.client.id === activeClientId) ?? null;
  const activeClientSlug = activeClientSummary ? slugifyClientName(activeClientSummary.client.name) : "";
  const validationChecklist = getNativeNgramValidationChecklist(selectedProduct);
  const dayCount = countInclusiveDays(dateFrom, dateTo);
  const runState = getNativeNgramRunState(selectedProfile, selectedProduct);
  const selectedProductConfig =
    [...ACTIVE_SEARCH_TERM_AD_PRODUCTS, ...FUTURE_SEARCH_TERM_AD_PRODUCTS].find(
      (product) => product.key === selectedProduct,
    ) ?? null;
  const inspectRowsHref =
    selectedProduct === "sp" && selectedProfile?.profileId && activeClientSlug
      ? `/reports/search-term-data/${activeClientSlug}?${new URLSearchParams({
          profile_id: selectedProfile.profileId,
          date_from: dateFrom,
          date_to: dateTo,
          ad_product: selectedProductConfig?.amazonAdsAdProduct ?? "SPONSORED_PRODUCTS",
        }).toString()}`
      : null;
  const summaryAllowsWorkbook = Boolean(summary && summary.eligible_rows > 0);
  const canGenerateWorkbook =
    !loading &&
    !workbookGenerating &&
    selectedProduct === "sp" &&
    runState.tone === "ready" &&
    Boolean(selectedProfile?.profileId) &&
    dayCount !== null &&
    !summaryLoading &&
    !summaryError &&
    summaryAllowsWorkbook;
  const canRunAiPreview =
    !loading &&
    !aiPreviewLoading &&
    selectedProduct === "sp" &&
    runState.tone === "ready" &&
    Boolean(selectedProfile?.profileId) &&
    dayCount !== null &&
    !summaryLoading &&
    !summaryError &&
    summaryAllowsWorkbook;
  const aiScratchpadCounts = aiPreview
    ? aiPreview.campaigns.reduce(
        (counts, campaign) => {
          if (campaign.prefillStrategy === "pure_model_single_campaign") {
            counts.mono += campaign.modelPrefills.mono.length;
            counts.bi += campaign.modelPrefills.bi.length;
            counts.tri += campaign.modelPrefills.tri.length;
          } else {
            counts.mono += campaign.synthesizedPrefills.mono.length;
            counts.bi += campaign.synthesizedPrefills.bi.length;
            counts.tri += campaign.synthesizedPrefills.tri.length;
          }
          return counts;
        },
        { mono: 0, bi: 0, tri: 0 },
      )
    : { mono: 0, bi: 0, tri: 0 };
  const aiExactPrefillCount = aiPreview
    ? aiPreview.campaigns.reduce((count, campaign) => count + campaign.modelPrefills.exact.length, 0)
    : 0;
  const canGenerateAiWorkbook = canGenerateWorkbook && !aiWorkbookGenerating;
  const canGenerateAiPreviewWorkbook =
    canGenerateWorkbook && !aiPreviewWorkbookGenerating && Boolean(aiPreviewRunId) && Boolean(selectedProfile?.profileId);
  const filteredCampaignOptions = (summary?.campaigns ?? [])
    .filter((campaign) =>
      aiCampaignQuery.trim()
        ? campaign.campaign_name.toLowerCase().includes(aiCampaignQuery.trim().toLowerCase())
        : true,
    )
    .slice(0, 24);
  const hasSelectedAiCampaignSubset = selectedAiCampaignNames.length > 0;
  const canRunPureModelPreview = canRunAiPreview && selectedAiCampaignNames.length === 1;

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

  const handleGenerateAiWorkbook = async () => {
    if (!canGenerateAiWorkbook || !selectedProfile) return;

    const parsedThreshold = Number.parseFloat(spendThreshold);
    if (!Number.isFinite(parsedThreshold) || parsedThreshold < 0) {
      setAiWorkbookError("Spend threshold must be a number greater than or equal to 0.");
      return;
    }

    setAiWorkbookGenerating(true);
    setAiWorkbookError(null);

    try {
      const previewResponse = await fetch("/api/ngram-2/ai-prefill-preview", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          profile_id: selectedProfile.profileId,
          ad_product: selectedProductConfig?.amazonAdsAdProduct,
          date_from: dateFrom,
          date_to: dateTo,
          spend_threshold: parsedThreshold,
          respect_legacy_exclusions: legacyExclusions,
          run_mode: "full",
        }),
      });

      if (!previewResponse.ok) {
        const detail = await previewResponse.json().catch(() => undefined);
        throw new Error(detail?.detail || "Full AI workbook run failed");
      }

      const previewPayload = (await previewResponse.json()) as {
        preview?: AIPrefillPreview;
        preview_run_id?: string | null;
      };
      const fullRun = previewPayload.preview ?? null;
      const fullRunId = previewPayload.preview_run_id ?? null;

      if (!fullRun || !fullRunId) {
        throw new Error("Full AI workbook run did not return a saved run id.");
      }

      const supabase = getBrowserSupabaseClient();
      const { data } = await supabase.auth.getSession();
      const accessToken = data.session?.access_token;

      if (!accessToken) {
        setAiWorkbookError("Please sign in again.");
        setAiWorkbookGenerating(false);
        return;
      }

      const response = await fetch(`${BACKEND_URL}/ngram/native-workbook-prefilled`, {
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
          preview_run_id: fullRunId,
          campaign_prefills: fullRun.campaigns
            .map((campaign) => ({
              campaign_name: campaign.campaignName,
              mono: campaign.synthesizedPrefills.mono.map((item) => item.gram),
              bi: campaign.synthesizedPrefills.bi.map((item) => item.gram),
              tri: campaign.synthesizedPrefills.tri.map((item) => item.gram),
            }))
            .filter((campaign) => campaign.mono.length + campaign.bi.length + campaign.tri.length > 0),
          campaign_term_reviews: Object.fromEntries(
            fullRun.campaigns.map((campaign) => [
              campaign.campaignName,
              campaign.evaluations.map((evaluation) => ({
                search_term: evaluation.search_term,
                recommendation: evaluation.recommendation,
                confidence: evaluation.confidence,
                reason_tag: evaluation.reason_tag,
              })),
            ]),
          ),
        }),
      });

      if (!response.ok) {
        const detail = await response.json().catch(() => undefined);
        throw new Error(detail?.detail || "AI-prefilled workbook generation failed");
      }

      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const disposition = response.headers.get("content-disposition") || "";
      const match = disposition.match(/filename=\"?([^\";]+)\"?/i);
      const filename =
        match?.[1] || `${selectedProfile.displayName.replace(/\s+/g, "_")}_ai_prefilled_native_ngrams.xlsx`;

      const anchor = document.createElement("a");
      anchor.href = downloadUrl;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(downloadUrl);

      setToast("Full AI-prefilled workbook download started.");
      window.setTimeout(() => setToast(null), 3200);
    } catch (generateError) {
      setAiWorkbookError(
        generateError instanceof Error ? generateError.message : "Full AI-prefilled workbook generation failed",
      );
    } finally {
      setAiWorkbookGenerating(false);
    }
  };

  const handleGenerateAiPreviewWorkbook = async () => {
    if (!canGenerateAiPreviewWorkbook || !selectedProfile || !aiPreviewRunId) return;

    setAiPreviewWorkbookGenerating(true);
    setAiWorkbookError(null);

    try {
      const supabase = getBrowserSupabaseClient();
      const { data } = await supabase.auth.getSession();
      const accessToken = data.session?.access_token;

      if (!accessToken) {
        setAiWorkbookError("Please sign in again.");
        setAiPreviewWorkbookGenerating(false);
        return;
      }

      const response = await fetch(`${BACKEND_URL}/ngram/native-workbook-prefilled`, {
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
          preview_run_id: aiPreviewRunId,
        }),
      });

      if (!response.ok) {
        const detail = await response.json().catch(() => undefined);
        throw new Error(detail?.detail || "Preview workbook generation failed");
      }

      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const disposition = response.headers.get("content-disposition") || "";
      const match = disposition.match(/filename=\"?([^\";]+)\"?/i);
      const filename =
        match?.[1] || `${selectedProfile.displayName.replace(/\s+/g, "_")}_ai_preview_native_ngrams.xlsx`;

      const anchor = document.createElement("a");
      anchor.href = downloadUrl;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(downloadUrl);

      setToast("AI preview workbook download started.");
      window.setTimeout(() => setToast(null), 3200);
    } catch (generateError) {
      setAiWorkbookError(
        generateError instanceof Error ? generateError.message : "Preview workbook generation failed",
      );
    } finally {
      setAiPreviewWorkbookGenerating(false);
    }
  };

  const runAiPreview = async (prefillStrategy: AIPrefillStrategy) => {
    if (!selectedProfile) return;
    if (prefillStrategy === "heuristic_synthesis" && !canRunAiPreview) return;
    if (prefillStrategy === "pure_model_single_campaign" && !canRunPureModelPreview) return;

    const parsedThreshold = Number.parseFloat(spendThreshold);
    if (!Number.isFinite(parsedThreshold) || parsedThreshold < 0) {
      setAiPreviewError("Spend threshold must be a number greater than or equal to 0.");
      return;
    }

    setAiPreviewLoading(true);
    setAiPreviewError(null);
    setAiPreview(null);
    setAiPreviewRunId(null);

    try {
      const response = await fetch("/api/ngram-2/ai-prefill-preview", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          profile_id: selectedProfile.profileId,
          ad_product: selectedProductConfig?.amazonAdsAdProduct,
          date_from: dateFrom,
          date_to: dateTo,
          spend_threshold: parsedThreshold,
          respect_legacy_exclusions: legacyExclusions,
          campaign_names: selectedAiCampaignNames,
          prefill_strategy: prefillStrategy,
        }),
      });

      if (!response.ok) {
        const detail = await response.json().catch(() => undefined);
        throw new Error(detail?.detail || "AI prefill preview failed");
      }

      const payload = (await response.json()) as {
        preview?: AIPrefillPreview;
        preview_run_id?: string | null;
      };
      setAiPreview(payload.preview ?? null);
      setAiPreviewRunId(payload.preview_run_id ?? null);
    } catch (previewError) {
      setAiPreviewError(
        previewError instanceof Error ? previewError.message : "AI prefill preview failed",
      );
    } finally {
      setAiPreviewLoading(false);
    }
  };

  const handleRunAiPreview = async () => runAiPreview("heuristic_synthesis");

  const handleRunPureModelPreview = async () => runAiPreview("pure_model_single_campaign");

  const toggleSelectedAiCampaignName = (campaignName: string) => {
    setSelectedAiCampaignNames((current) =>
      current.includes(campaignName)
        ? current.filter((value) => value !== campaignName)
        : [...current, campaignName],
    );
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

  useEffect(() => {
    if (loading || !selectedProfile?.profileId || dayCount === null) {
      setSummary(null);
      setSummaryError(null);
      setSummaryLoading(false);
      return;
    }

    if (selectedProduct !== "sp") {
      setSummary(null);
      setSummaryError(null);
      setSummaryLoading(false);
      return;
    }

    let cancelled = false;

    const loadSummary = async () => {
      setSummaryLoading(true);
      setSummaryError(null);
      setSummary(null);

      try {
        const supabase = getBrowserSupabaseClient();
        const { data } = await supabase.auth.getSession();
        const accessToken = data.session?.access_token;

        if (!accessToken) {
          throw new Error("Please sign in again.");
        }

        const response = await fetch(`${BACKEND_URL}/ngram/native-summary`, {
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
          throw new Error(detail?.detail || "Native summary failed");
        }

        const payload = (await response.json()) as { summary?: NativeNgramSummary };
        if (!cancelled) {
          setSummary(payload.summary ?? null);
        }
      } catch (loadError) {
        if (!cancelled) {
          setSummary(null);
          setSummaryError(loadError instanceof Error ? loadError.message : "Native summary failed");
        }
      } finally {
        if (!cancelled) {
          setSummaryLoading(false);
        }
      }
    };

    void loadSummary();

    return () => {
      cancelled = true;
    };
  }, [
    loading,
    selectedProfile?.profileId,
    selectedProduct,
    selectedProductConfig?.amazonAdsAdProduct,
    dateFrom,
    dateTo,
    legacyExclusions,
    dayCount,
  ]);

  useEffect(() => {
    setAiPreview(null);
    setAiPreviewRunId(null);
    setAiPreviewError(null);
    setAiWorkbookError(null);
    setSelectedAiCampaignNames([]);
    setAiCampaignQuery("");
  }, [selectedProfile?.profileId, selectedProduct, dateFrom, dateTo, legacyExclusions]);

  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-br from-[#eaf2ff] via-[#dce8ff] to-[#cddcf8]">
      <header className="border-b border-slate-200 bg-white px-6 py-4 shadow-sm">
        <div className="mx-auto flex max-w-6xl flex-wrap items-baseline gap-3">
          <h1 className="text-xl font-bold tracking-tight text-slate-900">N-GRAM 2.0</h1>
          <p className="text-sm text-slate-500">
            Native search-term input for the current workbook flow.
          </p>
        </div>
      </header>

      <div className="flex flex-1 items-start justify-center px-4 pb-16 pt-10">
        <div className="w-full max-w-5xl space-y-10">
          <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)]">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="flex flex-wrap items-center gap-3">
                  <span className="rounded-full border border-[#d8c4a4] bg-[#fff7eb] px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-[#8a5a15]">
                    Experimental
                  </span>
                  <span className="rounded-full border border-[#cad8f7] bg-[#eff5ff] px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-[#2453a6]">
                    Workbook First
                  </span>
                </div>
                <p className="mt-4 max-w-3xl text-sm leading-6 text-[#4c576f]">
                  Replace the old Pacvue export/upload step first. Generate the same practical workbook from native Agency OS data, while the legacy{" "}
                  <Link
                    href="/ngram"
                    className="font-semibold text-[#0a6fd6] underline decoration-[#9abfff] underline-offset-4"
                  >
                    N-Gram Processor
                  </Link>{" "}
                  stays live and untouched.
                </p>
              </div>
              <Link
                href="/ngram"
                className="rounded-full border border-[#c9d8f8] bg-[#eff5ff] px-4 py-2 text-sm font-semibold text-[#2453a6] transition hover:bg-[#e1ecff]"
              >
                Open Classic N-Gram
              </Link>
            </div>
          </div>

          <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)]">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[#94a3b8]">Step 1</p>
              <h2 className="mt-1 text-lg font-semibold text-[#0f172a]">Select native search-term data</h2>
              <p className="text-sm text-[#4c576f]">
                Choose the client, marketplace, ad product, and date range that should feed the workbook.
              </p>
            </div>

            <div className="mt-6 grid gap-5 md:grid-cols-2">
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
              <p className="text-sm font-semibold text-[#1b2430]">Ad product</p>
              <p className="mt-1 text-sm text-[#4c576f]">
                Keep the native flow anchored to the validated Amazon report contract for each ad product.
              </p>

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

            <div className="mt-8">
              <button
                type="button"
                onClick={() => setLegacyExclusions((current) => !current)}
                className={`w-full rounded-2xl border px-4 py-4 text-left transition ${
                  legacyExclusions
                    ? "border-[#c7d9ff] bg-[#eef5ff]"
                    : "border-[#d7dfec] bg-white"
                }`}
              >
                <p className="text-sm font-semibold text-[#1b2430]">Respect legacy exclusions</p>
                <p className="mt-1 text-sm text-[#4c576f]">
                  Exclude campaign names containing <span className="font-semibold text-[#1b2430]">Ex.</span>, <span className="font-semibold text-[#1b2430]">SDI</span>, or <span className="font-semibold text-[#1b2430]">SDV</span> so the native workbook matches the current analyst flow.
                </p>
              </button>
            </div>

            <div className="mt-6 rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-[#0f172a]">Run readiness</p>
                  <p className="mt-1 text-sm text-[#4c576f]">{runState.note}</p>
                </div>
                <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${runStateClasses}`}>
                  {runState.label}
                </span>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <div className="rounded-xl border border-[#dbe4f0] bg-white px-4 py-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7d8ba1]">Range span</p>
                  <p className="mt-2 text-base font-semibold text-[#0f172a]">
                    {dayCount === null ? "Invalid dates" : `${dayCount} day${dayCount === 1 ? "" : "s"}`}
                  </p>
                </div>
                <div className="rounded-xl border border-[#dbe4f0] bg-white px-4 py-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7d8ba1]">Selected lane</p>
                  <p className="mt-2 text-base font-semibold text-[#0f172a]">
                    {selectedProductConfig?.label ?? "Unknown"}
                  </p>
                </div>
                <div className="rounded-xl border border-[#dbe4f0] bg-white px-4 py-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7d8ba1]">Nightly sync</p>
                  <p className="mt-2 text-base font-semibold text-[#0f172a]">
                    {selectedProfile?.nightlyByProduct[selectedProduct] ? "Enabled" : "Manual / on demand"}
                  </p>
                </div>
              </div>
            </div>

            {error ? (
              <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
                {error}
              </p>
            ) : null}

            {failures.length > 0 ? (
              <div className="mt-4 rounded-xl border border-[#f0d9b1] bg-[#fff8ee] px-4 py-3 text-sm text-[#7d5a1d]">
                <p className="font-semibold">Some client summaries failed to load.</p>
                <p className="mt-1">{failures[0]}</p>
              </div>
            ) : null}
          </div>

          <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)]">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[#94a3b8]">Step 2</p>
              <h2 className="mt-1 text-lg font-semibold text-[#0f172a]">Review imported summary</h2>
              <p className="text-sm text-[#4c576f]">
                Check the selected window totals before generating the workbook. Inspect rows only when something looks off.
              </p>
            </div>

            {selectedProduct === "sp" ? (
              <>
                {summaryError ? (
                  <p className="mt-6 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
                    {summaryError}
                  </p>
                ) : null}

                {summaryLoading && !summary ? (
                  <div className="mt-6 rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-5 text-sm text-[#4c576f]">
                    Loading native preflight summary...
                  </div>
                ) : null}

                {summary ? (
                  <>
                    {summary.warnings.length > 0 ? (
                      <div className="mt-6 space-y-3">
                        {summary.warnings.map((warning) => (
                          <div
                            key={warning}
                            className="rounded-xl border border-[#f0d9b1] bg-[#fff8ee] px-4 py-3 text-sm text-[#7d5a1d]"
                          >
                            {warning}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="mt-6 rounded-xl border border-[#c7ebd4] bg-[#edf9f1] px-4 py-3 text-sm text-[#1f6b37]">
                        Selected window looks healthy for native workbook generation.
                      </div>
                    )}

                    <div className="mt-6 grid gap-4 md:grid-cols-2">
                      <div className="rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-4">
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7d8ba1]">Imported totals</p>
                        <div className="mt-3 space-y-2 text-sm text-[#4c576f]">
                          <p>Clicks: <span className="font-semibold text-[#0f172a]">{formatNumber(summary.imported_totals.clicks)}</span></p>
                          <p>Spend: <span className="font-semibold text-[#0f172a]">{formatCurrency(summary.imported_totals.spend, selectedProfile?.currencyCode)}</span></p>
                          <p>Orders: <span className="font-semibold text-[#0f172a]">{formatNumber(summary.imported_totals.orders)}</span></p>
                          <p>Sales: <span className="font-semibold text-[#0f172a]">{formatCurrency(summary.imported_totals.sales, selectedProfile?.currencyCode)}</span></p>
                        </div>
                      </div>
                      <div className="rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-4">
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7d8ba1]">Workbook input</p>
                        <div className="mt-3 space-y-2 text-sm text-[#4c576f]">
                          <p>Eligible rows: <span className="font-semibold text-[#0f172a]">{formatNumber(summary.eligible_rows)}</span></p>
                          <p>Campaigns: <span className="font-semibold text-[#0f172a]">{formatNumber(summary.campaigns_included)}</span></p>
                          <p>Search terms: <span className="font-semibold text-[#0f172a]">{formatNumber(summary.unique_search_terms)}</span></p>
                          <p>Coverage: <span className="font-semibold text-[#0f172a]">{summary.coverage_start ?? "—"} to {summary.coverage_end ?? "—"}</span></p>
                          <p>ASIN rows removed: <span className="font-semibold text-[#0f172a]">{formatNumber(summary.excluded_asin_rows)}</span></p>
                          <p>Legacy skips: <span className="font-semibold text-[#0f172a]">{formatNumber(summary.campaigns_skipped)}</span></p>
                        </div>
                      </div>
                    </div>

                    <div className="mt-6 rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-4">
                      <p className="text-sm font-semibold text-[#0f172a]">Spot-check rows only when needed</p>
                      <p className="mt-1 text-sm text-[#4c576f]">
                        Use the admin Search Term Data view for onboarding, debugging, or investigating a warning. It is not meant to be a required step on every run.
                      </p>
                      {inspectRowsHref ? (
                        <div className="mt-4">
                          <Link
                            href={inspectRowsHref}
                            className="inline-flex rounded-full bg-white px-5 py-2 text-sm font-semibold text-[#0a6fd6] shadow"
                          >
                            Inspect rows
                          </Link>
                        </div>
                      ) : null}
                    </div>
                  </>
                ) : null}
              </>
            ) : (
              <div className="mt-6 space-y-3">
                {validationChecklist.map((item) => (
                  <div key={item} className="rounded-xl border border-[#dbe4f0] bg-[#f7faff] px-4 py-3 text-sm text-[#4c576f]">
                    {item}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)]">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[#94a3b8]">Step 3</p>
              <h2 className="mt-1 text-lg font-semibold text-[#0f172a]">Preview AI prefill</h2>
              <p className="text-sm text-[#4c576f]">
                Optional term-level AI recommendations on the selected native window. This is a review surface only for now, not a direct workbook write.
              </p>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-[220px_1fr]">
              <label className="space-y-2">
                <span className="text-sm font-semibold text-[#1b2430]">Spend threshold</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={spendThreshold}
                  onChange={(event) => setSpendThreshold(event.target.value)}
                  className="w-full rounded-2xl border border-[#d4ddea] bg-white px-4 py-3 text-sm text-[#1b2430] shadow-sm outline-none transition focus:border-[#8bb6ff] focus:ring-4 focus:ring-[#d8e8ff]"
                />
              </label>

              <div className="rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-4">
                <p className="text-sm font-semibold text-[#0f172a]">Per-run filter</p>
                <p className="mt-1 text-sm text-[#4c576f]">
                  Terms below this spend threshold stay untouched. Leave campaign selection empty to use the capped top-spend preview, or pick one or more campaigns to run a cheaper full-term subset pass and export that preview workbook.
                </p>
                <div className="mt-4 flex flex-wrap gap-3">
                  <button
                    type="button"
                    disabled={!canRunAiPreview}
                    onClick={handleRunAiPreview}
                    className="inline-flex rounded-full bg-[#0f172a] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#1e293b] disabled:cursor-not-allowed disabled:bg-[#a8b4c8]"
                  >
                    {aiPreviewLoading ? "Running AI preview…" : "Run Shipped AI Preview"}
                  </button>
                  <button
                    type="button"
                    disabled={!canRunPureModelPreview}
                    onClick={handleRunPureModelPreview}
                    className="inline-flex rounded-full border border-[#b9c9e6] bg-white px-5 py-2.5 text-sm font-semibold text-[#0f172a] transition hover:border-[#8bb6ff] hover:bg-[#eef5ff] disabled:cursor-not-allowed disabled:border-[#d7deea] disabled:text-[#94a3b8]"
                  >
                    {aiPreviewLoading ? "Running pivot preview…" : "Run Pure-Model Pivot Preview"}
                  </button>
                </div>
                <p className="mt-3 text-xs text-[#7d8ba1]">
                  Pure-model pivot preview currently requires exactly one selected campaign and keeps Step 4 full workbook generation on the shipped heuristic path.
                </p>
              </div>
            </div>

            {summary?.campaigns?.length ? (
              <div className="mt-4 rounded-2xl border border-[#dbe4f0] bg-[#fbfdff] p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-[#0f172a]">Optional campaign subset</p>
                    <p className="mt-1 text-sm text-[#4c576f]">
                      Pick campaign(s) to bypass the preview caps and evaluate all eligible terms for just those lanes.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setSelectedAiCampaignNames([])}
                    disabled={selectedAiCampaignNames.length === 0}
                    className="rounded-full border border-[#cbd5e1] bg-white px-3 py-1.5 text-xs font-semibold text-[#334155] transition hover:border-[#94a3b8] disabled:cursor-not-allowed disabled:text-[#94a3b8]"
                  >
                    Clear selection
                  </button>
                </div>

                <div className="mt-4 grid gap-4 md:grid-cols-[280px_1fr]">
                  <label className="space-y-2">
                    <span className="text-sm font-semibold text-[#1b2430]">Search campaigns</span>
                    <input
                      type="text"
                      value={aiCampaignQuery}
                      onChange={(event) => setAiCampaignQuery(event.target.value)}
                      placeholder="Filter by campaign name"
                      className="w-full rounded-2xl border border-[#d4ddea] bg-white px-4 py-3 text-sm text-[#1b2430] shadow-sm outline-none transition focus:border-[#8bb6ff] focus:ring-4 focus:ring-[#d8e8ff]"
                    />
                    <p className="text-xs text-[#7d8ba1]">
                      {hasSelectedAiCampaignSubset
                        ? `${formatNumber(selectedAiCampaignNames.length)} selected for a full-term subset preview${selectedAiCampaignNames.length === 1 ? " or pure-model pivot preview" : ""}`
                        : "No selection: preview stays on the capped top-spend auto slice"}
                    </p>
                  </label>

                  <div className="rounded-2xl border border-[#dbe4f0] bg-white p-2">
                    <div className="max-h-64 space-y-2 overflow-y-auto px-2 py-1">
                      {filteredCampaignOptions.length > 0 ? (
                        filteredCampaignOptions.map((campaign) => {
                          const checked = selectedAiCampaignNames.includes(campaign.campaign_name);
                          return (
                            <label
                              key={campaign.campaign_name}
                              className={`flex cursor-pointer items-start gap-3 rounded-2xl border px-3 py-3 transition ${
                                checked
                                  ? "border-[#8bb6ff] bg-[#eef5ff]"
                                  : "border-[#e2e8f0] bg-[#fbfdff] hover:border-[#cbd5e1]"
                              }`}
                            >
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() => toggleSelectedAiCampaignName(campaign.campaign_name)}
                                className="mt-1 h-4 w-4 rounded border-[#94a3b8] text-[#0a6fd6] focus:ring-[#bfdbfe]"
                              />
                              <span className="min-w-0 flex-1">
                                <span className="block text-sm font-semibold text-[#0f172a]">{campaign.campaign_name}</span>
                                <span className="mt-1 block text-xs text-[#64748b]">
                                  {formatCurrency(campaign.spend, selectedProfile?.currencyCode)} spend • {formatNumber(campaign.search_terms)} search terms
                                </span>
                              </span>
                            </label>
                          );
                        })
                      ) : (
                        <p className="px-2 py-3 text-sm text-[#64748b]">No campaigns matched the current filter.</p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ) : null}

            {aiPreviewError ? (
              <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
                {aiPreviewError}
              </p>
            ) : null}

            {aiPreview ? (
              <>
                {aiPreview.warnings.length > 0 ? (
                  <div className="mt-6 space-y-3">
                    {aiPreview.warnings.map((warning) => (
                      <div
                        key={warning}
                        className="rounded-xl border border-[#f0d9b1] bg-[#fff8ee] px-4 py-3 text-sm text-[#7d5a1d]"
                      >
                        {warning}
                      </div>
                    ))}
                  </div>
                ) : null}

                <div className="mt-6 grid gap-4 md:grid-cols-4">
                  <div className="rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7d8ba1]">Campaigns</p>
                    <p className="mt-2 text-lg font-semibold text-[#0f172a]">{formatNumber(aiPreview.preview_campaigns)}</p>
                    <p className="mt-1 text-xs text-[#7d8ba1]">from {formatNumber(aiPreview.candidate_campaigns)} eligible</p>
                  </div>
                  <div className="rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7d8ba1]">Recommendations</p>
                    <p className="mt-2 text-lg font-semibold text-[#0f172a]">{formatNumber(aiPreview.recommendation_counts.negate)}</p>
                    <p className="mt-1 text-xs text-[#7d8ba1]">negate calls</p>
                  </div>
                  <div className="rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7d8ba1]">Review</p>
                    <p className="mt-2 text-lg font-semibold text-[#0f172a]">{formatNumber(aiPreview.recommendation_counts.review)}</p>
                    <p className="mt-1 text-xs text-[#7d8ba1]">manual checks</p>
                  </div>
                  <div className="rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7d8ba1]">Model</p>
                    <p className="mt-2 text-sm font-semibold text-[#0f172a]">{aiPreview.model ?? "n/a"}</p>
                    <p className="mt-1 text-xs text-[#7d8ba1]">
                      {aiPreview.prefill_strategy === "pure_model_single_campaign" ? "pure-model pivot" : "shipped heuristic"} • threshold {formatCurrency(aiPreview.spend_threshold, selectedProfile?.currencyCode)}
                    </p>
                  </div>
                </div>

                <div className="mt-4 grid gap-4 md:grid-cols-3">
                  <div className="rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7d8ba1]">
                      {aiPreview.prefill_strategy === "pure_model_single_campaign" ? "Model exact" : "Synthesized mono"}
                    </p>
                    <p className="mt-2 text-lg font-semibold text-[#0f172a]">
                      {formatNumber(
                        aiPreview.prefill_strategy === "pure_model_single_campaign"
                          ? aiExactPrefillCount
                          : aiScratchpadCounts.mono,
                      )}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7d8ba1]">
                      {aiPreview.prefill_strategy === "pure_model_single_campaign" ? "Model phrase" : "Synthesized bi"}
                    </p>
                    <p className="mt-2 text-lg font-semibold text-[#0f172a]">
                      {formatNumber(
                        aiPreview.prefill_strategy === "pure_model_single_campaign"
                          ? aiScratchpadCounts.mono + aiScratchpadCounts.bi + aiScratchpadCounts.tri
                          : aiScratchpadCounts.bi,
                      )}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7d8ba1]">
                      {aiPreview.prefill_strategy === "pure_model_single_campaign" ? "Phrase buckets" : "Synthesized tri"}
                    </p>
                    <p className="mt-2 text-lg font-semibold text-[#0f172a]">
                      {formatNumber(
                        aiPreview.prefill_strategy === "pure_model_single_campaign"
                          ? aiScratchpadCounts.mono + aiScratchpadCounts.bi + aiScratchpadCounts.tri
                          : aiScratchpadCounts.tri,
                      )}
                    </p>
                  </div>
                </div>

                <button
                  type="button"
                  disabled={!canGenerateAiPreviewWorkbook}
                  onClick={handleGenerateAiPreviewWorkbook}
                  className="mt-4 inline-flex rounded-full bg-[#0f172a] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#1e293b] disabled:cursor-not-allowed disabled:bg-[#a8b4c8]"
                >
                  {aiPreviewWorkbookGenerating ? "Generating preview workbook…" : "Download AI Preview Workbook"}
                </button>

                <div className="mt-6 space-y-4">
                  {aiPreview.campaigns.map((campaign) => (
                    <div key={campaign.campaignName} className="rounded-2xl border border-[#dbe4f0] bg-[#fbfdff] p-5">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="text-base font-semibold text-[#0f172a]">{campaign.campaignName}</p>
                          <p className="mt-1 text-sm text-[#4c576f]">
                            {campaign.matchedTitle
                              ? `${campaign.matchedTitle}${campaign.theme ? ` • theme: ${campaign.theme}` : ""}${campaign.matchSource === "ai_combined" ? " • AI matched" : ""}`
                              : campaign.matchStatus === "intentionally_skipped"
                                ? "Intentionally skipped campaign (brand / mix / defensive)."
                                : "AI could not confidently identify a single product."}
                          </p>
                        </div>
                        <div className="rounded-full border border-[#dbe4f0] bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-[#64748b]">
                          {campaign.prefillStrategy === "pure_model_single_campaign" ? "pure-model" : "heuristic"} •{" "}
                          {campaign.matchStatus === "matched"
                            ? campaign.matchSource === "ai_combined"
                              ? "ai match"
                              : "matched"
                            : campaign.matchStatus === "intentionally_skipped"
                              ? "skipped"
                              : "ambiguous"}
                        </div>
                      </div>

                      <div className="mt-4 grid gap-3 md:grid-cols-4">
                        <div className="rounded-xl border border-[#e3ebf6] bg-white px-4 py-3 text-sm text-[#4c576f]">
                          Eligible spend: <span className="font-semibold text-[#0f172a]">{formatCurrency(campaign.eligibleSpend, selectedProfile?.currencyCode)}</span>
                        </div>
                        <div className="rounded-xl border border-[#e3ebf6] bg-white px-4 py-3 text-sm text-[#4c576f]">
                          Terms above threshold: <span className="font-semibold text-[#0f172a]">{formatNumber(campaign.eligibleTerms)}</span>
                        </div>
                        <div className="rounded-xl border border-[#e3ebf6] bg-white px-4 py-3 text-sm text-[#4c576f]">
                          Skipped below threshold: <span className="font-semibold text-[#0f172a]">{formatNumber(campaign.skippedBelowThresholdTerms)}</span>
                        </div>
                        <div className="rounded-xl border border-[#e3ebf6] bg-white px-4 py-3 text-sm text-[#4c576f]">
                          Identifier: <span className="font-semibold text-[#0f172a]">{campaign.productIdentifier ?? "—"}</span>
                        </div>
                      </div>

                      {campaign.evaluations.length > 0 ? (
                        <div className="mt-4 space-y-3">
                          {campaign.evaluations.map((evaluation) => {
                            const pillClasses =
                              evaluation.recommendation === "NEGATE"
                                ? "border-[#f3c1c1] bg-[#fff3f3] text-[#991b1b]"
                                : evaluation.recommendation === "KEEP"
                                  ? "border-[#c7ebd4] bg-[#edf9f1] text-[#1f6b37]"
                                  : "border-[#f0d9b1] bg-[#fff8ee] text-[#7d5a1d]";
                            return (
                              <div key={evaluation.search_term} className="rounded-xl border border-[#e3ebf6] bg-white px-4 py-3">
                                <div className="flex flex-wrap items-start justify-between gap-3">
                                  <div>
                                    <p className="text-sm font-semibold text-[#0f172a]">{evaluation.search_term}</p>
                                    <p className="mt-1 text-xs text-[#64748b]">
                                      Spend {formatCurrency(evaluation.spend, selectedProfile?.currencyCode)} • Clicks {formatNumber(evaluation.clicks)} • Orders {formatNumber(evaluation.orders)}
                                    </p>
                                  </div>
                                  <div className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${pillClasses}`}>
                                    {evaluation.recommendation} • {evaluation.confidence}
                                  </div>
                                </div>
                                <p className="mt-2 text-sm text-[#334155]">
                                  <span className="font-semibold text-[#0f172a]">{evaluation.reason_tag}</span>
                                  {evaluation.rationale ? ` • ${evaluation.rationale}` : ""}
                                </p>
                              </div>
                            );
                          })}
                        </div>
                      ) : null}

                      {campaign.prefillStrategy === "pure_model_single_campaign" &&
                      campaign.modelPrefills.exact.length +
                        campaign.modelPrefills.mono.length +
                        campaign.modelPrefills.bi.length +
                        campaign.modelPrefills.tri.length >
                        0 ? (
                        <div className="mt-4 rounded-xl border border-[#dbe4f0] bg-[#f7faff] p-4">
                          <p className="text-sm font-semibold text-[#0f172a]">Pure-model prefills</p>
                          <div className="mt-2 space-y-2 text-sm text-[#4c576f]">
                            {campaign.modelPrefills.exact.length > 0 ? (
                              <p>
                                Exact: <span className="font-semibold text-[#0f172a]">{campaign.modelPrefills.exact.join(", ")}</span>
                              </p>
                            ) : null}
                            {campaign.modelPrefills.mono.length > 0 ? (
                              <p>
                                Mono: <span className="font-semibold text-[#0f172a]">{campaign.modelPrefills.mono.join(", ")}</span>
                              </p>
                            ) : null}
                            {campaign.modelPrefills.bi.length > 0 ? (
                              <p>
                                Bi: <span className="font-semibold text-[#0f172a]">{campaign.modelPrefills.bi.join(", ")}</span>
                              </p>
                            ) : null}
                            {campaign.modelPrefills.tri.length > 0 ? (
                              <p>
                                Tri: <span className="font-semibold text-[#0f172a]">{campaign.modelPrefills.tri.join(", ")}</span>
                              </p>
                            ) : null}
                          </div>
                          {campaign.phraseNegatives.length > 0 ? (
                            <div className="mt-3 space-y-2">
                              {campaign.phraseNegatives.map((phrase) => (
                                <div key={`${campaign.campaignName}-${phrase.bucket}-${phrase.phrase}`} className="rounded-lg border border-[#e3ebf6] bg-white px-3 py-2 text-sm text-[#334155]">
                                  <span className="font-semibold text-[#0f172a]">{phrase.bucket}</span>: {phrase.phrase} • {phrase.confidence}
                                  {phrase.sourceTerms.length > 0 ? ` • from ${phrase.sourceTerms.join(", ")}` : ""}
                                  {phrase.rationale ? ` • ${phrase.rationale}` : ""}
                                </div>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      ) : null}

                      {campaign.prefillStrategy !== "pure_model_single_campaign" &&
                      campaign.synthesizedPrefills.mono.length +
                        campaign.synthesizedPrefills.bi.length +
                        campaign.synthesizedPrefills.tri.length >
                        0 ? (
                        <div className="mt-4 rounded-xl border border-[#dbe4f0] bg-[#f7faff] p-4">
                          <p className="text-sm font-semibold text-[#0f172a]">Synthesized scratchpad</p>
                          <div className="mt-2 space-y-2 text-sm text-[#4c576f]">
                            {campaign.synthesizedPrefills.mono.length > 0 ? (
                              <p>
                                Mono: <span className="font-semibold text-[#0f172a]">{campaign.synthesizedPrefills.mono.map((item) => item.gram).join(", ")}</span>
                              </p>
                            ) : null}
                            {campaign.synthesizedPrefills.bi.length > 0 ? (
                              <p>
                                Bi: <span className="font-semibold text-[#0f172a]">{campaign.synthesizedPrefills.bi.map((item) => item.gram).join(", ")}</span>
                              </p>
                            ) : null}
                            {campaign.synthesizedPrefills.tri.length > 0 ? (
                              <p>
                                Tri: <span className="font-semibold text-[#0f172a]">{campaign.synthesizedPrefills.tri.map((item) => item.gram).join(", ")}</span>
                              </p>
                            ) : null}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </>
            ) : null}
          </div>

          <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)]">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[#94a3b8]">Step 4</p>
              <h2 className="mt-1 text-lg font-semibold text-[#0f172a]">Generate the native workbook</h2>
              <p className="text-sm text-[#4c576f]">
                Produce the familiar mono/bi/tri workbook from native data so the current analyst and manager review flow stays intact.
              </p>
              <p className="mt-1 text-xs text-[#94a3b8]">
                Preview stays capped and cheap; the AI workbook button below runs the full uncapped AI pass for the selected window and threshold.
              </p>
            </div>

            <button
              type="button"
              disabled={!canGenerateWorkbook}
              onClick={handleGenerateWorkbook}
              className="mt-6 w-full rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-[#b7cbea]"
            >
              {workbookGenerating ? "Generating workbook…" : "Generate Native Workbook"}
            </button>

            <button
              type="button"
              disabled={!canGenerateAiWorkbook}
              onClick={handleGenerateAiWorkbook}
              className="mt-4 w-full rounded-2xl bg-[#0f172a] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(15,23,42,0.24)] transition hover:bg-[#1e293b] disabled:cursor-not-allowed disabled:bg-[#b8c1d1]"
            >
              {aiWorkbookGenerating ? "Running full AI + generating workbook…" : "Generate Full AI-Prefilled Workbook"}
            </button>

            <div className="mt-4 rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-4">
              <p className="text-sm text-[#4c576f]">
                {selectedProduct === "sp"
                  ? "Uses native Sponsored Products search-term facts for the selected window and keeps the legacy exclusion rules. The AI button runs the full uncapped AI evaluation, then writes workbook prefills from that saved run."
                  : "Workbook generation is intentionally limited to Sponsored Products first."}
              </p>
            </div>

            {workbookError ? (
              <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
                {workbookError}
              </p>
            ) : null}

            {aiWorkbookError ? (
              <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
                {aiWorkbookError}
              </p>
            ) : null}
          </div>

          {loading ? (
            <p className="text-sm text-[#4c576f]">Loading client and marketplace options…</p>
          ) : null}
        </div>
      </div>

      {toast ? (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-full bg-[#0a6fd6] px-6 py-3 text-sm font-semibold text-white shadow-lg">
          {toast}
        </div>
      ) : null}
    </div>
  );
}
