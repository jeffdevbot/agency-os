import { describe, expect, it } from "vitest";

import { type AIPrefillCatalogProduct, type AggregatedCampaign, type AggregatedSearchTerm } from "@/lib/ngram2/aiPrefill";

import { buildCampaignPrompt, SYSTEM_PROMPT } from "@/lib/ngram2/aiPrompt";

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
  });

  it("documents the cloth-only and CA French decision rules", () => {
    expect(SYSTEM_PROMPT).toContain("When you can write a clear one-sentence rationale for why the term is wrong-fit, that is a NEGATE, not a REVIEW.");
    expect(SYSTEM_PROMPT).toContain('A shopper searching "laptop cloth" when the product is a spray+cloth duo kit is seeking the cloth standalone.');
    expect(SYSTEM_PROMPT).toContain("Use the marketplace_code from the input payload.");
    expect(SYSTEM_PROMPT).toContain("On CA marketplace profiles, French-language terms are expected");
  });
});
