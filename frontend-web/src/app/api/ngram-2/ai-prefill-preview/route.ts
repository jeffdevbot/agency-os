import { NextResponse } from "next/server";

import { logAppError } from "@/lib/ai/errorLogger";
import { logUsage } from "@/lib/ai/usageLogger";
import { createChatCompletion, parseJSONResponse, type ChatMessage } from "@/lib/composer/ai/openai";
import { createSupabaseRouteClient, createSupabaseServiceClient } from "@/lib/supabase/serverClient";
import {
  aggregateSearchTerms,
  AI_PREFILL_PREVIEW_MAX_CAMPAIGNS,
  AI_PREFILL_PREVIEW_MAX_TERMS_PER_CAMPAIGN,
  buildPreparedListingCatalog,
  buildCampaignAggregates,
  chooseBestListingMatch,
  isAsinQuery,
  isLegacyExcludedCampaign,
  synthesizeCampaignScratchpad,
  type AggregatedCampaign,
  type AggregatedSearchTerm,
  type CampaignPrefillScratchpad,
  type NgramListingRow,
  type SearchTermFactRow,
} from "@/lib/ngram2/aiPrefill";

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
  "child_product_name",
  "parent_title",
  "category",
  "item_description",
].join(",");

const MAX_BATCH_SIZE = 1000;
const SUPPORTED_AD_PRODUCT = "SPONSORED_PRODUCTS";

type NormalizedRecommendation = "KEEP" | "NEGATE" | "REVIEW";
type NormalizedConfidence = "HIGH" | "MEDIUM" | "LOW";

type ParsedAiEvaluation = {
  search_term: string;
  recommendation: NormalizedRecommendation;
  confidence: NormalizedConfidence;
  reason_tag: string;
  rationale: string | null;
};

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
  matchSource: "deterministic" | "ai_fallback" | "none";
  skipReason: "brand_mix_defensive" | "missing_identifier" | null;
  matchedTitle: string | null;
  category: string | null;
  itemDescription: string | null;
  matchScore: number | null;
  synthesizedPrefills: CampaignPrefillScratchpad;
  evaluations: Array<
    ParsedAiEvaluation & {
      spend: number;
      clicks: number;
      orders: number;
      sales: number;
      keyword: string | null;
      keywordType: string | null;
      targeting: string | null;
      matchType: string | null;
    }
  >;
};

const SYSTEM_PROMPT = `You evaluate Amazon Sponsored Products shopper queries for N-Gram negative recommendation prefill.

Return strict JSON with this shape:
{
  "evaluations": [
    {
      "search_term": "string",
      "recommendation": "KEEP" | "NEGATE" | "REVIEW",
      "confidence": "HIGH" | "MEDIUM" | "LOW",
      "reason_tag": "snake_case_or_short_slug",
      "rationale": "one short sentence"
    }
  ]
}

Rules:
- Judge each search term in the context of both the product and the campaign theme.
- KEEP means the term is relevant and should not be prefilled as a negative.
- NEGATE means the term is clearly irrelevant or wrong-fit for this campaign/product.
- REVIEW means mixed, ambiguous, low-signal, or context-dependent.
- Use REVIEW instead of forcing a weak NEGATE.
- Prefer compact reason tags like competitor_brand, wrong_category, travel_size_mismatch, accessories_intent, core_use_case, foreign_language.
- Return one evaluation for every input search term and preserve the exact search_term text.
- Do not include markdown or explanation outside the JSON object.`;

const PRODUCT_MATCH_SYSTEM_PROMPT = `You disambiguate Amazon Ads campaign product identifiers against a short candidate list of listing titles.

Return strict JSON with this shape:
{
  "selected_title": "exact candidate title or null",
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "ambiguous": true | false,
  "rationale": "one short sentence"
}

Rules:
- Choose only from the provided candidate titles.
- Use the campaign identifier segment as the primary anchor.
- Prefer exact family-level resolution, not loose semantic similarity.
- If the best choice is uncertain, set ambiguous=true and selected_title=null.
- Do not invent a title that is not in the candidate list.
- Do not include markdown or explanation outside the JSON object.`;

const normalizeRecommendation = (value: unknown): NormalizedRecommendation => {
  const normalized = String(value || "").trim().toUpperCase();
  if (normalized === "KEEP" || normalized === "NEGATE" || normalized === "REVIEW") {
    return normalized;
  }
  return "REVIEW";
};

const normalizeConfidence = (value: unknown): NormalizedConfidence => {
  const normalized = String(value || "").trim().toUpperCase();
  if (normalized === "HIGH" || normalized === "MEDIUM" || normalized === "LOW") {
    return normalized;
  }
  return "LOW";
};

const toReasonTag = (value: unknown): string => {
  const raw = String(value || "").trim().toLowerCase();
  if (!raw) return "review_needed";
  return raw.replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 48) || "review_needed";
};

