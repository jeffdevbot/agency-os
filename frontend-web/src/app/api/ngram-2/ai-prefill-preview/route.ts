import { NextResponse } from "next/server";

import { logAppError } from "@/lib/ai/errorLogger";
import { persistNgramPreviewRun } from "@/lib/ai/ngramPreviewLogger";
import { logUsage } from "@/lib/ai/usageLogger";
import { NGRAM_AI_PROMPT_VERSION, NGRAM_PURE_MODEL_PROMPT_VERSION } from "@/lib/ngram2/aiPrompt";
import {
  estimateNgramCampaignMaxTokens,
  NgramStructuredOutputValidationError,
  evaluateCampaignWithValidationRetry,
  evaluateCampaignTermTriageWithValidationRetry,
  evaluateCampaignWithPureModelValidationRetry,
} from "@/lib/ngram2/aiCampaignEvaluator";
import {
  aggregateSearchTerms,
  AI_PREFILL_PREVIEW_MAX_CAMPAIGNS,
  AI_PREFILL_PREVIEW_MAX_TERMS_PER_CAMPAIGN,
  type AIPrefillBrandContext,
  buildCampaignAggregates,
  buildPreparedCatalogProductIndex,
  isAsinQuery,
  isLegacyExcludedCampaign,
  mergePureModelTermTriageResponses,
  parseCampaignProductIdentifier,
  parseCampaignTheme,
  prepareAIPrefillCatalogProducts,
  selectCatalogCandidatesForCampaign,
  selectCampaignsForAIPrefill,
  selectTermsForAIPrefillCampaign,
  synthesizeCampaignScratchpad,
  type AIPrefillStrategy,
  type AggregatedCampaign,
  type AggregatedSearchTerm,
  type AIPrefillRunMode,
  type AIPrefillCatalogProduct,
  type CampaignModelPrefills,
  type CampaignPrefillScratchpad,
  type NgramListingRow,
  type PureModelPhraseNegative,
  type SearchTermFactRow,
  type ValidatedPureModelContextResponse,
  type ValidatedPureModelTermTriageResponse,
} from "@/lib/ngram2/aiPrefill";
import { resolveCatalogSource, type CatalogSourceCandidate, type CatalogSourceProfile } from "@/lib/ngram2/catalogSource";
import { createSupabaseRouteClient, createSupabaseServiceClient } from "@/lib/supabase/serverClient";

const FACT_SELECT = [
  "report_date",
  "campaign_name",
  "search_term",
  "impressions",
  "clicks",
  "spend",
  "orders",
  "sales",
  "keyword",
  "keyword_type",
  "targeting",
  "match_type",
].join(",");

const LISTING_SELECT = [
  "child_asin",
  "child_sku",
  "child_product_name",
  "parent_title",
  "category",
  "item_description",
].join(",");

const MAX_BATCH_SIZE = 1000;
const SUPPORTED_AD_PRODUCT = "SPONSORED_PRODUCTS";
const PROFILE_SELECT = ["id", "client_id", "display_name", "marketplace_code", "status"].join(",");
const NGRAM_MODEL_OVERRIDE = process.env.OPENAI_MODEL_NGRAM?.trim() || null;
const PURE_MODEL_MAX_TERMS_PER_CHUNK = 100;
const HEURISTIC_CATALOG_CANDIDATE_LIMIT = 24;
const PURE_MODEL_CONTEXT_CANDIDATE_LIMIT = 18;
const PURE_MODEL_CONTEXT_EXPANDED_CANDIDATE_LIMIT = 36;
const RECENT_RUN_REUSE_WINDOW_MS = 2 * 60 * 60 * 1000;

type CampaignPreview = {
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
  synthesizedPrefills: CampaignPrefillScratchpad;
  modelPrefills: CampaignModelPrefills;
  phraseNegatives: PureModelPhraseNegative[];
  evaluations: Array<{
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
  }>;
};

type PureModelEvaluationResult = {
  completion: {
    model: string;
  };
  context: ValidatedPureModelContextResponse;
  triage: ValidatedPureModelTermTriageResponse;
  attempts: number;
  tokensIn: number;
  tokensOut: number;
  tokensTotal: number;
};

