import { NextResponse } from "next/server";

import { logAppError } from "@/lib/ai/errorLogger";
import { persistNgramPreviewRun } from "@/lib/ai/ngramPreviewLogger";
import { logUsage } from "@/lib/ai/usageLogger";
import { createChatCompletion, parseJSONResponse } from "@/lib/composer/ai/openai";
import { buildCampaignPrompt, NGRAM_AI_PROMPT_VERSION } from "@/lib/ngram2/aiPrompt";
import {
  aggregateSearchTerms,
  AI_PREFILL_PREVIEW_MAX_CAMPAIGNS,
  AI_PREFILL_PREVIEW_MAX_TERMS_PER_CAMPAIGN,
  buildCampaignAggregates,
  isAsinQuery,
  isIntentionallySkippedCampaign,
  isLegacyExcludedCampaign,
  parseCampaignProductIdentifier,
  parseCampaignTheme,
  prepareAIPrefillCatalogProducts,
  synthesizeCampaignScratchpad,
  validateAIPrefillCampaignResponse,
  type AggregatedCampaign,
  type AggregatedSearchTerm,
  type AIPrefillCatalogProduct,
  type CampaignPrefillScratchpad,
  type NgramListingRow,
  type SearchTermFactRow,
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

type CampaignPreview = {
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
}> => {
  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null;
  const profileId = String(body?.profile_id || "").trim();
  const adProduct = String(body?.ad_product || "").trim().toUpperCase();
  const dateFrom = String(body?.date_from || "").trim();
  const dateTo = String(body?.date_to || "").trim();
  const spendThresholdRaw = Number(body?.spend_threshold ?? 0);

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

  return {
    profileId,
    adProduct,
    dateFrom,
    dateTo,
    spendThreshold: spendThresholdRaw,
    respectLegacyExclusions: body?.respect_legacy_exclusions !== false,
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

  try {
    const { profileId, adProduct, dateFrom, dateTo, spendThreshold, respectLegacyExclusions } =
      await coerceRequest(request);

    const warnings: string[] = [];

    const [{ profile: catalogProfile, listings, warning: catalogWarning }, rows] = await Promise.all([
      resolveCatalogListings(profileId),
      loadAllFactRows(profileId, adProduct, dateFrom, dateTo),
    ]);

    if (catalogWarning) {
      warnings.push(catalogWarning);
    }

    const catalogProducts = prepareAIPrefillCatalogProducts(listings);
    if (catalogProducts.length === 0) {
      throw new Error(
        "No active Windsor child ASIN catalog rows were found for this profile. Import Windsor listings for this marketplace before running AI preview.",
      );
    }

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

    const runnableCampaigns = candidateCampaigns.filter((campaign) => {
      const productIdentifier = parseCampaignProductIdentifier(campaign.campaignName);
      return Boolean(productIdentifier) && !isIntentionallySkippedCampaign(campaign.campaignName);
    });
    const intentionallySkippedCampaigns =
      candidateCampaigns.length - runnableCampaigns.length;
    const previewCampaigns = runnableCampaigns.slice(0, AI_PREFILL_PREVIEW_MAX_CAMPAIGNS);

    if (runnableCampaigns.length > AI_PREFILL_PREVIEW_MAX_CAMPAIGNS) {
      warnings.push(
        `Preview is limited to the top ${AI_PREFILL_PREVIEW_MAX_CAMPAIGNS} runnable campaigns by eligible spend.`,
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
      const terms = campaign.terms.slice(0, AI_PREFILL_PREVIEW_MAX_TERMS_PER_CAMPAIGN);
      const skippedBelowThresholdTerms = aggregatedTerms.filter(
        (term) => term.campaignName === campaign.campaignName && term.spend < spendThreshold,
      ).length;
      const productIdentifier = parseCampaignProductIdentifier(campaign.campaignName);
      const theme = parseCampaignTheme(campaign.campaignName);

      if (campaign.terms.length > AI_PREFILL_PREVIEW_MAX_TERMS_PER_CAMPAIGN) {
        warnings.push(
          `${campaign.campaignName}: preview only evaluates the top ${AI_PREFILL_PREVIEW_MAX_TERMS_PER_CAMPAIGN} terms by spend.`,
        );
      }

      const result = await createChatCompletion(
        buildCampaignPrompt(campaign, catalogProducts, terms, catalogProfile.marketplaceCode),
        {
        model: NGRAM_MODEL_OVERRIDE || undefined,
        maxTokens: 2200,
        },
      );

      tokensIn += result.tokensIn;
      tokensOut += result.tokensOut;
      tokensTotal += result.tokensTotal;
      model = result.model || model;

      const parsed = parseJSONResponse<Record<string, unknown>>(result.content || "{}");
      const validated = validateAIPrefillCampaignResponse(
        parsed,
        catalogProducts,
        terms.map((term) => term.searchTerm),
      );

      const lowConfidenceNoMatch = !validated.matchedProduct && validated.matchConfidence === "LOW";
      if (lowConfidenceNoMatch) {
        ambiguousCampaigns += 1;
        aiLowConfidenceCampaigns += 1;
      }

      const evaluations = lowConfidenceNoMatch
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

      previewResults.push({
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
        evaluations,
      });
    }

    if (previewResults.length === 0) {
      warnings.push(
        candidateCampaigns.length > 0
          ? "No runnable campaigns were found after skipping brand/mix/defensive lanes."
          : "No eligible campaigns were found above the selected spend threshold.",
      );
    }

    if (intentionallySkippedCampaigns > 0) {
      warnings.push(
        `${intentionallySkippedCampaigns} preview campaign(s) were intentionally skipped because they are brand/mix/defensive.`,
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
      ad_product: adProduct,
      profile_id: profileId,
      date_from: dateFrom,
      date_to: dateTo,
      spend_threshold: spendThreshold,
      max_campaigns: AI_PREFILL_PREVIEW_MAX_CAMPAIGNS,
      max_terms_per_campaign: AI_PREFILL_PREVIEW_MAX_TERMS_PER_CAMPAIGN,
      raw_rows: rows.length,
      eligible_rows: usableRows.length,
      candidate_campaigns: candidateCampaigns.length,
      preview_campaigns: previewResults.length,
      ambiguous_campaigns: ambiguousCampaigns,
      intentionally_skipped_campaigns: intentionallySkippedCampaigns,
      recommendation_counts: recommendationCounts,
      model: model || null,
      prompt_version: NGRAM_AI_PROMPT_VERSION,
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
        spend_threshold: spendThreshold,
        preview_campaigns: previewResults.length,
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
      promptVersion: NGRAM_AI_PROMPT_VERSION,
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
    });
    return NextResponse.json({ detail: message }, { status: 500 });
  }
}