const toRationale = (value: unknown): string | null => {
  const raw = String(value || "").trim();
  return raw ? raw.slice(0, 240) : null;
};

const buildCampaignPrompt = (
  campaign: AggregatedCampaign,
  match: ReturnType<typeof chooseBestListingMatch>,
  terms: AggregatedSearchTerm[],
): ChatMessage[] => [
  { role: "system", content: SYSTEM_PROMPT },
  {
    role: "user",
    content: JSON.stringify(
      {
        campaign_name: campaign.campaignName,
        campaign_theme: match.theme,
        product_identifier: match.identifier,
        matched_product: {
          title: match.matchedTitle,
          category: match.category,
          item_description: match.itemDescription,
        },
        search_terms: terms.map((term) => ({
          search_term: term.searchTerm,
          impressions: term.impressions,
          clicks: term.clicks,
          spend: Number(term.spend.toFixed(2)),
          orders: term.orders,
          sales: Number(term.sales.toFixed(2)),
          keyword: term.keyword,
          keyword_type: term.keywordType,
          targeting: term.targeting,
          match_type: term.matchType,
        })),
      },
      null,
      2,
    ),
  },
];

const buildProductMatchPrompt = (
  _campaignName: string,
  match: ReturnType<typeof chooseBestListingMatch>,
): ChatMessage[] => [
  { role: "system", content: PRODUCT_MATCH_SYSTEM_PROMPT },
  {
    role: "user",
    content: JSON.stringify(
      {
        campaign_identifier_segment: match.identifier,
        candidates: match.candidates.slice(0, 3).map((candidate) => ({
          title: candidate.title,
          item_description: candidate.itemDescription,
        })),
      },
      null,
      2,
    ),
  },
];

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

