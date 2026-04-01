import { describe, expect, it, vi, afterEach } from "vitest";

vi.mock("server-only", () => ({}));

import {
  estimateNgramCampaignMaxTokens,
  evaluateCampaignWithValidationRetry,
  evaluateCampaignTermTriageWithValidationRetry,
  evaluateCampaignWithPureModelValidationRetry,
} from "./aiCampaignEvaluator";
import type { AIPrefillCatalogProduct, AggregatedCampaign, AggregatedSearchTerm } from "./aiPrefill";
import * as openaiModule from "@/lib/composer/ai/openai";

describe("evaluateCampaignWithValidationRetry", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("sizes completion budget for large full-run campaigns", () => {
    expect(estimateNgramCampaignMaxTokens(1)).toBe(2200);
    expect(estimateNgramCampaignMaxTokens(20)).toBe(2200);
    expect(estimateNgramCampaignMaxTokens(176)).toBe(11360);
    expect(estimateNgramCampaignMaxTokens(1000)).toBe(14000);
  });

  it("retries when the model returns invalid confidence fields", async () => {
    const campaign: AggregatedCampaign = {
      campaignName: "Screen Shine - Duo | SPA | Cls. | Rsrch",
      totalSpend: 10,
      termCount: 1,
      terms: [],
    };
    const catalogProducts: AIPrefillCatalogProduct[] = [
      {
        childAsin: "A1",
        childSku: "DUO-1",
        productName: "WHOOSH! Screen Shine Duo",
        category: "electronics cleaner",
        itemDescription: "spray plus cloth",
      },
    ];
    const terms: AggregatedSearchTerm[] = [
      {
        campaignName: campaign.campaignName,
        searchTerm: "laptop cloth",
        impressions: 100,
        clicks: 10,
        spend: 5,
        orders: 0,
        sales: 0,
        keyword: "laptop cloth",
        keywordType: "BROAD",
        targeting: null,
        matchType: "broad",
      },
    ];

    vi.spyOn(openaiModule, "createChatCompletion")
      .mockResolvedValueOnce({
        content: JSON.stringify({
          matched_product: {
            child_asin: "A1",
            child_sku: "DUO-1",
            product_name: "WHOOSH! Screen Shine Duo",
          },
          match_confidence: "",
          match_reason: "bad draft",
          term_recommendations: [
            {
              search_term: "laptop cloth",
              recommendation: "NEGATE",
              confidence: "",
              reason_tag: "accessory_only_intent",
              rationale: "standalone cloth query",
            },
          ],
        }),
        tokensIn: 100,
        tokensOut: 20,
        tokensTotal: 120,
        model: "gpt-5.4-2026-03-05",
        durationMs: 1,
      })
      .mockResolvedValueOnce({
        content: JSON.stringify({
          matched_product: {
            child_asin: "A1",
            child_sku: "DUO-1",
            product_name: "WHOOSH! Screen Shine Duo",
          },
          match_confidence: "HIGH",
          match_reason: "valid retry",
          term_recommendations: [
            {
              search_term: "laptop cloth",
              recommendation: "NEGATE",
              confidence: "HIGH",
              reason_tag: "accessory_only_intent",
              rationale: "standalone cloth query",
            },
          ],
        }),
        tokensIn: 120,
        tokensOut: 30,
        tokensTotal: 150,
        model: "gpt-5.4-2026-03-05",
        durationMs: 1,
      });

    const result = await evaluateCampaignWithValidationRetry({
      campaign,
      catalogProducts,
      terms,
      marketplaceCode: "CA",
      model: "gpt-5.4-2026-03-05",
      maxTokens: 2200,
    });

    expect(result.attempts).toBe(2);
    expect(result.tokensIn).toBe(220);
    expect(result.tokensOut).toBe(50);
    expect(result.tokensTotal).toBe(270);
    expect(result.validated.matchConfidence).toBe("HIGH");

    const calls = vi.mocked(openaiModule.createChatCompletion).mock.calls;
    expect(calls).toHaveLength(2);
    expect(calls[0]?.[1]?.responseFormat).toMatchObject({
      type: "json_schema",
      json_schema: {
        name: "ngram_campaign_prefill_response",
        strict: true,
      },
    });
    expect(calls[1]?.[0][2]).toEqual({
      role: "assistant",
      content: JSON.stringify({
        matched_product: {
          child_asin: "A1",
          child_sku: "DUO-1",
          product_name: "WHOOSH! Screen Shine Duo",
        },
        match_confidence: "",
        match_reason: "bad draft",
        term_recommendations: [
          {
            search_term: "laptop cloth",
            recommendation: "NEGATE",
            confidence: "",
            reason_tag: "accessory_only_intent",
            rationale: "standalone cloth query",
          },
        ],
      }),
    });
    expect(calls[1]?.[0].at(-1)?.content).toContain("Invalid confidence:");
  });

  it("fails after exhausting validation retries", async () => {
    const campaign: AggregatedCampaign = {
      campaignName: "Screen Shine - Pro | SPM | MKW | Br.M | 2 - computer | Perf",
      totalSpend: 10,
      termCount: 1,
      terms: [],
    };

    vi.spyOn(openaiModule, "createChatCompletion").mockResolvedValue({
      content: JSON.stringify({
        matched_product: null,
        match_confidence: "",
        match_reason: "bad draft",
        term_recommendations: [],
      }),
      tokensIn: 10,
      tokensOut: 5,
      tokensTotal: 15,
      model: "gpt-5.4-2026-03-05",
      durationMs: 1,
    });

    await expect(
      evaluateCampaignWithValidationRetry({
        campaign,
        catalogProducts: [],
        terms: [
          {
            campaignName: campaign.campaignName,
            searchTerm: "screen cleaner",
            impressions: 10,
            clicks: 1,
            spend: 1,
            orders: 0,
            sales: 0,
            keyword: null,
            keywordType: null,
            targeting: null,
            matchType: null,
          },
        ],
        marketplaceCode: "CA",
        model: "gpt-5.4-2026-03-05",
        maxTokens: 2200,
      }),
    ).rejects.toThrow("AI response validation failed after 3 attempts");
  });

  it("fails clearly if the model refuses structured output", async () => {
    const campaign: AggregatedCampaign = {
      campaignName: "Screen Shine - Go | SPM | STPP | Exp. | Rsrch",
      totalSpend: 10,
      termCount: 1,
      terms: [],
    };

    vi.spyOn(openaiModule, "createChatCompletion").mockResolvedValue({
      content: null,
      refusal: "safety refusal",
      tokensIn: 10,
      tokensOut: 1,
      tokensTotal: 11,
      model: "gpt-5.4-2026-03-05",
      durationMs: 1,
    });

    await expect(
      evaluateCampaignWithValidationRetry({
        campaign,
        catalogProducts: [],
        terms: [
          {
            campaignName: campaign.campaignName,
            searchTerm: "screen cleaner",
            impressions: 10,
            clicks: 1,
            spend: 1,
            orders: 0,
            sales: 0,
            keyword: null,
            keywordType: null,
            targeting: null,
            matchType: null,
          },
        ],
        marketplaceCode: "CA",
        model: "gpt-5.4-2026-03-05",
        maxTokens: 2200,
      }),
    ).rejects.toThrow("model refused structured output");
  });

  it("validates the pure-model context contract", async () => {
    const campaign: AggregatedCampaign = {
      campaignName: "Screen Shine - Duo | SPA | Cls. | Rsrch",
      totalSpend: 10,
      termCount: 1,
      terms: [],
    };
    const catalogProducts: AIPrefillCatalogProduct[] = [
      {
        childAsin: "A1",
        childSku: "DUO-1",
        productName: "WHOOSH! Screen Shine Duo",
        category: "electronics cleaner",
        itemDescription: "spray plus cloth",
      },
    ];

    vi.spyOn(openaiModule, "createChatCompletion").mockResolvedValue({
      content: JSON.stringify({
        matched_product: {
          child_asin: "A1",
          child_sku: "DUO-1",
          product_name: "WHOOSH! Screen Shine Duo",
        },
        match_confidence: "HIGH",
        match_reason: "valid draft",
      }),
      tokensIn: 70,
      tokensOut: 20,
      tokensTotal: 90,
      model: "gpt-5.4-2026-03-05",
      durationMs: 1,
    });

    const result = await evaluateCampaignWithPureModelValidationRetry({
      campaign,
      catalogProducts,
      marketplaceCode: "US",
      model: "gpt-5.4-2026-03-05",
      maxTokens: 2200,
    });

    expect(result.attempts).toBe(1);
    expect(result.validated.matchedProduct?.productName).toBe("WHOOSH! Screen Shine Duo");
    const calls = vi.mocked(openaiModule.createChatCompletion).mock.calls;
    expect(calls[0]?.[1]?.responseFormat).toMatchObject({
      type: "json_schema",
      json_schema: {
        name: "ngram_campaign_context_response",
        strict: true,
      },
    });
  });

  it("validates the pure-model term-triage contract with locked product context", async () => {
    const campaign: AggregatedCampaign = {
      campaignName: "Screen Shine - Duo | SPA | Cls. | Rsrch",
      totalSpend: 10,
      termCount: 2,
      terms: [],
    };
    const matchedProduct: AIPrefillCatalogProduct = {
      childAsin: "A1",
      childSku: "DUO-1",
      productName: "WHOOSH! Screen Shine Duo",
      category: "electronics cleaner",
      itemDescription: "spray plus cloth",
    };
    const terms: AggregatedSearchTerm[] = [
      {
        campaignName: campaign.campaignName,
        searchTerm: "laptop cloth",
        impressions: 100,
        clicks: 10,
        spend: 5,
        orders: 0,
        sales: 0,
        keyword: "laptop cloth",
        keywordType: "BROAD",
        targeting: null,
        matchType: "broad",
      },
      {
        campaignName: campaign.campaignName,
        searchTerm: "portable monitor travel case",
        impressions: 50,
        clicks: 4,
        spend: 4,
        orders: 0,
        sales: 0,
        keyword: "portable monitor travel case",
        keywordType: "BROAD",
        targeting: null,
        matchType: "broad",
      },
    ];

    vi.spyOn(openaiModule, "createChatCompletion").mockResolvedValue({
      content: JSON.stringify({
        term_recommendations: [
          {
            search_term: "laptop cloth",
            recommendation: "NEGATE",
            confidence: "HIGH",
            reason_tag: "accessory_only_intent",
            rationale: "standalone cloth query",
          },
          {
            search_term: "portable monitor travel case",
            recommendation: "NEGATE",
            confidence: "HIGH",
            reason_tag: "accessory_only_intent",
            rationale: "case intent",
          },
        ],
        exact_negatives: ["portable monitor travel case"],
        phrase_negatives: [
          {
            phrase: "laptop cloth",
            bucket: "bi",
            confidence: "HIGH",
            source_terms: ["laptop cloth"],
            rationale: "reusable cloth phrase",
          },
        ],
      }),
      tokensIn: 140,
      tokensOut: 40,
      tokensTotal: 180,
      model: "gpt-5.4-2026-03-05",
      durationMs: 1,
    });

    const result = await evaluateCampaignTermTriageWithValidationRetry({
      campaign,
      matchedProduct,
      terms,
      marketplaceCode: "US",
      matchConfidence: "HIGH",
      matchReason: "valid draft",
      model: "gpt-5.4-2026-03-05",
      maxTokens: 2200,
    });

    expect(result.attempts).toBe(1);
    expect(result.validated.exactNegatives).toEqual(["portable monitor travel case"]);
    expect(result.validated.modelPrefills.bi).toEqual(["laptop cloth"]);
    const calls = vi.mocked(openaiModule.createChatCompletion).mock.calls;
    expect(calls[0]?.[1]?.responseFormat).toMatchObject({
      type: "json_schema",
      json_schema: {
        name: "ngram_campaign_term_triage_response",
        strict: true,
      },
    });
  });
});