const loadAllFactRows = async (
  profileId: string,
  adProduct: string,
  dateFrom: string,
  dateTo: string,
): Promise<SearchTermFactRow[]> => {
  const supabase = createSupabaseServiceClient();
  const rows: SearchTermFactRow[] = [];
  let offset = 0;

  while (true) {
    const { data, error } = await supabase
      .from("search_term_daily_facts")
      .select(FACT_SELECT)
      .eq("profile_id", profileId)
      .eq("ad_product", adProduct)
      .gte("report_date", dateFrom)
      .lte("report_date", dateTo)
      .range(offset, offset + MAX_BATCH_SIZE - 1);

    if (error) throw new Error(error.message);
    const rawBatch: unknown[] = Array.isArray(data) ? [...data] : [];
    const batch = rawBatch.filter(
      (row): row is SearchTermFactRow => Boolean(row) && typeof row === "object",
    );
    rows.push(...batch);
    if (batch.length < MAX_BATCH_SIZE) break;
    offset += MAX_BATCH_SIZE;
  }

  return rows;
};

const loadListings = async (profileId: string): Promise<NgramListingRow[]> => {
  const supabase = createSupabaseServiceClient();
  const { data, error } = await supabase
    .from("wbr_profile_child_asins")
    .select(LISTING_SELECT)
    .eq("profile_id", profileId)
    .eq("active", true);

  if (error) throw new Error(error.message);
  const rawRows: unknown[] = Array.isArray(data) ? [...data] : [];
  return rawRows.filter((row): row is NgramListingRow => Boolean(row) && typeof row === "object");
};

const loadCatalogProfile = async (profileId: string): Promise<CatalogSourceProfile> => {
  const supabase = createSupabaseServiceClient();
  const { data, error } = await supabase
    .from("wbr_profiles")
    .select(PROFILE_SELECT)
    .eq("id", profileId)
    .limit(1)
    .maybeSingle();

  if (error) throw new Error(error.message);
  if (!data || typeof data !== "object") {
    throw new Error(`Profile ${profileId} was not found.`);
  }

  return {
    profileId: String((data as Record<string, unknown>).id || "").trim(),
    clientId: String((data as Record<string, unknown>).client_id || "").trim() || null,
    displayName: String((data as Record<string, unknown>).display_name || "").trim() || null,
    marketplaceCode: String((data as Record<string, unknown>).marketplace_code || "").trim() || null,
  };
};

const loadSiblingCatalogCandidates = async (
  profile: CatalogSourceProfile,
): Promise<CatalogSourceCandidate[]> => {
  if (!profile.clientId) return [];

  const supabase = createSupabaseServiceClient();
  const { data, error } = await supabase
    .from("wbr_profiles")
    .select(PROFILE_SELECT)
    .eq("client_id", profile.clientId)
    .neq("id", profile.profileId);

  if (error) throw new Error(error.message);

  const rawRows: unknown[] = Array.isArray(data) ? [...data] : [];
  const siblingProfiles = rawRows.filter(
    (row): row is Record<string, unknown> => Boolean(row) && typeof row === "object",
  );

  return Promise.all(
    siblingProfiles.map(async (row) => ({
      profileId: String(row.id || "").trim(),
      clientId: String(row.client_id || "").trim() || null,
      displayName: String(row.display_name || "").trim() || null,
      marketplaceCode: String(row.marketplace_code || "").trim() || null,
      listings: await loadListings(String(row.id || "").trim()),
    })),
  );
};

const normalizeBrandName = (value: unknown): string | null => {
  const trimmed = String(value || "").trim();
  return trimmed || null;
};

const isNonEmptyString = (value: string | null): value is string => Boolean(value);

const loadClientBrandContext = async (
  profile: CatalogSourceProfile,
): Promise<AIPrefillBrandContext> => {
  if (!profile.clientId) {
    return {
      clientName: null,
      knownBrandNames: [],
      marketplaceBrandNames: [],
    };
  }

  const supabase = createSupabaseServiceClient();
  const { data, error } = await supabase
    .from("agency_clients")
    .select("name, brands(name, amazon_marketplaces)")
    .eq("id", profile.clientId)
    .limit(1)
    .maybeSingle();

  if (error) throw new Error(error.message);

  const clientRow =
    data && typeof data === "object" && !Array.isArray(data) ? (data as Record<string, unknown>) : null;
  const rawBrands =
    clientRow && Array.isArray((clientRow as { brands?: unknown }).brands)
      ? (((clientRow as { brands?: unknown }).brands as unknown[]) ?? [])
      : [];

  const clientName = normalizeBrandName(clientRow?.name);
  const knownBrandNames = [
    ...new Set(
      rawBrands
        .map((brand) => normalizeBrandName((brand as Record<string, unknown>)?.name))
        .filter(isNonEmptyString),
    ),
  ];
  const profileMarketplace = String(profile.marketplaceCode || "").trim().toUpperCase();
  const marketplaceBrandNames = [
    ...new Set(
      rawBrands
        .filter((brand) => {
          const marketplaces = Array.isArray((brand as { amazon_marketplaces?: unknown }).amazon_marketplaces)
            ? ((brand as { amazon_marketplaces?: unknown }).amazon_marketplaces as unknown[])
                .map((value) => String(value || "").trim().toUpperCase())
                .filter(Boolean)
            : [];
          return marketplaces.length === 0 || !profileMarketplace || marketplaces.includes(profileMarketplace);
        })
        .map((brand) => normalizeBrandName((brand as Record<string, unknown>)?.name))
        .filter(isNonEmptyString),
    ),
  ];

  return {
    clientName,
    knownBrandNames,
    marketplaceBrandNames,
  };
};

