import {
  createChatCompletion,
  parseJSONResponse,
  type ChatMessage,
  type ChatCompletionResult,
  type ResponseFormat,
} from "@/lib/composer/ai/openai";
import { logAppError } from "@/lib/ai/errorLogger";

import {
  validateAIPrefillCampaignResponse,
  validatePureModelContextResponse,
  validatePureModelTermTriageResponse,
  type AggregatedCampaign,
  type AggregatedSearchTerm,
  type AIPrefillBrandContext,
  type AIPrefillCatalogProduct,
  type ValidatedAIPrefillCampaignResponse,
  type ValidatedPureModelContextResponse,
  type ValidatedPureModelTermTriageResponse,
} from "./aiPrefill";
import type { NgramLanguageCode } from "./languages";
import {
  buildCampaignPrompt,
  buildPureModelContextPrompt,
  buildPureModelTermTriagePrompt,
} from "./aiPrompt";

const MAX_VALIDATION_ATTEMPTS = 3;
const MIN_RESPONSE_MAX_TOKENS = 2200;
const MAX_RESPONSE_MAX_TOKENS = 14000;
const RESPONSE_OVERHEAD_TOKENS = 800;
const RESPONSE_TOKENS_PER_TERM = 60;

export class NgramStructuredOutputValidationError extends Error {
  readonly meta: Record<string, unknown>;

  constructor(message: string, meta: Record<string, unknown>) {
    super(message);
    this.name = "NgramStructuredOutputValidationError";
    this.meta = meta;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

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

const NGRAM_PURE_MODEL_CONTEXT_RESPONSE_FORMAT: ResponseFormat = {
  type: "json_schema",
  json_schema: {
    name: "ngram_campaign_context_response",
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
      },
      required: [
        "matched_product",
        "match_confidence",
        "match_reason",
      ],
    },
  },
};

