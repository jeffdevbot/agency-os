"use client";

import Link from "next/link";
import { startTransition, useEffect, useRef, useState } from "react";

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
const AI_PREVIEW_RESULT_LIMIT = 10;
const ACTIVITY_LINE_LIMIT = 18;

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
    mono: Array<{
      gram: string;
      supportTerms: string[];
      negateCount: number;
      keepCount: number;
      reviewCount: number;
      negateSpend: number;
      weightedScore: number;
    }>;
    bi: Array<{
      gram: string;
      supportTerms: string[];
      negateCount: number;
      keepCount: number;
      reviewCount: number;
      negateSpend: number;
      weightedScore: number;
    }>;
    tri: Array<{
      gram: string;
      supportTerms: string[];
      negateCount: number;
      keepCount: number;
      reviewCount: number;
      negateSpend: number;
      weightedScore: number;
    }>;
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

type ActivityMode = "preview" | "full_workbook" | "preview_workbook";

const formatNumber = (value: number): string => value.toLocaleString();

const formatCurrency = (value: number, currencyCode: string | null | undefined): string =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currencyCode ?? "USD",
    minimumFractionDigits: 2,
  }).format(value);

const parseAttachmentFilename = (response: Response, fallback: string): string => {
  const disposition = response.headers.get("Content-Disposition") || response.headers.get("content-disposition");
  if (!disposition) return fallback;
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1]);
  }
  const plainMatch = disposition.match(/filename="?([^";]+)"?/i);
  return plainMatch?.[1] || fallback;
};

const formatRecommendationLabel = (
  recommendation: AIPrefillRecommendation["recommendation"],
): string => {
  if (recommendation === "NEGATE") return "LIKELY NEGATE";
  if (recommendation === "KEEP") return "SAFE KEEP";
  return "REVIEW";
};

const formatReasonTag = (reasonTag: string): string =>
  reasonTag
    .split("_")
    .filter(Boolean)
    .map((part) => `${part.slice(0, 1).toUpperCase()}${part.slice(1)}`)
    .join(" ");

const sortPreviewEvaluations = (
  evaluations: AIPrefillRecommendation[],
): AIPrefillRecommendation[] => {
  const recommendationRank: Record<AIPrefillRecommendation["recommendation"], number> = {
    NEGATE: 0,
    REVIEW: 1,
    KEEP: 2,
  };

  return [...evaluations].sort((left, right) => {
    const recommendationDiff =
      recommendationRank[left.recommendation] - recommendationRank[right.recommendation];
    if (recommendationDiff !== 0) return recommendationDiff;
    if (right.spend !== left.spend) return right.spend - left.spend;
    return left.search_term.localeCompare(right.search_term);
  });
};