const resolveCatalogListings = async (
  profileId: string,
): Promise<{
  profile: CatalogSourceProfile;
  listings: NgramListingRow[];
  warning: string | null;
}> => {
  const [profile, requestedListings] = await Promise.all([
    loadCatalogProfile(profileId),
    loadListings(profileId),
  ]);

  const siblingCandidates = requestedListings.length > 0 ? [] : await loadSiblingCatalogCandidates(profile);
  const resolved = resolveCatalogSource(profile, requestedListings, siblingCandidates);

  return {
    profile,
    listings: resolved.listings,
    warning: resolved.warning,
  };
};

const coerceRequest = async (request: Request): Promise<{
  profileId: string;
  adProduct: string;
  dateFrom: string;
  dateTo: string;
  spendThreshold: number;
  respectLegacyExclusions: boolean;
  runMode: AIPrefillRunMode;
  prefillStrategy: AIPrefillStrategy;
  requestedCampaignNames: string[];
}> => {
  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null;
  const profileId = String(body?.profile_id || "").trim();
  const adProduct = String(body?.ad_product || "").trim().toUpperCase();
  const dateFrom = String(body?.date_from || "").trim();
  const dateTo = String(body?.date_to || "").trim();
  const spendThresholdRaw = Number(body?.spend_threshold ?? 0);
  const runModeRaw = String(body?.run_mode || "preview").trim().toLowerCase();
  const prefillStrategyRaw = String(body?.prefill_strategy || "heuristic_synthesis")
    .trim()
    .toLowerCase();
  const requestedCampaignNames = Array.isArray(body?.campaign_names)
    ? [...new Set(body.campaign_names.map((value) => String(value || "").trim()).filter(Boolean))]
    : [];

  if (!profileId || !adProduct || !dateFrom || !dateTo) {
    throw new Error("profile_id, ad_product, date_from, and date_to are required");
  }
  if (adProduct !== SUPPORTED_AD_PRODUCT) {
    throw new Error("AI prefill preview is currently enabled for Sponsored Products only.");
  }
  if (!Number.isFinite(spendThresholdRaw) || spendThresholdRaw < 0) {
    throw new Error("spend_threshold must be a number greater than or equal to 0");
  }
  if (dateFrom > dateTo) {
    throw new Error("date_from must be on or before date_to");
  }
  if (runModeRaw !== "preview" && runModeRaw !== "full") {
    throw new Error("run_mode must be either 'preview' or 'full'");
  }
  if (prefillStrategyRaw !== "heuristic_synthesis" && prefillStrategyRaw !== "pure_model_single_campaign") {
    throw new Error("prefill_strategy must be either 'heuristic_synthesis' or 'pure_model_single_campaign'");
  }
  if (prefillStrategyRaw === "pure_model_single_campaign") {
    if (runModeRaw === "preview" && requestedCampaignNames.length === 0) {
      throw new Error("pure_model_single_campaign requires at least one selected campaign.");
    }
  }

  return {
    profileId,
    adProduct,
    dateFrom,
    dateTo,
    spendThreshold: spendThresholdRaw,
    respectLegacyExclusions: body?.respect_legacy_exclusions !== false,
    runMode: runModeRaw as AIPrefillRunMode,
    prefillStrategy: prefillStrategyRaw as AIPrefillStrategy,
    requestedCampaignNames,
  };
};

const normalizeRequestedCampaignNames = (value: unknown): string[] =>
  Array.isArray(value)
    ? [...new Set(value.map((item) => String(item || "").trim()).filter(Boolean))].sort((left, right) =>
        left.localeCompare(right),
      )
    : [];

