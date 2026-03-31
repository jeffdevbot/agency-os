import {
  createChatCompletion,
  parseJSONResponse,
  type ChatMessage,
  type ChatCompletionResult,
  type ResponseFormat,
} from "@/lib/composer/ai/openai";

import {
  validateAIPrefillCampaignResponse,
  type AggregatedCampaign,
  type AggregatedSearchTerm,
  type AIPrefillCatalogProduct,
  type ValidatedAIPrefillCampaignResponse,
} from "./aiPrefill";
import { buildCampaignPrompt } from "./aiPrompt";

const MAX_VALIDATION_ATTEMPTS = 3;
const MIN_RESPONSE_MAX_TOKENS = 2200;
const MAX_RESPONSE_MAX_TOKENS = 14000;
const RESPONSE_OVERHEAD_TOKENS = 800;
const RESPONSE_TOKENS_PER_TERM = 60;

const NGRAM_RESPONSE_FORMAT: ResponseFormat = {
  type: "json_schema",
  json_schema: {
    name: "ngram_campaign_prefill_response",
    strict: true,
    schema: {
      type: "object",
      additionalProperties: false,
      properties: {
        matched_product: {
          anyOf: [
            {
              type: "object",
              additionalProperties: false,
              properties: {
                child_asin: { type: "string" },
                child_sku: { anyOf: [{ type: "string" }, { type: "null" }] },
                product_name: { type: "string" },
              },
              required: ["child_asin", "child_sku", "product_name"],
            },
            { type: "null" },
          ],
        },
        match_confidence: {
          type: "string",
          enum: ["HIGH", "MEDIUM", "LOW"],
        },
        match_reason: { type: "string" },
        term_recommendations: {
          type: "array",
          items: {
            type: "object",
            additionalProperties: false,
            properties: {
              search_term: { type: "string" },
              recommendation: {
                type: "string",
                enum: ["KEEP", "NEGATE", "REVIEW"],
              },
              confidence: {
                type: "string",
                enum: ["HIGH", "MEDIUM", "LOW"],
              },
              reason_tag: {
                type: "string",
                enum: [
                  "core_use_case",
                  "wrong_category",
                  "wrong_product_form",
                  "wrong_size_variant",
                  "wrong_audience_theme",
                  "competitor_brand",
                  "cloth_primary_intent",
                  "accessory_only_intent",
                  "foreign_language",
                  "ambiguous_intent",
                ],
              },
              rationale: {
                anyOf: [{ type: "string" }, { type: "null" }],
              },
            },
            required: [
              "search_term",
              "recommendation",
              "confidence",
              "reason_tag",
              "rationale",
            ],
          },
        },
      },
      required: [
        "matched_product",
        "match_confidence",
        "match_reason",
        "term_recommendations",
      ],
    },
  },
};

const buildValidationRetryMessage = (errorMessage: string): ChatMessage => ({
  role: "user",
  content: [
    "Your previous response was invalid for this exact reason:",
    errorMessage,
    "",
    "Return the full JSON again.",
    "Every match_confidence and every term confidence must be exactly HIGH, MEDIUM, or LOW.",
    "Return one term_recommendation for every input search term exactly once.",
    "Do not omit any required fields.",
  ].join("\n"),
});

export const estimateNgramCampaignMaxTokens = (termCount: number): number => {
  const safeTermCount = Number.isFinite(termCount) ? Math.max(0, Math.floor(termCount)) : 0;
  return Math.min(
    MAX_RESPONSE_MAX_TOKENS,
    Math.max(
      MIN_RESPONSE_MAX_TOKENS,
      RESPONSE_OVERHEAD_TOKENS + safeTermCount * RESPONSE_TOKENS_PER_TERM,
    ),
  );
};

export const evaluateCampaignWithValidationRetry = async ({
  campaign,
  catalogProducts,
  terms,
  marketplaceCode,
  model,
  maxTokens,
}: {
  campaign: AggregatedCampaign;
  catalogProducts: AIPrefillCatalogProduct[];
  terms: AggregatedSearchTerm[];
  marketplaceCode: string | null;
  model?: string;
  maxTokens: number;
}): Promise<{
  completion: ChatCompletionResult;
  validated: ValidatedAIPrefillCampaignResponse;
  attempts: number;
  tokensIn: number;
  tokensOut: number;
  tokensTotal: number;
}> => {
  const baseMessages = buildCampaignPrompt(campaign, catalogProducts, terms, marketplaceCode);
  let tokensIn = 0;
  let tokensOut = 0;
  let tokensTotal = 0;
  let lastError: Error | null = null;
  let lastContent: string | null = null;

  for (let attempt = 1; attempt <= MAX_VALIDATION_ATTEMPTS; attempt += 1) {
    const messages =
      attempt === 1
        ? baseMessages
        : [
            ...baseMessages,
            {
              role: "assistant" as const,
              content: lastContent || "{}",
            },
            buildValidationRetryMessage(lastError?.message || "Unknown validation error"),
          ];

    const completion = await createChatCompletion(messages, {
      model,
      maxTokens,
      responseFormat: NGRAM_RESPONSE_FORMAT,
    });

    if (completion.refusal) {
      throw new Error(`${campaign.campaignName}: model refused structured output: ${completion.refusal}`);
    }

    tokensIn += completion.tokensIn;
    tokensOut += completion.tokensOut;
    tokensTotal += completion.tokensTotal;
    lastContent = completion.content ?? "{}";

    try {
      const parsed = parseJSONResponse<Record<string, unknown>>(completion.content || "{}");
      const validated = validateAIPrefillCampaignResponse(
        parsed,
        catalogProducts,
        terms.map((term) => term.searchTerm),
      );

      return {
        completion,
        validated,
        attempts: attempt,
        tokensIn,
        tokensOut,
        tokensTotal,
      };
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
      if (attempt === MAX_VALIDATION_ATTEMPTS) {
        throw new Error(
          `${campaign.campaignName}: AI response validation failed after ${MAX_VALIDATION_ATTEMPTS} attempts: ${lastError.message}`,
        );
      }
    }
  }

  throw new Error(`${campaign.campaignName}: AI response validation failed.`);
};