const applyProductMatchFallback = async (
  campaignName: string,
  match: ReturnType<typeof chooseBestListingMatch>,
): Promise<{
  match: ReturnType<typeof chooseBestListingMatch>;
  usage: { tokensIn: number; tokensOut: number; tokensTotal: number; model: string };
}> => {
  if (match.status !== "ambiguous" || match.candidates.length < 2) {
    return {
      match,
      usage: { tokensIn: 0, tokensOut: 0, tokensTotal: 0, model: "" },
    };
  }

  const result = await createChatCompletion(buildProductMatchPrompt(campaignName, match), {
    temperature: 0,
    maxTokens: 300,
  });

  const parsed = parseJSONResponse<{
    selected_title?: string | null;
    confidence?: string | null;
    ambiguous?: boolean | null;
  }>(result.content || "{}");

  const ambiguous = Boolean(parsed.ambiguous);
  const selectedTitle = String(parsed.selected_title || "").trim();
  const confidence = normalizeConfidence(parsed.confidence);

  if (ambiguous || !selectedTitle || confidence === "LOW") {
    return {
      match,
      usage: {
        tokensIn: result.tokensIn,
        tokensOut: result.tokensOut,
        tokensTotal: result.tokensTotal,
        model: result.model,
      },
    };
  }

  const candidate = match.candidates.find((item) => item.title === selectedTitle);
  if (!candidate) {
    return {
      match,
      usage: {
        tokensIn: result.tokensIn,
        tokensOut: result.tokensOut,
        tokensTotal: result.tokensTotal,
        model: result.model,
      },
    };
  }

  return {
    match: {
      ...match,
      status: "matched",
      matchedTitle: candidate.title,
      category: candidate.category,
      itemDescription: candidate.itemDescription,
      score: candidate.score,
      matchSource: "ai_fallback",
    },
    usage: {
      tokensIn: result.tokensIn,
      tokensOut: result.tokensOut,
      tokensTotal: result.tokensTotal,
      model: result.model,
    },
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

    const [rows, listings] = await Promise.all([
      loadAllFactRows(profileId, adProduct, dateFrom, dateTo),
      loadListings(profileId),
    ]);
    const listingCatalog = buildPreparedListingCatalog(listings);

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

    const previewCampaigns = candidateCampaigns.slice(0, AI_PREFILL_PREVIEW_MAX_CAMPAIGNS);

    const warnings: string[] = [];
    if (candidateCampaigns.length > AI_PREFILL_PREVIEW_MAX_CAMPAIGNS) {
      warnings.push(
        `Preview is limited to the top ${AI_PREFILL_PREVIEW_MAX_CAMPAIGNS} campaigns by eligible spend.`,
      );
    }

    let tokensIn = 0;
    let tokensOut = 0;
    let tokensTotal = 0;
    let model = "";

    const previewResults: CampaignPreview[] = [];
    let ambiguousCampaigns = 0;
    let intentionallySkippedCampaigns = 0;
    let aiMatchFallbackCalls = 0;

    for (const campaign of previewCampaigns) {
      let match = chooseBestListingMatch(campaign.campaignName, listingCatalog);
      const terms = campaign.terms.slice(0, AI_PREFILL_PREVIEW_MAX_TERMS_PER_CAMPAIGN);
      const skippedBelowThresholdTerms = aggregatedTerms.filter(
        (term) => term.campaignName === campaign.campaignName && term.spend < spendThreshold,
      ).length;

      if (campaign.terms.length > AI_PREFILL_PREVIEW_MAX_TERMS_PER_CAMPAIGN) {
        warnings.push(
          `${campaign.campaignName}: preview only evaluates the top ${AI_PREFILL_PREVIEW_MAX_TERMS_PER_CAMPAIGN} terms by spend.`,
        );
      }

      if (match.status === "ambiguous" && match.candidates.length >= 2) {
        aiMatchFallbackCalls += 1;
        const fallback = await applyProductMatchFallback(campaign.campaignName, match);
        match = fallback.match;
        tokensIn += fallback.usage.tokensIn;
        tokensOut += fallback.usage.tokensOut;
        tokensTotal += fallback.usage.tokensTotal;
        model = fallback.usage.model || model;
      }

      if (match.status !== "matched") {
        if (match.status === "intentionally_skipped") {
          intentionallySkippedCampaigns += 1;
        } else {
          ambiguousCampaigns += 1;
        }
        previewResults.push({
          campaignName: campaign.campaignName,
          totalSpend: Number(campaign.totalSpend.toFixed(2)),
          eligibleSpend: Number(terms.reduce((sum, term) => sum + term.spend, 0).toFixed(2)),
          totalTerms: aggregatedTerms.filter((term) => term.campaignName === campaign.campaignName).length,
          eligibleTerms: terms.length,
          skippedBelowThresholdTerms,
          productIdentifier: match.identifier,
          theme: match.theme,
          matchStatus: match.status,
          matchSource: match.matchSource,
          skipReason: match.skipReason,
          matchedTitle: match.matchedTitle,
          category: match.category,
          itemDescription: match.itemDescription,
          matchScore: match.score,
          synthesizedPrefills: { mono: [], bi: [], tri: [] },
          evaluations: [],
        });
        continue;
      }

      const result = await createChatCompletion(buildCampaignPrompt(campaign, match, terms), {
        temperature: 0.1,
        maxTokens: 1400,
      });

      tokensIn += result.tokensIn;
      tokensOut += result.tokensOut;
      tokensTotal += result.tokensTotal;
      model = result.model || model;

      const parsed = parseJSONResponse<{ evaluations?: Array<Record<string, unknown>> }>(result.content || "{}");
      const byTerm = new Map<string, ParsedAiEvaluation>();
      for (const evaluation of parsed.evaluations || []) {
        const searchTerm = String(evaluation.search_term || "").trim();
        if (!searchTerm) continue;
        byTerm.set(searchTerm.toLowerCase(), {
          search_term: searchTerm,
          recommendation: normalizeRecommendation(evaluation.recommendation),
          confidence: normalizeConfidence(evaluation.confidence),
          reason_tag: toReasonTag(evaluation.reason_tag),
          rationale: toRationale(evaluation.rationale),
        });
      }

      const evaluations = terms.map((term) => {
        const fallback = byTerm.get(term.searchTerm.toLowerCase()) || {
          search_term: term.searchTerm,
          recommendation: "REVIEW" as const,
          confidence: "LOW" as const,
          reason_tag: "no_ai_output",
          rationale: "Model did not return a structured evaluation for this term.",
        };

        return {
          ...fallback,
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
        productIdentifier: match.identifier,
        theme: match.theme,
        matchStatus: match.status,
        matchSource: match.matchSource,
        skipReason: match.skipReason,
        matchedTitle: match.matchedTitle,
        category: match.category,
        itemDescription: match.itemDescription,
        matchScore: match.score,
        synthesizedPrefills: synthesizeCampaignScratchpad(evaluations, spendThreshold),
        evaluations,
      });
    }

    if (previewResults.length === 0) {
      warnings.push("No eligible campaigns were found above the selected spend threshold.");
    }

    if (intentionallySkippedCampaigns > 0) {
      warnings.push(
        `${intentionallySkippedCampaigns} preview campaign(s) were intentionally skipped because they are brand/mix/defensive.`,
      );
    }

    if (ambiguousCampaigns > 0) {
      warnings.push(
        `${ambiguousCampaigns} preview campaign(s) remain unresolved after deterministic and fallback product matching.`,
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
        ai_match_fallback_calls: aiMatchFallbackCalls,
        evaluated_terms: recommendationCounts.keep + recommendationCounts.negate + recommendationCounts.review,
      },
    });

    return NextResponse.json({
      ok: true,
      preview: {
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
        campaigns: previewResults,
        warnings,
      },
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