const isRecentMatchingSavedRun = (
  row: Record<string, unknown>,
  request: {
    requestedByAuthUserId: string;
    profileId: string;
    adProduct: string;
    dateFrom: string;
    dateTo: string;
    spendThreshold: number;
    respectLegacyExclusions: boolean;
    runMode: AIPrefillRunMode;
    prefillStrategy: AIPrefillStrategy;
    requestedCampaignNames: string[];
    expectedPromptVersion: string;
  },
): boolean => {
  const createdAtRaw = String(row.created_at || "").trim();
  if (!createdAtRaw) return false;
  const createdAtMs = Date.parse(createdAtRaw);
  if (!Number.isFinite(createdAtMs)) return false;
  if (Date.now() - createdAtMs > RECENT_RUN_REUSE_WINDOW_MS) return false;

  if (String(row.requested_by_auth_user_id || "").trim() !== request.requestedByAuthUserId) return false;
  if (String(row.profile_id || "").trim() !== request.profileId) return false;
  if (String(row.ad_product || "").trim().toUpperCase() !== request.adProduct) return false;
  if (String(row.date_from || "").trim() !== request.dateFrom) return false;
  if (String(row.date_to || "").trim() !== request.dateTo) return false;
  if (Number(row.spend_threshold ?? 0) !== request.spendThreshold) return false;
  if (Boolean(row.respect_legacy_exclusions) !== request.respectLegacyExclusions) return false;
  if (String(row.prompt_version || "").trim() !== request.expectedPromptVersion) return false;

  const payload =
    row.preview_payload && typeof row.preview_payload === "object" && !Array.isArray(row.preview_payload)
      ? (row.preview_payload as Record<string, unknown>)
      : null;
  if (!payload) return false;

  const payloadRunMode = String(payload.run_mode || "preview").trim().toLowerCase();
  const payloadStrategy = String(payload.prefill_strategy || "heuristic_synthesis").trim().toLowerCase();
  if (payloadRunMode !== request.runMode) return false;
  if (payloadStrategy !== request.prefillStrategy) return false;

  const payloadCampaignNames = normalizeRequestedCampaignNames(payload.selected_campaigns);
  const requestCampaignNames = [...request.requestedCampaignNames].sort((left, right) =>
    left.localeCompare(right),
  );
  if (payloadCampaignNames.length !== requestCampaignNames.length) return false;
  return payloadCampaignNames.every((value, index) => value === requestCampaignNames[index]);
};

const loadRecentMatchingSavedRun = async (request: {
  requestedByAuthUserId: string;
  profileId: string;
  adProduct: string;
  dateFrom: string;
  dateTo: string;
  spendThreshold: number;
  respectLegacyExclusions: boolean;
  runMode: AIPrefillRunMode;
  prefillStrategy: AIPrefillStrategy;
  requestedCampaignNames: string[];
  expectedPromptVersion: string;
}): Promise<{ id: string; createdAt: string | null; previewPayload: Record<string, unknown> } | null> => {
  const supabase = createSupabaseServiceClient();
  const { data, error } = await supabase
    .from("ngram_ai_preview_runs")
    .select(
      [
        "id",
        "created_at",
        "requested_by_auth_user_id",
        "profile_id",
        "ad_product",
        "date_from",
        "date_to",
        "spend_threshold",
        "respect_legacy_exclusions",
        "prompt_version",
        "preview_payload",
      ].join(","),
    )
    .eq("requested_by_auth_user_id", request.requestedByAuthUserId)
    .eq("profile_id", request.profileId)
    .eq("ad_product", request.adProduct)
    .eq("date_from", request.dateFrom)
    .eq("date_to", request.dateTo)
    .eq("respect_legacy_exclusions", request.respectLegacyExclusions)
    .eq("prompt_version", request.expectedPromptVersion)
    .eq("spend_threshold", request.spendThreshold)
    .order("created_at", { ascending: false })
    .limit(5);

  if (error) {
    throw new Error(error.message);
  }

  const rows = Array.isArray(data) ? data : [];
  const match = rows.find((row) =>
    row && typeof row === "object" && isRecentMatchingSavedRun(row as Record<string, unknown>, request),
  ) as Record<string, unknown> | undefined;

  if (!match) return null;

  const previewPayload =
    match.preview_payload && typeof match.preview_payload === "object" && !Array.isArray(match.preview_payload)
      ? (match.preview_payload as Record<string, unknown>)
      : null;

  if (!previewPayload) return null;

  return {
    id: String(match.id || "").trim(),
    createdAt: typeof match.created_at === "string" ? match.created_at : null,
    previewPayload,
  };
};

