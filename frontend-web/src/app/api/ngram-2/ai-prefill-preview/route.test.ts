import { describe, expect, it } from "vitest";

import { type AIPrefillCatalogProduct, type AggregatedCampaign, type AggregatedSearchTerm } from "@/lib/ngram2/aiPrefill";

import {
  buildCampaignPrompt,
  buildPureModelCampaignPrompt,
  NGRAM_AI_PROMPT_VERSION,
  NGRAM_PURE_MODEL_PROMPT_VERSION,
  PURE_MODEL_SYSTEM_PROMPT,
  SYSTEM_PROMPT,
} from "@/lib/ngram2/aiPrompt";

describe("ngram-2 ai prefill preview route prompt", () => {
  it("includes explicit marketplace code in the campaign payload", () => {
    const campaign: AggregatedCampaign = {
      campaignName: "Screen Shine - Duo | SPA | Cls. | Rsrch",
      totalSpend: 12.34,
      termCount: 1,
      terms: [],
    };
    const catalogProducts: AIPrefillCatalogProduct[] = [
      {
        childAsin: "B001",
        childSku: "DUO-1",
        productName: "WHOOSH! Screen Shine Duo Kit",
        category: "electronics cleaner",
        itemDescription: "spray plus cloth kit",
      },
    ];
    const terms: AggregatedSearchTerm[] = [
      {
        campaignName: campaign.campaignName,
        searchTerm: "laptop cloth",
        impressions: 100,
        clicks: 10,
        spend: 4.5,
        orders: 0,
        sales: 0,
        keyword: "laptop cloth",
        keywordType: "BROAD",
        targeting: null,
        matchType: "broad",
      },
    ];

    const messages = buildCampaignPrompt(campaign, catalogProducts, terms, "CA");
    const userMessage = messages.find((message) => message.role === "user");

    expect(userMessage?.content).toContain('"marketplace_code": "CA"');
    expect(NGRAM_AI_PROMPT_VERSION).toBe("ngram_step3_calibrated_v2026_03_30");
  });

  it("documents the cloth-only and CA French decision rules", () => {
    expect(SYSTEM_PROMPT).toContain("When you can write a clear one-sentence rationale for why the term is wrong-fit, that is a NEGATE, not a REVIEW.");
    expect(SYSTEM_PROMPT).toContain('A shopper searching "laptop cloth" when the product is a spray+cloth duo kit is seeking the cloth standalone.');
    expect(SYSTEM_PROMPT).toContain("Use the marketplace_code from the input payload.");
    expect(SYSTEM_PROMPT).toContain("On CA marketplace profiles, French-language terms are expected");
  });

  it("defines the pure-model prompt contract for exact and phrase negatives", () => {
    const campaign: AggregatedCampaign = {
      campaignName: "Screen Shine - Duo | SPA | Cls. | Rsrch",
      totalSpend: 12.34,
      termCount: 1,
      terms: [],
    };
    const catalogProducts: AIPrefillCatalogProduct[] = [
      {
        childAsin: "B001",
        childSku: "DUO-1",
        productName: "WHOOSH! Screen Shine Duo Kit",
        category: "electronics cleaner",
        itemDescription: "spray plus cloth kit",
      },
    ];
    const terms: AggregatedSearchTerm[] = [
      {
        campaignName: campaign.campaignName,
        searchTerm: "laptop cloth",
        impressions: 100,
        clicks: 10,
        spend: 4.5,
        orders: 0,
        sales: 0,
        keyword: "laptop cloth",
        keywordType: "BROAD",
        targeting: null,
        matchType: "broad",
      },
    ];

    const messages = buildPureModelCampaignPrompt(campaign, catalogProducts, terms, "US");
    const userMessage = messages.find((message) => message.role === "user");

    expect(userMessage?.content).toContain('"search_term": "laptop cloth"');
    expect(PURE_MODEL_SYSTEM_PROMPT).toContain('"exact_negatives"');
    expect(PURE_MODEL_SYSTEM_PROMPT).toContain('"phrase_negatives"');
    expect(PURE_MODEL_SYSTEM_PROMPT).toContain("exact_negatives must only contain search terms");
    expect(NGRAM_PURE_MODEL_PROMPT_VERSION).toBe("ngram_pure_model_single_campaign_v2026_03_31");
  });
});
