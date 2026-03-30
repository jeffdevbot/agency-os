import {
  createChatCompletion,
  parseJSONResponse,
  type ChatMessage,
  type ChatCompletionResult,
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
    });

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