const NGRAM_PURE_MODEL_TERM_TRIAGE_RESPONSE_FORMAT: ResponseFormat = {
  type: "json_schema",
  json_schema: {
    name: "ngram_campaign_term_triage_response",
    strict: true,
    schema: {
      type: "object",
      additionalProperties: false,
      properties: {
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
        exact_negatives: {
          type: "array",
          items: { type: "string" },
        },
        phrase_negatives: {
          type: "array",
          items: {
            type: "object",
            additionalProperties: false,
            properties: {
              phrase: { type: "string" },
              bucket: {
                type: "string",
                enum: ["mono", "bi", "tri"],
              },
              confidence: {
                type: "string",
                enum: ["HIGH", "MEDIUM", "LOW"],
              },
              source_terms: {
                type: "array",
                items: { type: "string" },
              },
              rationale: {
                anyOf: [{ type: "string" }, { type: "null" }],
              },
            },
            required: ["phrase", "bucket", "confidence", "source_terms", "rationale"],
          },
        },
      },
      required: [
        "term_recommendations",
        "exact_negatives",
        "phrase_negatives",
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

const buildPureModelContextValidationRetryMessage = (errorMessage: string): ChatMessage => ({
  role: "user",
  content: [
    "Your previous response was invalid for this exact reason:",
    errorMessage,
    "",
    "Return the full JSON again.",
    "match_confidence must be exactly HIGH, MEDIUM, or LOW.",
    "matched_product must either be a valid catalog row or null.",
    "Do not omit any required fields.",
  ].join("\n"),
});

const buildPureModelTermTriageValidationRetryMessage = (errorMessage: string): ChatMessage => ({
  role: "user",
  content: [
    "Your previous response was invalid for this exact reason:",
    errorMessage,
    "",
    "Return the full JSON again.",
    "Every match_confidence and every term confidence must be exactly HIGH, MEDIUM, or LOW.",
    "Return one term_recommendation for every input search term exactly once.",
    "exact_negatives must only reference exact input search terms.",
    "phrase_negatives must use only mono, bi, or tri buckets and each source_terms entry must reference a NEGATE input search term.",
    "Do not omit any required fields.",
  ].join("\n"),
});

const measurePromptChars = (messages: ChatMessage[]): number =>
  messages.reduce((sum, message) => sum + message.content.length, 0);

const buildAttemptDiagnostic = ({
  attempt,
  messages,
  completion,
  errorMessage,
  maxTokens,
}: {
  attempt: number;
  messages: ChatMessage[];
  completion: ChatCompletionResult;
  errorMessage: string;
  maxTokens: number;
}): Record<string, unknown> => ({
  attempt,
  prompt_chars: measurePromptChars(messages),
  response_chars: (completion.content || "").length,
  max_tokens: maxTokens,
  finish_reason: completion.finishReason ?? null,
  model: completion.model,
  tokens_in: completion.tokensIn,
  tokens_out: completion.tokensOut,
  tokens_total: completion.tokensTotal,
  duration_ms: completion.durationMs,
  validation_error: errorMessage,
  response_content: completion.content,
});

const logStructuredOutputFailure = async ({
  stage,
  campaign,
  marketplaceCode,
  maxTokens,
  diagnostics,
  meta,
}: {
  stage: "combined_campaign" | "pure_model_context" | "pure_model_term_triage";
  campaign: AggregatedCampaign;
  marketplaceCode: string | null;
  maxTokens: number;
  diagnostics: Record<string, unknown>[];
  meta?: Record<string, unknown>;
}): Promise<void> => {
  await logAppError({
    tool: "ngram",
    severity: "error",
    message: `${campaign.campaignName}: structured output validation failed`,
    meta: {
      evaluator_stage: stage,
      campaign_name: campaign.campaignName,
      campaign_total_spend: campaign.totalSpend,
      campaign_term_count: campaign.termCount,
      marketplace_code: marketplaceCode,
      max_tokens: maxTokens,
      attempt_diagnostics: diagnostics,
      ...(meta ?? {}),
    },
  });
};

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
  allowedLanguages,
  disableLanguageNegation,
  brandContext,
  model,
  maxTokens,
}: {
  campaign: AggregatedCampaign;
  catalogProducts: AIPrefillCatalogProduct[];
  terms: AggregatedSearchTerm[];
  marketplaceCode: string | null;
  allowedLanguages: NgramLanguageCode[];
  disableLanguageNegation: boolean;
  brandContext?: AIPrefillBrandContext;
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
  const baseMessages = buildCampaignPrompt(
    campaign,
    catalogProducts,
    terms,
    marketplaceCode,
    allowedLanguages,
    disableLanguageNegation,
    brandContext,
  );
  let tokensIn = 0;
  let tokensOut = 0;
  let tokensTotal = 0;
  let lastError: Error | null = null;
  let lastContent: string | null = null;
  const diagnostics: Record<string, unknown>[] = [];

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
      diagnostics.push(
        buildAttemptDiagnostic({
          attempt,
          messages,
          completion,
          errorMessage: lastError.message,
          maxTokens,
        }),
      );
      if (attempt === MAX_VALIDATION_ATTEMPTS) {
        await logStructuredOutputFailure({
          stage: "combined_campaign",
          campaign,
          marketplaceCode,
          maxTokens,
          diagnostics,
          meta: {
            catalog_product_count: catalogProducts.length,
            term_count: terms.length,
            response_format_name: NGRAM_RESPONSE_FORMAT.json_schema.name,
          },
        });
        throw new NgramStructuredOutputValidationError(
          `${campaign.campaignName}: AI response validation failed after ${MAX_VALIDATION_ATTEMPTS} attempts: ${lastError.message}`,
          {
            evaluator_stage: "combined_campaign",
            campaign_name: campaign.campaignName,
            campaign_total_spend: campaign.totalSpend,
            campaign_term_count: campaign.termCount,
            marketplace_code: marketplaceCode,
            max_tokens: maxTokens,
            catalog_product_count: catalogProducts.length,
            term_count: terms.length,
            response_format_name: NGRAM_RESPONSE_FORMAT.json_schema.name,
            attempt_diagnostics: diagnostics,
          },
        );
      }
    }
  }

  throw new Error(`${campaign.campaignName}: AI response validation failed.`);
};

export const evaluateCampaignWithPureModelValidationRetry = async ({
  campaign,
  catalogProducts,
  marketplaceCode,
  allowedLanguages,
  disableLanguageNegation,
  brandContext,
  model,
  maxTokens,
}: {
  campaign: AggregatedCampaign;
  catalogProducts: AIPrefillCatalogProduct[];
  marketplaceCode: string | null;
  allowedLanguages: NgramLanguageCode[];
  disableLanguageNegation: boolean;
  brandContext?: AIPrefillBrandContext;
  model?: string;
  maxTokens: number;
}): Promise<{
  completion: ChatCompletionResult;
  validated: ValidatedPureModelContextResponse;
  attempts: number;
  tokensIn: number;
  tokensOut: number;
  tokensTotal: number;
}> => {
  const baseMessages = buildPureModelContextPrompt(
    campaign,
    catalogProducts,
    marketplaceCode,
    allowedLanguages,
    disableLanguageNegation,
    brandContext,
  );
  let tokensIn = 0;
  let tokensOut = 0;
  let tokensTotal = 0;
  let lastError: Error | null = null;
  let lastContent: string | null = null;
  const diagnostics: Record<string, unknown>[] = [];

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
            buildPureModelContextValidationRetryMessage(lastError?.message || "Unknown validation error"),
          ];

    const completion = await createChatCompletion(messages, {
      model,
      maxTokens,
      responseFormat: NGRAM_PURE_MODEL_CONTEXT_RESPONSE_FORMAT,
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
      const validated = validatePureModelContextResponse(parsed, catalogProducts);

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
      diagnostics.push(
        buildAttemptDiagnostic({
          attempt,
          messages,
          completion,
          errorMessage: lastError.message,
          maxTokens,
        }),
      );
      if (attempt === MAX_VALIDATION_ATTEMPTS) {
        await logStructuredOutputFailure({
          stage: "pure_model_context",
          campaign,
          marketplaceCode,
          maxTokens,
          diagnostics,
          meta: {
            catalog_product_count: catalogProducts.length,
            response_format_name: NGRAM_PURE_MODEL_CONTEXT_RESPONSE_FORMAT.json_schema.name,
          },
        });
        throw new NgramStructuredOutputValidationError(
          `${campaign.campaignName}: AI response validation failed after ${MAX_VALIDATION_ATTEMPTS} attempts: ${lastError.message}`,
          {
            evaluator_stage: "pure_model_context",
            campaign_name: campaign.campaignName,
            campaign_total_spend: campaign.totalSpend,
            campaign_term_count: campaign.termCount,
            marketplace_code: marketplaceCode,
            max_tokens: maxTokens,
            catalog_product_count: catalogProducts.length,
            response_format_name: NGRAM_PURE_MODEL_CONTEXT_RESPONSE_FORMAT.json_schema.name,
            attempt_diagnostics: diagnostics,
          },
        );
      }
    }
  }

  throw new Error(`${campaign.campaignName}: AI response validation failed.`);
};