export async function POST(request: Request) {
  const supabase = await createSupabaseRouteClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  let requestMeta: Record<string, unknown> = {};

  try {
    const {
      profileId,
      adProduct,
      dateFrom,
      dateTo,
      spendThreshold,
      respectLegacyExclusions,
      runMode,
      prefillStrategy,
      requestedCampaignNames,
    } =
      await coerceRequest(request);

    requestMeta = {
      profile_id: profileId,
      ad_product: adProduct,
      date_from: dateFrom,
      date_to: dateTo,
      spend_threshold: spendThreshold,
      respect_legacy_exclusions: respectLegacyExclusions,
      run_mode: runMode,
      prefill_strategy: prefillStrategy,
      requested_campaign_names: requestedCampaignNames,
    };

    const expectedPromptVersion =
      prefillStrategy === "pure_model_single_campaign"
        ? NGRAM_PURE_MODEL_PROMPT_VERSION
        : NGRAM_AI_PROMPT_VERSION;

    if (runMode === "full") {
      const recentSavedRun = await loadRecentMatchingSavedRun({
        requestedByAuthUserId: user.id,
        profileId,
        adProduct,
        dateFrom,
        dateTo,
        spendThreshold,
        respectLegacyExclusions,
        runMode,
        prefillStrategy,
        requestedCampaignNames,
        expectedPromptVersion,
      });

      if (recentSavedRun) {
        const previewPayload = {
          ...recentSavedRun.previewPayload,
          warnings: [
            ...((Array.isArray(recentSavedRun.previewPayload.warnings)
              ? recentSavedRun.previewPayload.warnings
              : []) as string[]),
            "Reused a recent identical saved AI run instead of rerunning the model.",
          ],
        };

        return NextResponse.json({
          ok: true,
          reused_saved_run: true,
          preview_run_id: recentSavedRun.id,
          preview_created_at: recentSavedRun.createdAt,
          preview: previewPayload,
        });
      }
    }

    const warnings: string[] = [];

    const [{ profile: catalogProfile, listings, warning: catalogWarning }, rows] = await Promise.all([
      resolveCatalogListings(profileId),
      loadAllFactRows(profileId, adProduct, dateFrom, dateTo),
    ]);

      if (catalogWarning) {
      warnings.push(catalogWarning);
    }

    if (prefillStrategy === "pure_model_single_campaign") {
      warnings.push(
        runMode === "preview"
          ? `Pure-model two-step preview is active for ${requestedCampaignNames.length} selected campaign(s).`
          : "Pure-model two-step evaluation is active for full workbook generation.",
      );
    }

    const brandContext = await loadClientBrandContext(catalogProfile);
    const catalogProducts = prepareAIPrefillCatalogProducts(listings);
    if (catalogProducts.length === 0) {
      throw new Error(
        "No active Windsor child ASIN catalog rows were found for this profile. Import Windsor listings for this marketplace before running AI preview.",
      );
    }
    const preparedCatalogIndex = buildPreparedCatalogProductIndex(catalogProducts);

    const usableRows = rows.filter((row) => {
      const campaignName = String(row.campaign_name || "").trim();
      const searchTerm = String(row.search_term || "").trim();
      if (!campaignName || !searchTerm) return false;
      if (isAsinQuery(searchTerm)) return false;
      if (respectLegacyExclusions && isLegacyExcludedCampaign(campaignName)) return false;
      return true;
    });

    const aggregatedTerms = aggregateSearchTerms(usableRows);
    const candidateCampaigns = buildCampaignAggregates(aggregatedTerms, {
      spendThreshold,
      respectLegacyExclusions,
    });

    const runnableCampaigns = candidateCampaigns;
    const intentionallySkippedCampaigns = 0;
    const previewCampaigns = selectCampaignsForAIPrefill(runnableCampaigns, runMode, requestedCampaignNames);
    const hasRequestedCampaigns = requestedCampaignNames.length > 0;
    const missingRequestedCampaigns = hasRequestedCampaigns
      ? requestedCampaignNames.filter(
          (campaignName) => !runnableCampaigns.some((campaign) => campaign.campaignName === campaignName),
        )
      : [];

    if (!hasRequestedCampaigns && runMode === "preview" && runnableCampaigns.length > AI_PREFILL_PREVIEW_MAX_CAMPAIGNS) {
      warnings.push(
        `Preview is limited to the top ${AI_PREFILL_PREVIEW_MAX_CAMPAIGNS} runnable campaigns by eligible spend.`,
      );
    }

    if (hasRequestedCampaigns) {
      warnings.push(
        `Campaign-scoped preview selected ${previewCampaigns.length} campaign(s); preview caps are bypassed for those campaigns.`,
      );
    }

    if (missingRequestedCampaigns.length > 0) {
      warnings.push(
        `${missingRequestedCampaigns.length} requested campaign(s) were not runnable for this window, threshold, or exclusion setting.`,
      );
    }

    let tokensIn = 0;
    let tokensOut = 0;
    let tokensTotal = 0;
    let model = "";

    const previewResults: CampaignPreview[] = [];
    let ambiguousCampaigns = 0;
    let aiLowConfidenceCampaigns = 0;

    for (const campaign of previewCampaigns) {
      const terms = selectTermsForAIPrefillCampaign(campaign, runMode, hasRequestedCampaigns);
      const skippedBelowThresholdTerms = aggregatedTerms.filter(
        (term) => term.campaignName === campaign.campaignName && term.spend < spendThreshold,
      ).length;
      const productIdentifier = parseCampaignProductIdentifier(campaign.campaignName);
      const theme = parseCampaignTheme(campaign.campaignName);
      const rankedCatalogCandidates = selectCatalogCandidatesForCampaign(
        campaign.campaignName,
        preparedCatalogIndex,
        {
          limit:
            prefillStrategy === "pure_model_single_campaign"
              ? PURE_MODEL_CONTEXT_EXPANDED_CANDIDATE_LIMIT
              : HEURISTIC_CATALOG_CANDIDATE_LIMIT,
        },
      );

      if (
        !hasRequestedCampaigns &&
        runMode === "preview" &&
        campaign.terms.length > AI_PREFILL_PREVIEW_MAX_TERMS_PER_CAMPAIGN
      ) {
        warnings.push(
          `${campaign.campaignName}: preview only evaluates the top ${AI_PREFILL_PREVIEW_MAX_TERMS_PER_CAMPAIGN} terms by spend.`,
        );
      }

      const heuristicEvaluation =
        prefillStrategy === "heuristic_synthesis"
          ? await evaluateCampaignWithValidationRetry({
              campaign,
              catalogProducts: rankedCatalogCandidates
                .slice(0, HEURISTIC_CATALOG_CANDIDATE_LIMIT)
                .map((candidate) => candidate.product),
              terms,
              marketplaceCode: catalogProfile.marketplaceCode,
              brandContext,
              model: NGRAM_MODEL_OVERRIDE || undefined,
              maxTokens: estimateNgramCampaignMaxTokens(terms.length),
            })
          : null;
      let pureModelEvaluation: PureModelEvaluationResult | null = null;
      if (prefillStrategy === "pure_model_single_campaign") {
        const termChunks: AggregatedSearchTerm[][] = [];
        for (let index = 0; index < terms.length; index += PURE_MODEL_MAX_TERMS_PER_CHUNK) {
          termChunks.push(terms.slice(index, index + PURE_MODEL_MAX_TERMS_PER_CHUNK));
        }

        if (termChunks.length > 1) {
          warnings.push(
            `${campaign.campaignName}: pure-model preview chunked ${terms.length} terms into ${termChunks.length} batches of up to ${PURE_MODEL_MAX_TERMS_PER_CHUNK}.`,
          );
        }

        const initialContextCandidates = rankedCatalogCandidates
          .slice(0, PURE_MODEL_CONTEXT_CANDIDATE_LIMIT)
          .map((candidate) => candidate.product);
        let contextPasses = 1;
        let contextEvaluation = await evaluateCampaignWithPureModelValidationRetry({
          campaign,
          catalogProducts: initialContextCandidates,
          marketplaceCode: catalogProfile.marketplaceCode,
          brandContext,
          model: NGRAM_MODEL_OVERRIDE || undefined,
          maxTokens: 2200,
        });
        let contextTokensIn = contextEvaluation.tokensIn;
        let contextTokensOut = contextEvaluation.tokensOut;
        let contextTokensTotal = contextEvaluation.tokensTotal;
        let contextModel = contextEvaluation.completion.model || "";
        if (
          !contextEvaluation.validated.matchedProduct &&
          contextEvaluation.validated.matchConfidence === "LOW" &&
          rankedCatalogCandidates.length > PURE_MODEL_CONTEXT_CANDIDATE_LIMIT
        ) {
          const expandedContextEvaluation = await evaluateCampaignWithPureModelValidationRetry({
            campaign,
            catalogProducts: rankedCatalogCandidates
              .slice(0, PURE_MODEL_CONTEXT_EXPANDED_CANDIDATE_LIMIT)
              .map((candidate) => candidate.product),
            marketplaceCode: catalogProfile.marketplaceCode,
            brandContext,
            model: NGRAM_MODEL_OVERRIDE || undefined,
            maxTokens: 2200,
          });
          contextEvaluation = expandedContextEvaluation;
          contextTokensIn += expandedContextEvaluation.tokensIn;
          contextTokensOut += expandedContextEvaluation.tokensOut;
          contextTokensTotal += expandedContextEvaluation.tokensTotal;
          contextModel = expandedContextEvaluation.completion.model || contextModel;
          contextPasses += 1;
        }

        let chunkTokensIn = contextTokensIn;
        let chunkTokensOut = contextTokensOut;
        let chunkTokensTotal = contextTokensTotal;
        let chunkModel = contextModel;
        let mergedTriage: ValidatedPureModelTermTriageResponse = {
          termRecommendations: [],
          exactNegatives: [],
          phraseNegatives: [],
          modelPrefills: { exact: [], mono: [], bi: [], tri: [] },
        };

        if (contextEvaluation.validated.matchedProduct) {
          const chunkValidated: ValidatedPureModelTermTriageResponse[] = [];

          for (const termChunk of termChunks) {
            const chunkEvaluation = await evaluateCampaignTermTriageWithValidationRetry({
              campaign,
              matchedProduct: contextEvaluation.validated.matchedProduct,
              terms: termChunk,
              marketplaceCode: catalogProfile.marketplaceCode,
              matchConfidence: contextEvaluation.validated.matchConfidence,
              matchReason: contextEvaluation.validated.matchReason,
              brandContext,
              model: NGRAM_MODEL_OVERRIDE || undefined,
              maxTokens: estimateNgramCampaignMaxTokens(termChunk.length),
            });

            chunkTokensIn += chunkEvaluation.tokensIn;
            chunkTokensOut += chunkEvaluation.tokensOut;
            chunkTokensTotal += chunkEvaluation.tokensTotal;
            chunkModel = chunkEvaluation.completion.model || chunkModel;
            chunkValidated.push(chunkEvaluation.validated);
          }

          mergedTriage = mergePureModelTermTriageResponses(chunkValidated);
        } else {
          mergedTriage = {
            termRecommendations: terms.map((term) => ({
              search_term: term.searchTerm,
              recommendation: "REVIEW",
              confidence: "LOW",
              reason_tag: "ambiguous_intent",
              rationale: contextEvaluation.validated.matchReason,
            })),
            exactNegatives: [],
            phraseNegatives: [],
            modelPrefills: { exact: [], mono: [], bi: [], tri: [] },
          };
        }

        pureModelEvaluation = {
          completion: {
            model: chunkModel,
          },
          context: contextEvaluation.validated,
          triage: mergedTriage,
          attempts: contextPasses + (contextEvaluation.validated.matchedProduct ? termChunks.length : 0),
          tokensIn: chunkTokensIn,
          tokensOut: chunkTokensOut,
          tokensTotal: chunkTokensTotal,
        };
      }

      const activeEvaluation = pureModelEvaluation ?? heuristicEvaluation;
      if (!activeEvaluation) {
        throw new Error(`${campaign.campaignName}: missing AI evaluation result.`);
      }

      tokensIn += activeEvaluation.tokensIn;
      tokensOut += activeEvaluation.tokensOut;
      tokensTotal += activeEvaluation.tokensTotal;
      model = activeEvaluation.completion.model || model;

      const validated = pureModelEvaluation
        ? {
            matchedProduct: pureModelEvaluation.context.matchedProduct,
            matchConfidence: pureModelEvaluation.context.matchConfidence,
            matchReason: pureModelEvaluation.context.matchReason,
            termRecommendations: pureModelEvaluation.triage.termRecommendations,
          }
        : heuristicEvaluation?.validated;
      if (!validated) {
        throw new Error(`${campaign.campaignName}: missing validated AI payload.`);
      }

      const lowConfidenceNoMatch = !validated.matchedProduct && validated.matchConfidence === "LOW";
      if (lowConfidenceNoMatch) {
        ambiguousCampaigns += 1;
        aiLowConfidenceCampaigns += 1;
      }

      const evaluations =
        lowConfidenceNoMatch && prefillStrategy !== "pure_model_single_campaign"
          ? []
          : validated.termRecommendations.map((evaluation, index) => {
            const term = terms[index];
            return {
              ...evaluation,
              spend: Number(term.spend.toFixed(2)),
              clicks: term.clicks,
              orders: term.orders,
              sales: Number(term.sales.toFixed(2)),
              keyword: term.keyword,
              keywordType: term.keywordType,
              targeting: term.targeting,
              matchType: term.matchType,
            };
          });

      const modelPrefills =
        pureModelEvaluation?.triage.modelPrefills ?? {
          exact: [],
          mono: [],
          bi: [],
          tri: [],
        };
      const phraseNegatives = pureModelEvaluation?.triage.phraseNegatives ?? [];

      previewResults.push({
        prefillStrategy,
        campaignName: campaign.campaignName,
        totalSpend: Number(campaign.totalSpend.toFixed(2)),
        eligibleSpend: Number(terms.reduce((sum, term) => sum + term.spend, 0).toFixed(2)),
        totalTerms: aggregatedTerms.filter((term) => term.campaignName === campaign.campaignName).length,
        eligibleTerms: terms.length,
        skippedBelowThresholdTerms,
        productIdentifier,
        theme,
        matchStatus: lowConfidenceNoMatch ? "ambiguous" : "matched",
        matchSource: lowConfidenceNoMatch ? "none" : "ai_combined",
        skipReason: null,
        matchedTitle: validated.matchedProduct?.productName ?? null,
        category: validated.matchedProduct?.category ?? null,
        itemDescription: validated.matchedProduct?.itemDescription ?? null,
        matchScore:
          validated.matchConfidence === "HIGH"
            ? 1
            : validated.matchConfidence === "MEDIUM"
              ? 0.75
              : null,
        synthesizedPrefills: lowConfidenceNoMatch
          ? { mono: [], bi: [], tri: [] }
          : synthesizeCampaignScratchpad(evaluations, spendThreshold),
        modelPrefills,
        phraseNegatives,
        evaluations,
      });
    }

    if (previewResults.length === 0) {
      warnings.push(
        candidateCampaigns.length > 0
          ? "No runnable campaigns were found after the current filters."
          : "No eligible campaigns were found above the selected spend threshold.",
      );
    }

    if (ambiguousCampaigns > 0) {
      warnings.push(
        `${ambiguousCampaigns} preview campaign(s) were flagged because AI could not confidently identify a single product.`,
      );
    }

    const recommendationCounts = previewResults.reduce(
      (counts, campaign) => {
        for (const evaluation of campaign.evaluations) {
          counts[evaluation.recommendation.toLowerCase() as "keep" | "negate" | "review"] += 1;
        }
        return counts;
      },
      { keep: 0, negate: 0, review: 0 },
    );

    const previewPayload = {
      run_mode: runMode,
      ad_product: adProduct,
      profile_id: profileId,
      date_from: dateFrom,
      date_to: dateTo,
      spend_threshold: spendThreshold,
      max_campaigns: runMode === "preview" && !hasRequestedCampaigns ? AI_PREFILL_PREVIEW_MAX_CAMPAIGNS : null,
      max_terms_per_campaign:
        runMode === "preview" && !hasRequestedCampaigns ? AI_PREFILL_PREVIEW_MAX_TERMS_PER_CAMPAIGN : null,
      raw_rows: rows.length,
      eligible_rows: usableRows.length,
      candidate_campaigns: candidateCampaigns.length,
      runnable_campaigns: runnableCampaigns.length,
      preview_campaigns: previewResults.length,
      selected_campaigns: requestedCampaignNames,
      ambiguous_campaigns: ambiguousCampaigns,
      intentionally_skipped_campaigns: intentionallySkippedCampaigns,
      recommendation_counts: recommendationCounts,
      prefill_strategy: prefillStrategy,
      model: model || null,
      prompt_version:
        expectedPromptVersion,
      campaigns: previewResults,
      warnings,
    };

    await logUsage({
      tool: "ngram",
      userId: user.id,
      stage: "ai_prefill_term_eval",
      promptTokens: tokensIn,
      completionTokens: tokensOut,
      totalTokens: tokensTotal,
      model: model || undefined,
      meta: {
        profile_id: profileId,
        ad_product: adProduct,
        date_from: dateFrom,
        date_to: dateTo,
        run_mode: runMode,
        prefill_strategy: prefillStrategy,
        spend_threshold: spendThreshold,
        selected_campaigns: requestedCampaignNames,
        preview_campaigns: previewResults.length,
        runnable_campaigns: runnableCampaigns.length,
        ambiguous_campaigns: ambiguousCampaigns,
        intentionally_skipped_campaigns: intentionallySkippedCampaigns,
        ai_low_confidence_campaigns: aiLowConfidenceCampaigns,
        catalog_products: catalogProducts.length,
        evaluated_terms: recommendationCounts.keep + recommendationCounts.negate + recommendationCounts.review,
      },
    });

    const persistedPreviewRun = await persistNgramPreviewRun({
      profileId,
      requestedByAuthUserId: user.id,
      adProduct,
      dateFrom,
      dateTo,
      spendThreshold,
      respectLegacyExclusions,
      model: model || null,
      promptVersion:
        expectedPromptVersion,
      promptTokens: tokensIn,
      completionTokens: tokensOut,
      totalTokens: tokensTotal,
      previewPayload,
    });

    return NextResponse.json({
      ok: true,
      preview_run_id: persistedPreviewRun?.id ?? null,
      preview_created_at: persistedPreviewRun?.createdAt ?? null,
      preview: previewPayload,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "AI prefill preview failed";
    await logAppError({
      tool: "ngram",
      route: "/api/ngram-2/ai-prefill-preview",
      method: "POST",
      statusCode: 500,
      userId: user.id,
      userEmail: user.email,
      message,
      meta:
        error instanceof NgramStructuredOutputValidationError
          ? {
              ...requestMeta,
              structured_output_failure: error.meta,
            }
          : requestMeta,
    });
    return NextResponse.json({ detail: message }, { status: 500 });
  }
}