export default function NgramTwoPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [failures, setFailures] = useState<string[]>([]);
  const [summaries, setSummaries] = useState<ClientProfileSummary[]>([]);
  const [selectedClientId, setSelectedClientId] = useState("");
  const [selectedProfileId, setSelectedProfileId] = useState("");
  const [selectedProduct, setSelectedProduct] = useState<SearchTermAdProductKey>("sp");
  const [dateFrom, setDateFrom] = useState(defaultDates.from);
  const [dateTo, setDateTo] = useState(defaultDates.to);
  const [legacyExclusions, setLegacyExclusions] = useState(true);
  const [aiWorkbookGenerating, setAiWorkbookGenerating] = useState(false);
  const [aiWorkbookError, setAiWorkbookError] = useState<string | null>(null);
  const [aiPreviewWorkbookGenerating, setAiPreviewWorkbookGenerating] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [summary, setSummary] = useState<NativeNgramSummary | null>(null);
  const [spendThreshold, setSpendThreshold] = useState("0.00");
  const [aiCampaignQuery, setAiCampaignQuery] = useState("");
  const [selectedAiCampaignNames, setSelectedAiCampaignNames] = useState<string[]>([]);
  const [aiPreviewLoading, setAiPreviewLoading] = useState(false);
  const [aiPreviewError, setAiPreviewError] = useState<string | null>(null);
  const [aiPreview, setAiPreview] = useState<AIPrefillPreview | null>(null);
  const [aiPreviewRunId, setAiPreviewRunId] = useState<string | null>(null);
  const [selectedFilledWorkbook, setSelectedFilledWorkbook] = useState<File | null>(null);
  const [collectingNegatives, setCollectingNegatives] = useState(false);
  const [collectError, setCollectError] = useState<string | null>(null);
  const [expandedPreviewRows, setExpandedPreviewRows] = useState<Record<string, number>>({});
  const [activityLines, setActivityLines] = useState<string[]>([]);
  const [activityMode, setActivityMode] = useState<ActivityMode | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const activityScrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const supabase = getBrowserSupabaseClient();

    const load = async () => {
      setLoading(true);
      setError(null);

      try {
        const { data } = await supabase.auth.getSession();
        const accessToken = data.session?.access_token;

        if (!accessToken) {
          setError("Sign in first to load N-Gram 2.0.");
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
        setError(loadError instanceof Error ? loadError.message : "Failed to load N-Gram 2.0.");
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
  const activeClientSummary = summaries.find((summaryRow) => summaryRow.client.id === activeClientId) ?? null;
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
  const hasSelectedAiCampaignSubset = selectedAiCampaignNames.length > 0;
  const canGenerateWorkbook =
    !loading &&
    !aiWorkbookGenerating &&
    selectedProduct === "sp" &&
    runState.tone === "ready" &&
    Boolean(selectedProfile?.profileId) &&
    dayCount !== null &&
    !summaryLoading &&
    !summaryError &&
    summaryAllowsWorkbook;
  const canRunPreviewBase =
    !loading &&
    !aiPreviewLoading &&
    selectedProduct === "sp" &&
    runState.tone === "ready" &&
    Boolean(selectedProfile?.profileId) &&
    dayCount !== null &&
    !summaryLoading &&
    !summaryError &&
    summaryAllowsWorkbook;
  const canGenerateAiWorkbook = canGenerateWorkbook && !aiWorkbookGenerating;
  const canGenerateAiPreviewWorkbook =
    canGenerateWorkbook &&
    !aiPreviewWorkbookGenerating &&
    Boolean(aiPreviewRunId) &&
    Boolean(selectedProfile?.profileId);
  const canRunPureModelPreview = canRunPreviewBase && hasSelectedAiCampaignSubset;
  const canCollectNegatives = Boolean(selectedFilledWorkbook) && !collectingNegatives;
  const filteredCampaignOptions = (summary?.campaigns ?? [])
    .filter((campaign) =>
      aiCampaignQuery.trim()
        ? campaign.campaign_name.toLowerCase().includes(aiCampaignQuery.trim().toLowerCase())
        : true,
    )
    .slice(0, 24);
  const statusToneClasses =
    runState.tone === "ready"
      ? "border-[#c7ebd4] bg-[#edf9f1] text-[#1f6b37]"
      : runState.tone === "caution"
        ? "border-[#f0d9b1] bg-[#fff8ee] text-[#8a5a15]"
        : "border-[#f3d0d0] bg-[#fff5f5] text-[#8f1d1d]";
  const campaignExclusionHelper = legacyExclusions
    ? "Campaign names containing Ex., SDI, or SDV will be skipped."
    : "All campaign names in the selected window will be included.";

  const appendActivity = (line: string) => {
    setActivityLines((current) => [...current.slice(-(ACTIVITY_LINE_LIMIT - 1)), line]);
  };

  const startActivity = (mode: ActivityMode, initialLines: string[]) => {
    setActivityMode(mode);
    setActivityLines(initialLines);
  };

  const finishActivity = (finalLine?: string) => {
    setActivityMode(null);
    if (finalLine) {
      appendActivity(finalLine);
    }
  };

  const handleGenerateAiWorkbook = async () => {
    if (!canGenerateWorkbook || !selectedProfile) return;

    const parsedThreshold = Number.parseFloat(spendThreshold);
    if (!Number.isFinite(parsedThreshold) || parsedThreshold < 0) {
      setAiWorkbookError("Spend threshold must be a number greater than or equal to 0.");
      return;
    }

    setAiWorkbookGenerating(true);
    setAiWorkbookError(null);
    startActivity("full_workbook", [
      "Loading search-term data",
      "Preparing campaign set",
      "Running AI context pass",
    ]);

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

      appendActivity("Running AI term analysis");
      appendActivity("Saving AI run");

      const supabase = getBrowserSupabaseClient();
      const { data } = await supabase.auth.getSession();
      const accessToken = data.session?.access_token;

      if (!accessToken) {
        setAiWorkbookError("Please sign in again.");
        setAiWorkbookGenerating(false);
        return;
      }

      appendActivity("Preparing workbook");
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
                rationale: evaluation.rationale,
              })),
            ]),
          ),
        }),
      });

      if (!response.ok) {
        const detail = await response.json().catch(() => undefined);
        throw new Error(detail?.detail || "AI review workbook generation failed");
      }

      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const disposition = response.headers.get("content-disposition") || "";
      const match = disposition.match(/filename=\"?([^\";]+)\"?/i);
      const filename =
        match?.[1] || `${selectedProfile.displayName.replace(/\s+/g, "_")}_ai_review_native_ngrams.xlsx`;

      const anchor = document.createElement("a");
      anchor.href = downloadUrl;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(downloadUrl);

      finishActivity("Done");
      setToast("Full AI review workbook download started.");
      window.setTimeout(() => setToast(null), 3200);
    } catch (generateError) {
      finishActivity("AI workbook run failed");
      setAiWorkbookError(
        generateError instanceof Error ? generateError.message : "Full AI review workbook generation failed",
      );
    } finally {
      setAiWorkbookGenerating(false);
    }
  };

  const handleGenerateAiPreviewWorkbook = async () => {
    if (!canGenerateAiPreviewWorkbook || !selectedProfile || !aiPreviewRunId) return;

    setAiPreviewWorkbookGenerating(true);
    setAiWorkbookError(null);
    startActivity("preview_workbook", [
      "Preparing preview workbook",
      "Loading saved preview run",
      "Preparing workbook download",
    ]);

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

      finishActivity("Done");
      setToast("Preview workbook download started.");
      window.setTimeout(() => setToast(null), 3200);
    } catch (generateError) {
      finishActivity("Preview workbook run failed");
      setAiWorkbookError(
        generateError instanceof Error ? generateError.message : "Preview workbook generation failed",
      );
    } finally {
      setAiPreviewWorkbookGenerating(false);
    }
  };

  const handleFilledWorkbookChange = (file: File | null) => {
    setSelectedFilledWorkbook(file);
    setCollectError(null);
  };

  const handleFilledWorkbookDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const file = event.dataTransfer.files[0] ?? null;
    handleFilledWorkbookChange(file);
  };

  const handleCollectNegatives = async () => {
    if (!selectedFilledWorkbook || collectingNegatives) return;

    setCollectingNegatives(true);
    setCollectError(null);
    startActivity("preview_workbook", [
      "Uploading reviewed workbook",
      "Reading analyst selections",
      "Preparing negatives summary",
    ]);

    try {
      const supabase = getBrowserSupabaseClient();
      const { data } = await supabase.auth.getSession();
      const accessToken = data.session?.access_token;

      if (!accessToken) {
        setCollectError("Please sign in again.");
        setCollectingNegatives(false);
        return;
      }

      const formData = new FormData();
      formData.append("file", selectedFilledWorkbook);

      const response = await fetch(`${BACKEND_URL}/ngram/collect`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const detail = await response.json().catch(() => undefined);
        throw new Error(detail?.detail || "Failed to collect negatives");
      }

      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const filename = parseAttachmentFilename(
        response,
        `${selectedFilledWorkbook.name.replace(/\.[^.]+$/, "")}_negatives.xlsx`,
      );

      const anchor = document.createElement("a");
      anchor.href = downloadUrl;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(downloadUrl);

      finishActivity("Done");
      setToast("Negatives summary download started.");
      window.setTimeout(() => setToast(null), 3200);
    } catch (collectNegativesError) {
      finishActivity("Negatives summary failed");
      setCollectError(
        collectNegativesError instanceof Error
          ? collectNegativesError.message
          : "Failed to collect negatives",
      );
    } finally {
      setCollectingNegatives(false);
    }
  };

  const handleRunPureModelPreview = async () => {
    if (!selectedProfile || !canRunPureModelPreview) return;

    const parsedThreshold = Number.parseFloat(spendThreshold);
    if (!Number.isFinite(parsedThreshold) || parsedThreshold < 0) {
      setAiPreviewError("Spend threshold must be a number greater than or equal to 0.");
      return;
    }

    setAiPreviewLoading(true);
    setAiPreviewError(null);
    setAiPreview(null);
    setAiPreviewRunId(null);
    startActivity("preview", [
      "Loading search-term data",
      "Preparing campaign preview",
      "Running AI analysis",
    ]);

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
          prefill_strategy: "pure_model_single_campaign",
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
      appendActivity("Saving preview run");
      setAiPreview(payload.preview ?? null);
      setAiPreviewRunId(payload.preview_run_id ?? null);
      finishActivity("Done");
    } catch (previewError) {
      finishActivity("Preview failed");
      setAiPreviewError(
        previewError instanceof Error ? previewError.message : "AI prefill preview failed",
      );
    } finally {
      setAiPreviewLoading(false);
    }
  };

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
          throw new Error(detail?.detail || "Data summary failed");
        }

        const payload = (await response.json()) as { summary?: NativeNgramSummary };
        if (!cancelled) {
          setSummary(payload.summary ?? null);
        }
      } catch (loadError) {
        if (!cancelled) {
          setSummary(null);
          setSummaryError(loadError instanceof Error ? loadError.message : "Data summary failed");
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
    setExpandedPreviewRows({});
    setAiPreviewError(null);
    setAiWorkbookError(null);
    setSelectedFilledWorkbook(null);
    setCollectError(null);
    setSelectedAiCampaignNames([]);
    setAiCampaignQuery("");
    setActivityLines([]);
    setActivityMode(null);
  }, [selectedProfile?.profileId, selectedProduct, dateFrom, dateTo, legacyExclusions]);

  useEffect(() => {
    if (!activityMode) return;

    const waitingScripts: Record<ActivityMode, string[]> = {
      preview: [
        "Checking campaign context",
        "Reviewing above-threshold terms",
        "Waiting for preview response",
        "Still generating AI recommendations",
        "Preparing saved preview payload",
      ],
      full_workbook: [
        "Checking campaign context",
        "Reviewing above-threshold terms",
        "Waiting for AI campaign results",
        "Building review workbook rows",
        "Finalizing workbook payload",
      ],
      preview_workbook: [
        "Checking saved preview payload",
        "Mapping AI review rows",
        "Preparing workbook file",
        "Waiting for download payload",
      ],
    };

    let scriptIndex = 0;
    const script = waitingScripts[activityMode];
    const intervalId = window.setInterval(() => {
      appendActivity(script[scriptIndex % script.length] ?? "Working…");
      scriptIndex += 1;
    }, 900);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [activityMode]);

  useEffect(() => {
    const element = activityScrollRef.current;
    if (!element) return;
    element.scrollTop = element.scrollHeight;
  }, [activityLines]);

  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-br from-[#eaf2ff] via-[#dce8ff] to-[#cddcf8]">
      <header className="border-b border-slate-200 bg-white px-6 py-4 shadow-sm">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900">N-GRAM 2.0</h1>
            <p className="text-sm text-slate-500">
              Build an N-Gram workbook from Agency OS search-term data.
            </p>
          </div>
          <Link
            href="/ngram"
            className="rounded-full border border-[#c9d8f8] bg-[#eff5ff] px-4 py-2 text-sm font-semibold text-[#2453a6] transition hover:bg-[#e1ecff]"
          >
            Open Classic N-Gram
          </Link>
        </div>
      </header>

      <div className="flex flex-1 items-start justify-center px-4 pb-16 pt-10">
        <div className="w-full max-w-5xl space-y-10">
          <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)]">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[#94a3b8]">Step 1</p>
              <h2 className="mt-1 text-lg font-semibold text-[#0f172a]">
                Choose Account, Marketplace, Date Range, and Ad Type
              </h2>
              <p className="text-sm text-[#4c576f]">
                Choose the search-term window that should feed the workbook and the AI review pass.
              </p>
            </div>

            <div className="mt-6 grid gap-5 md:grid-cols-2">
              <label className="space-y-2">
                <span className="text-sm font-semibold text-[#1b2430]">Client</span>
                <select
                  value={activeClientId}
                  onChange={(event) => setSelectedClientId(event.target.value)}
                  disabled={loading}
                  className="w-full rounded-2xl border border-[#d4ddea] bg-white px-4 py-3 text-sm text-[#1b2430] shadow-sm outline-none transition focus:border-[#8bb6ff] focus:ring-4 focus:ring-[#d8e8ff]"
                >
                  {loading ? <option value="">Loading clients…</option> : null}
                  {!loading && clientOptions.length === 0 ? (
                    <option value="">No clients available</option>
                  ) : null}
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
                  disabled={loading}
                  className="w-full rounded-2xl border border-[#d4ddea] bg-white px-4 py-3 text-sm text-[#1b2430] shadow-sm outline-none transition focus:border-[#8bb6ff] focus:ring-4 focus:ring-[#d8e8ff]"
                >
                  {loading ? <option value="">Loading marketplaces…</option> : null}
                  {!loading && profileOptions.length === 0 ? (
                    <option value="">No marketplaces available</option>
                  ) : null}
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

            <p className="mt-3 text-xs text-[#7d8ba1]">
              Missing a client or marketplace? Contact the admin (Jeff) to have it added.
            </p>

            <div className="mt-8">
              <p className="text-sm font-semibold text-[#1b2430]">Ad type</p>

              <div className="mt-4 grid gap-4 lg:grid-cols-3">
                {ACTIVE_SEARCH_TERM_AD_PRODUCTS.map((product) => {
                  const selected = selectedProduct === product.key;
                  const statusLabel = product.key === "sb" ? "live" : product.status;

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
                            statusLabel === "live"
                              ? "bg-[#eaf7ee] text-[#1c7a3b]"
                              : "bg-[#fff2df] text-[#9c6b1f]"
                          }`}
                        >
                          {statusLabel}
                        </span>
                      </div>
                      <p className="mt-4 text-sm leading-6 text-[#526074]">{product.summary}</p>
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
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-8 grid gap-4 md:grid-cols-[1fr_280px]">
              <button
                type="button"
                onClick={() => setLegacyExclusions((current) => !current)}
                className={`rounded-2xl border px-4 py-4 text-left transition ${
                  legacyExclusions ? "border-[#c7d9ff] bg-[#eef5ff]" : "border-[#d7dfec] bg-white"
                }`}
              >
                <p className="text-sm font-semibold text-[#1b2430]">Campaign exclusions</p>
                <p className="mt-1 text-sm text-[#4c576f]">{campaignExclusionHelper}</p>
              </button>

              <label className="space-y-2">
                <span className="text-sm font-semibold text-[#1b2430]">Minimum Spend per Search Term</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={spendThreshold}
                  onChange={(event) => setSpendThreshold(event.target.value)}
                  className="w-full rounded-2xl border border-[#d4ddea] bg-white px-4 py-3 text-sm text-[#1b2430] shadow-sm outline-none transition focus:border-[#8bb6ff] focus:ring-4 focus:ring-[#d8e8ff]"
                />
                <p className="text-xs text-[#7d8ba1]">
                  AI review only looks at terms at or above this spend.
                </p>
              </label>
            </div>

            {selectedProfile && dayCount !== null ? (
              <div className={`mt-4 rounded-2xl border px-4 py-3 text-sm ${statusToneClasses}`}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p>
                    {dayCount} day{dayCount === 1 ? "" : "s"} selected.
                  </p>
                  <span className="font-semibold uppercase tracking-[0.18em]">{runState.label}</span>
                </div>
              </div>
            ) : null}

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
              <h2 className="mt-1 text-lg font-semibold text-[#0f172a]">Data Summary</h2>
              <p className="text-sm text-[#4c576f]">
                Give the selected window a quick totals check before you generate the workbook.
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
                    Loading data summary...
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
                    ) : null}

                    <div className="mt-6 grid gap-4 md:grid-cols-2">
                      <div className="rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-4">
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7d8ba1]">
                          Imported totals
                        </p>
                        <div className="mt-3 space-y-2 text-sm text-[#4c576f]">
                          <p>
                            Clicks:{" "}
                            <span className="font-semibold text-[#0f172a]">
                              {formatNumber(summary.imported_totals.clicks)}
                            </span>
                          </p>
                          <p>
                            Spend:{" "}
                            <span className="font-semibold text-[#0f172a]">
                              {formatCurrency(summary.imported_totals.spend, selectedProfile?.currencyCode)}
                            </span>
                          </p>
                          <p>
                            Orders:{" "}
                            <span className="font-semibold text-[#0f172a]">
                              {formatNumber(summary.imported_totals.orders)}
                            </span>
                          </p>
                          <p>
                            Sales:{" "}
                            <span className="font-semibold text-[#0f172a]">
                              {formatCurrency(summary.imported_totals.sales, selectedProfile?.currencyCode)}
                            </span>
                          </p>
                        </div>
                      </div>

                      <div className="rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-4">
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7d8ba1]">
                          Workbook input
                        </p>
                        <div className="mt-3 space-y-2 text-sm text-[#4c576f]">
                          <p>
                            Eligible rows:{" "}
                            <span className="font-semibold text-[#0f172a]">
                              {formatNumber(summary.eligible_rows)}
                            </span>
                          </p>
                          <p>
                            Campaigns:{" "}
                            <span className="font-semibold text-[#0f172a]">
                              {formatNumber(summary.campaigns_included)}
                            </span>
                          </p>
                          <p>
                            Search terms:{" "}
                            <span className="font-semibold text-[#0f172a]">
                              {formatNumber(summary.unique_search_terms)}
                            </span>
                          </p>
                          <p>
                            Coverage:{" "}
                            <span className="font-semibold text-[#0f172a]">
                              {summary.coverage_start ?? "—"} to {summary.coverage_end ?? "—"}
                            </span>
                          </p>
                          <p>
                            ASIN rows removed:{" "}
                            <span className="font-semibold text-[#0f172a]">
                              {formatNumber(summary.excluded_asin_rows)}
                            </span>
                          </p>
                          <p>
                            Campaigns skipped:{" "}
                            <span className="font-semibold text-[#0f172a]">
                              {formatNumber(summary.campaigns_skipped)}
                            </span>
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#dbe4f0] bg-[#fbfdff] px-4 py-3 text-sm text-[#4c576f]">
                      <div>
                        <p className="font-semibold text-[#0f172a]">
                          Spot-check rows only if you want a closer look.
                        </p>
                        <p className="mt-1 text-xs text-[#7d8ba1]">
                          Campaign exclusions are {legacyExclusions ? "on" : "off"}. Open Search Term Data in a new tab if you want to inspect a few rows or investigate a warning.
                        </p>
                      </div>
                      {inspectRowsHref ? (
                        <Link
                          href={inspectRowsHref}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex rounded-full bg-white px-5 py-2 text-sm font-semibold text-[#0a6fd6] shadow"
                        >
                          Open Search Term Data
                        </Link>
                      ) : null}
                    </div>
                  </>
                ) : null}
              </>
            ) : (
              <div className="mt-6 space-y-3">
                {validationChecklist.map((item) => (
                  <div
                    key={item}
                    className="rounded-xl border border-[#dbe4f0] bg-[#f7faff] px-4 py-3 text-sm text-[#4c576f]"
                  >
                    {item}
                  </div>
                ))}
              </div>
            )}
          </div>

          {activityLines.length > 0 ? (
            <div className="rounded-3xl border border-[#d9e4f3] bg-[#0f172a] p-5 shadow-[0_20px_50px_rgba(15,23,42,0.24)]">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[#93c5fd]">
                  Activity
                </p>
                <button
                  type="button"
                  onClick={() => setActivityLines([])}
                  className="text-xs font-semibold uppercase tracking-[0.18em] text-[#94a3b8] transition hover:text-white"
                >
                  Clear
                </button>
              </div>
              <div
                ref={activityScrollRef}
                className="mt-3 max-h-64 space-y-2 overflow-y-auto pr-2 font-mono text-sm text-[#dbeafe]"
              >
                {activityLines.map((line, index) => (
                  <p key={`${line}-${index}`}>
                    <span className="mr-2 text-[#38bdf8]">$</span>
                    {line}
                  </p>
                ))}
              </div>
            </div>
          ) : null}

          <div className="rounded-3xl border border-dashed border-[#c7d8f5] bg-white/90 p-6 shadow-[0_24px_60px_rgba(10,59,130,0.12)]">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[#94a3b8]">Step 3</p>
              <h2 className="mt-1 text-lg font-semibold text-[#0f172a]">
                Optional: Preview AI Analysis on a Few Campaigns
              </h2>
              <p className="text-sm text-[#4c576f]">
                Use this if you want a quick spot-check before generating the workbook. Pick one campaign, run a small preview, and review the AI triage.
              </p>
            </div>

            <div className="mt-4 rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm font-semibold text-[#0f172a]">Preview selected campaigns</p>
                <button
                  type="button"
                  disabled={!canRunPureModelPreview}
                  onClick={handleRunPureModelPreview}
                  className="inline-flex rounded-full bg-[#0f172a] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#1e293b] disabled:cursor-not-allowed disabled:bg-[#a8b4c8]"
                >
                  {aiPreviewLoading ? "Running preview…" : "Run AI Preview"}
                </button>
              </div>
              <p className="mt-2 text-sm text-[#4c576f]">
                The preview stays small on purpose. Step 4 still handles the full workbook run for the selected window and threshold.
              </p>
              <p className="mt-2 text-xs text-[#7d8ba1]">
                {hasSelectedAiCampaignSubset
                  ? `${formatNumber(selectedAiCampaignNames.length)} campaign${selectedAiCampaignNames.length === 1 ? "" : "s"} selected for preview.`
                  : "Select one or more campaigns below to enable the preview."}
              </p>
            </div>

            {summary?.campaigns?.length ? (
              <div className="mt-4 rounded-2xl border border-[#dbe4f0] bg-[#fbfdff] p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-[#0f172a]">Campaign selector</p>
                    <p className="mt-1 text-sm text-[#4c576f]">
                      Choose one or more campaigns for the preview. The full workbook run is still available in Step 4.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setSelectedAiCampaignNames([])}
                    disabled={!hasSelectedAiCampaignSubset}
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
                        ? `${formatNumber(selectedAiCampaignNames.length)} campaign${selectedAiCampaignNames.length === 1 ? "" : "s"} selected for preview.`
                        : "No campaign selected yet."}
                    </p>
                  </label>

                  <div className="rounded-2xl border border-[#dbe4f0] bg-white p-2">
                    <div className="max-h-56 space-y-2 overflow-y-auto px-2 py-1">
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
                                <span className="block text-sm font-semibold text-[#0f172a]">
                                  {campaign.campaign_name}
                                </span>
                                <span className="mt-1 block text-xs text-[#64748b]">
                                  {formatCurrency(campaign.spend, selectedProfile?.currencyCode)} spend •{" "}
                                  {formatNumber(campaign.search_terms)} search terms
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
                  <div className="mt-4 space-y-3">
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

                <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <div className="rounded-2xl border border-[#dbe4f0] bg-white p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7d8ba1]">
                      Campaigns previewed
                    </p>
                    <p className="mt-2 text-lg font-semibold text-[#0f172a]">
                      {formatNumber(aiPreview.preview_campaigns)}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-[#dbe4f0] bg-white p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7d8ba1]">
                      Likely negatives
                    </p>
                    <p className="mt-2 text-lg font-semibold text-[#0f172a]">
                      {formatNumber(aiPreview.recommendation_counts.negate)}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-[#dbe4f0] bg-white p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7d8ba1]">Reviews</p>
                    <p className="mt-2 text-lg font-semibold text-[#0f172a]">
                      {formatNumber(aiPreview.recommendation_counts.review)}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-[#dbe4f0] bg-white p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7d8ba1]">Model</p>
                    <p className="mt-2 text-sm font-semibold text-[#0f172a]">{aiPreview.model ?? "n/a"}</p>
                    <p className="mt-1 text-xs text-[#7d8ba1]">
                      Threshold {formatCurrency(aiPreview.spend_threshold, selectedProfile?.currencyCode)}
                    </p>
                  </div>
                </div>

                {canGenerateAiPreviewWorkbook ? (
                  <button
                    type="button"
                    disabled={!canGenerateAiPreviewWorkbook}
                    onClick={handleGenerateAiPreviewWorkbook}
                    className="mt-4 inline-flex rounded-full border border-[#b9c9e6] bg-white px-5 py-2.5 text-sm font-semibold text-[#0f172a] transition hover:border-[#8bb6ff] hover:bg-[#eef5ff] disabled:cursor-not-allowed disabled:border-[#d7deea] disabled:text-[#94a3b8]"
                  >
                    {aiPreviewWorkbookGenerating ? "Generating preview workbook…" : "Download Preview Workbook"}
                  </button>
                ) : null}

                <div className="mt-4 space-y-3">
                  {aiPreview.campaigns.map((campaign) => {
                    const sortedEvaluations = sortPreviewEvaluations(campaign.evaluations);
                    const visibleCount =
                      expandedPreviewRows[campaign.campaignName] ?? AI_PREVIEW_RESULT_LIMIT;
                    const visibleEvaluations = sortedEvaluations.slice(0, visibleCount);
                    const hiddenEvaluationCount = Math.max(sortedEvaluations.length - visibleCount, 0);
                    const campaignCounts = sortedEvaluations.reduce<
                      Record<AIPrefillRecommendation["recommendation"], number>
                    >(
                      (counts, evaluation) => {
                        counts[evaluation.recommendation] += 1;
                        return counts;
                      },
                      { KEEP: 0, NEGATE: 0, REVIEW: 0 },
                    );

                    return (
                      <details
                        key={campaign.campaignName}
                        className="rounded-2xl border border-[#dbe4f0] bg-white px-4 py-4"
                      >
                        <summary className="cursor-pointer list-none">
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                              <p className="text-sm font-semibold text-[#0f172a]">{campaign.campaignName}</p>
                              <p className="mt-1 text-xs text-[#64748b]">
                                {campaign.matchedTitle
                                  ? `${campaign.matchedTitle}${campaign.theme ? ` • theme: ${campaign.theme}` : ""}`
                                  : "AI could not confidently identify one product."}
                              </p>
                            </div>
                            <div className="flex flex-wrap gap-2 text-[11px] font-semibold uppercase tracking-[0.18em]">
                              <span className="rounded-full border border-[#f3c1c1] bg-[#fff3f3] px-3 py-1 text-[#991b1b]">
                                {campaignCounts.NEGATE} likely negate
                              </span>
                              <span className="rounded-full border border-[#f0d9b1] bg-[#fff8ee] px-3 py-1 text-[#7d5a1d]">
                                {campaignCounts.REVIEW} review
                              </span>
                              <span className="rounded-full border border-[#c7ebd4] bg-[#edf9f1] px-3 py-1 text-[#1f6b37]">
                                {campaignCounts.KEEP} safe keep
                              </span>
                            </div>
                          </div>
                        </summary>

                        <div className="mt-4 grid gap-3 md:grid-cols-4">
                          <div className="rounded-xl border border-[#e3ebf6] bg-[#fbfdff] px-4 py-3 text-sm text-[#4c576f]">
                            Eligible spend:{" "}
                            <span className="font-semibold text-[#0f172a]">
                              {formatCurrency(campaign.eligibleSpend, selectedProfile?.currencyCode)}
                            </span>
                          </div>
                          <div className="rounded-xl border border-[#e3ebf6] bg-[#fbfdff] px-4 py-3 text-sm text-[#4c576f]">
                            Terms above threshold:{" "}
                            <span className="font-semibold text-[#0f172a]">
                              {formatNumber(campaign.eligibleTerms)}
                            </span>
                          </div>
                          <div className="rounded-xl border border-[#e3ebf6] bg-[#fbfdff] px-4 py-3 text-sm text-[#4c576f]">
                            Skipped below threshold:{" "}
                            <span className="font-semibold text-[#0f172a]">
                              {formatNumber(campaign.skippedBelowThresholdTerms)}
                            </span>
                          </div>
                          <div className="rounded-xl border border-[#e3ebf6] bg-[#fbfdff] px-4 py-3 text-sm text-[#4c576f]">
                            Identifier:{" "}
                            <span className="font-semibold text-[#0f172a]">
                              {campaign.productIdentifier ?? "—"}
                            </span>
                          </div>
                        </div>

                        {visibleEvaluations.length > 0 ? (
                          <div className="mt-4 space-y-3">
                            {visibleEvaluations.map((evaluation) => {
                              const pillClasses =
                                evaluation.recommendation === "NEGATE"
                                  ? "border-[#f3c1c1] bg-[#fff3f3] text-[#991b1b]"
                                  : evaluation.recommendation === "KEEP"
                                    ? "border-[#c7ebd4] bg-[#edf9f1] text-[#1f6b37]"
                                    : "border-[#f0d9b1] bg-[#fff8ee] text-[#7d5a1d]";

                              return (
                                <div
                                  key={evaluation.search_term}
                                  className="rounded-xl border border-[#e3ebf6] bg-[#fbfdff] px-4 py-3"
                                >
                                  <div className="flex flex-wrap items-start justify-between gap-3">
                                    <div>
                                      <p className="text-sm font-semibold text-[#0f172a]">
                                        {evaluation.search_term}
                                      </p>
                                      <p className="mt-1 text-xs text-[#64748b]">
                                        Spend{" "}
                                        {formatCurrency(evaluation.spend, selectedProfile?.currencyCode)} •
                                        Clicks {formatNumber(evaluation.clicks)} • Orders{" "}
                                        {formatNumber(evaluation.orders)}
                                      </p>
                                    </div>
                                    <div
                                      className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${pillClasses}`}
                                    >
                                      {formatRecommendationLabel(evaluation.recommendation)} •{" "}
                                      {evaluation.confidence}
                                    </div>
                                  </div>
                                  <p className="mt-2 text-sm text-[#334155]">
                                    <span className="font-semibold text-[#0f172a]">
                                      {formatReasonTag(evaluation.reason_tag)}
                                    </span>
                                    {evaluation.rationale ? ` • ${evaluation.rationale}` : ""}
                                  </p>
                                </div>
                              );
                            })}

                            {hiddenEvaluationCount > 0 ? (
                              <div className="flex flex-wrap items-center gap-3 text-xs text-[#7d8ba1]">
                                <p>
                                  Showing the first {formatNumber(visibleCount)} rows for this campaign.{" "}
                                  {formatNumber(hiddenEvaluationCount)} more rows are hidden to keep the
                                  preview compact.
                                </p>
                                <button
                                  type="button"
                                  onClick={() =>
                                    setExpandedPreviewRows((current) => ({
                                      ...current,
                                      [campaign.campaignName]: Math.min(
                                        sortedEvaluations.length,
                                        visibleCount + AI_PREVIEW_RESULT_LIMIT,
                                      ),
                                    }))
                                  }
                                  className="font-semibold text-[#0a6fd6] transition hover:text-[#0959ab]"
                                >
                                  Show 10 more
                                </button>
                                <button
                                  type="button"
                                  onClick={() =>
                                    setExpandedPreviewRows((current) => ({
                                      ...current,
                                      [campaign.campaignName]: sortedEvaluations.length,
                                    }))
                                  }
                                  className="font-semibold text-[#0a6fd6] transition hover:text-[#0959ab]"
                                >
                                  Show all
                                </button>
                              </div>
                            ) : null}
                            {visibleCount > AI_PREVIEW_RESULT_LIMIT ? (
                              <button
                                type="button"
                                onClick={() =>
                                  setExpandedPreviewRows((current) => ({
                                    ...current,
                                    [campaign.campaignName]: AI_PREVIEW_RESULT_LIMIT,
                                  }))
                                }
                                className="text-xs font-semibold text-[#0a6fd6] transition hover:text-[#0959ab]"
                              >
                                Show less
                              </button>
                            ) : null}
                          </div>
                        ) : null}
                      </details>
                    );
                  })}
                </div>
              </>
            ) : null}
          </div>

          <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)]">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[#94a3b8]">Step 4</p>
              <h2 className="mt-1 text-lg font-semibold text-[#0f172a]">Generate Workbook</h2>
              <p className="text-sm text-[#4c576f]">
                Run the full AI triage pass for the selected window and download the review workbook.
              </p>
              <p className="mt-1 text-xs text-[#94a3b8]">
                The workbook uses the selected date range and minimum spend from Step 1, then writes triage guidance without filling `NE/NP` or scratchpad negatives.
              </p>
            </div>

            <button
              type="button"
              disabled={!canGenerateWorkbook}
              onClick={handleGenerateAiWorkbook}
              className="mt-6 w-full rounded-2xl bg-[#0f172a] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(15,23,42,0.24)] transition hover:bg-[#1e293b] disabled:cursor-not-allowed disabled:bg-[#b8c1d1]"
            >
              {aiWorkbookGenerating ? "Running AI and generating workbook…" : "Generate Workbook"}
            </button>

            <div className="mt-4 rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-4">
              <p className="text-sm text-[#4c576f]">
                {selectedProduct === "sp"
                  ? "The generated workbook writes SAFE KEEP / LIKELY NEGATE / REVIEW guidance across the full selected window and leaves final analyst expression blank."
                  : "Workbook generation is intentionally limited to Sponsored Products first."}
              </p>
            </div>

            {aiWorkbookError ? (
              <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
                {aiWorkbookError}
              </p>
            ) : null}
          </div>

          <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)]">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[#94a3b8]">Step 5</p>
              <h2 className="mt-1 text-lg font-semibold text-[#0f172a]">Upload Reviewed Workbook to Collect Negatives</h2>
              <p className="text-sm text-[#4c576f]">
                After the analyst reviews the workbook and fills the final negatives, upload it here to get the campaign-by-campaign negatives summary back.
              </p>
            </div>

            <div
              onDragOver={(event) => event.preventDefault()}
              onDrop={handleFilledWorkbookDrop}
              className="mt-6 rounded-2xl border border-dashed border-[#c7d8f5] bg-[#f7faff] p-10 text-center"
            >
              <p className="text-base font-semibold text-[#0f172a]">Drag and drop the reviewed workbook</p>
              <p className="text-sm text-[#4c576f]">(.xlsx)</p>
              <div className="mt-4 flex flex-col items-center gap-3">
                <label className="cursor-pointer rounded-full bg-white px-5 py-2 text-sm font-semibold text-[#0a6fd6] shadow">
                  <input
                    type="file"
                    accept=".xlsx"
                    className="hidden"
                    onChange={(event) => handleFilledWorkbookChange(event.target.files?.[0] ?? null)}
                  />
                  Browse files
                </label>
                <p className="text-xs text-[#94a3b8]">
                  {selectedFilledWorkbook ? selectedFilledWorkbook.name : "No file selected"}
                </p>
              </div>
            </div>

            <button
              type="button"
              disabled={!canCollectNegatives}
              onClick={handleCollectNegatives}
              className="mt-6 w-full rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-[#b7cbea]"
            >
              {collectingNegatives ? "Collecting…" : "Download Negatives Summary"}
            </button>

            {collectError ? (
              <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
                {collectError}
              </p>
            ) : null}
          </div>

          <div className="rounded-3xl border border-dashed border-[#d7dfec] bg-white/70 p-8 opacity-75 shadow-[0_18px_40px_rgba(10,59,130,0.08)]">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[#94a3b8]">Step 6</p>
                <h2 className="mt-1 text-lg font-semibold text-[#0f172a]">Coming Soon: Push Negatives Directly to Amazon</h2>
                <p className="text-sm text-[#4c576f]">
                  A future step will let analysts send approved negatives straight to Amazon with explicit confirmation and audit logging.
                </p>
              </div>
              <span className="rounded-full bg-[#f2f4f8] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-[#65748a]">
                coming soon
              </span>
            </div>
          </div>

          {loading ? <p className="text-sm text-[#4c576f]">Loading client and marketplace options…</p> : null}
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