export const evaluateCampaignTermTriageWithValidationRetry = async ({
  campaign,
  matchedProduct,
  terms,
  marketplaceCode,
  allowedLanguages,
  disableLanguageNegation,
  matchConfidence,
  matchReason,
  brandContext,
  model,
  maxTokens,
}: {
  campaign: AggregatedCampaign;
  matchedProduct: AIPrefillCatalogProduct;
  terms: AggregatedSearchTerm[];
  marketplaceCode: string | null;
  allowedLanguages: NgramLanguageCode[];
  disableLanguageNegation: boolean;
  matchConfidence: "HIGH" | "MEDIUM" | "LOW";
  matchReason: string;
  brandContext?: AIPrefillBrandContext;
  model?: string;
  maxTokens: number;
}): Promise<{
  completion: ChatCompletionResult;
  validated: ValidatedPureModelTermTriageResponse;
  attempts: number;
  tokensIn: number;
  tokensOut: number;
  tokensTotal: number;
}> => {
  const baseMessages = buildPureModelTermTriagePrompt(
    campaign,
    matchedProduct,
    terms,
    marketplaceCode,
    allowedLanguages,
    disableLanguageNegation,
    matchConfidence,
    matchReason,
    brandContext,
  );
  let tokensIn = 0;
  let tokensOut = 0;
  let tokensTotal = 0;
  let lastError: Error | null = null;
  let lastContent: string | null = null;
  const diagnostics: Record<string, unknown>[] = [];

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
            buildPureModelTermTriageValidationRetryMessage(lastError?.message || "Unknown validation error"),
          ];

    const completion = await createChatCompletion(messages, {
      model,
      maxTokens,
      responseFormat: NGRAM_PURE_MODEL_TERM_TRIAGE_RESPONSE_FORMAT,
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
      const validated = validatePureModelTermTriageResponse(
        parsed,
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
      diagnostics.push(
        buildAttemptDiagnostic({
          attempt,
          messages,
          completion,
          errorMessage: lastError.message,
          maxTokens,
        }),
      );
      if (attempt === MAX_VALIDATION_ATTEMPTS) {
        await logStructuredOutputFailure({
          stage: "pure_model_term_triage",
          campaign,
          marketplaceCode,
          maxTokens,
          diagnostics,
          meta: {
            matched_product_child_asin: matchedProduct.childAsin,
            match_confidence: matchConfidence,
            response_format_name: NGRAM_PURE_MODEL_TERM_TRIAGE_RESPONSE_FORMAT.json_schema.name,
            term_count: terms.length,
          },
        });
        throw new NgramStructuredOutputValidationError(
          `${campaign.campaignName}: AI response validation failed after ${MAX_VALIDATION_ATTEMPTS} attempts: ${lastError.message}`,
          {
            evaluator_stage: "pure_model_term_triage",
            campaign_name: campaign.campaignName,
            campaign_total_spend: campaign.totalSpend,
            campaign_term_count: campaign.termCount,
            marketplace_code: marketplaceCode,
            max_tokens: maxTokens,
            matched_product_child_asin: matchedProduct.childAsin,
            match_confidence: matchConfidence,
            response_format_name: NGRAM_PURE_MODEL_TERM_TRIAGE_RESPONSE_FORMAT.json_schema.name,
            term_count: terms.length,
            attempt_diagnostics: diagnostics,
          },
        );
      }
    }
  }

  throw new Error(`${campaign.campaignName}: AI response validation failed.`);
};
