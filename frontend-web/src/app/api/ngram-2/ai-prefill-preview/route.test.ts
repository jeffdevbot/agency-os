import { describe, expect, it } from "vitest";

import { type AIPrefillCatalogProduct, type AggregatedCampaign, type AggregatedSearchTerm } from "@/lib/ngram2/aiPrefill";

import {
  buildCampaignPrompt,
  buildPureModelContextPrompt,
  buildPureModelTermTriagePrompt,
  NGRAM_AI_PROMPT_VERSION,
  NGRAM_PURE_MODEL_PROMPT_VERSION,
  PURE_MODEL_CONTEXT_SYSTEM_PROMPT,
  PURE_MODEL_TERM_TRIAGE_SYSTEM_PROMPT,
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

    expect(userMessage?.content).toContain('"marketplace_code":"CA"');
    expect(userMessage?.content).toContain('"campaign_scope":"product_family"');
    expect(userMessage?.content).toContain('"client_context"');
    expect(NGRAM_AI_PROMPT_VERSION).toBe("ngram_step3_calibrated_v2026_04_02_brand_portfolio");
  });

  it("documents the cloth-only and CA French decision rules", () => {
    expect(SYSTEM_PROMPT).toContain("When you can write a clear one-sentence rationale for why the term is wrong-fit, that is a NEGATE, not a REVIEW.");
    expect(SYSTEM_PROMPT).toContain("When you can write a clear one-sentence rationale for why the term is plausibly relevant to this product, that is a KEEP, not a REVIEW.");
    expect(SYSTEM_PROMPT).toContain('A shopper searching "laptop cloth" when the product is a spray+cloth duo kit is seeking the cloth standalone.');
    expect(SYSTEM_PROMPT).toContain("Use the marketplace_code from the input payload.");
    expect(SYSTEM_PROMPT).toContain("On CA marketplace profiles, French-language terms are expected");
    expect(SYSTEM_PROMPT).toContain("REVIEW should represent a small minority of terms, typically 5-10% of the input.");
    expect(SYSTEM_PROMPT).toContain('treat "apple" as referring to Apple devices unless the term contains a clear counter-signal such as "juice" or "fruit"');
    expect(SYSTEM_PROMPT).toContain("Brand campaigns are valid input and must still be evaluated");
    expect(SYSTEM_PROMPT).toContain("If campaign_scope = brand_portfolio, the selected matched_product is only a representative anchor");
  });

  it("marks brand defensive lanes as brand_portfolio scope", () => {
    const campaign: AggregatedCampaign = {
      campaignName: "Brand | SPM | MKW | Br. | Mix. | Def",
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
        searchTerm: "whoosh wipes",
        impressions: 100,
        clicks: 10,
        spend: 4.5,
        orders: 0,
        sales: 0,
        keyword: "whoosh wipes",
        keywordType: "BROAD",
        targeting: null,
        matchType: "broad",
      },
    ];

    const messages = buildCampaignPrompt(campaign, catalogProducts, terms, "US", {
      clientName: "Whoosh",
      knownBrandNames: ["Whoosh"],
      marketplaceBrandNames: ["Whoosh"],
    });
    const userMessage = messages.find((message) => message.role === "user");

    expect(userMessage?.content).toContain('"campaign_scope":"brand_portfolio"');
    expect(userMessage?.content).toContain('"known_brand_names":["Whoosh"]');
  });

  it("defines the pure-model context pass contract", () => {
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
    const messages = buildPureModelContextPrompt(campaign, catalogProducts, "US");
    const userMessage = messages.find((message) => message.role === "user");

    expect(userMessage?.content).toContain('"campaign_identifier":"Screen Shine - Duo"');
    expect(userMessage?.content).toContain('"campaign_scope":"product_family"');
    expect(userMessage?.content).toContain('"client_context"');
    expect(userMessage?.content).toContain('"catalog_products"');
    expect(PURE_MODEL_CONTEXT_SYSTEM_PROMPT).toContain("Your job in this pass is only to lock product context");
    expect(PURE_MODEL_CONTEXT_SYSTEM_PROMPT).toContain("Use the provided client_context when campaign naming is broad, branded, defensive, or family-level.");
    expect(PURE_MODEL_CONTEXT_SYSTEM_PROMPT).toContain("If campaign_scope = brand_portfolio, choose a representative anchor product");
    expect(PURE_MODEL_CONTEXT_SYSTEM_PROMPT).toContain("Distinguish product-family ambiguity from product ambiguity.");
    expect(PURE_MODEL_CONTEXT_SYSTEM_PROMPT).toContain("return the single catalog row that best represents that family with match_confidence = MEDIUM");
    expect(PURE_MODEL_CONTEXT_SYSTEM_PROMPT).toContain("SKU prefixes and repeated catalog naming patterns are meaningful evidence.");
    expect(PURE_MODEL_CONTEXT_SYSTEM_PROMPT).toContain("Do not evaluate search terms in this pass.");
    expect(NGRAM_PURE_MODEL_PROMPT_VERSION).toBe("ngram_pure_model_two_step_v2026_04_02_brand_portfolio");
  });

  it("defines the pure-model term-triage pass contract", () => {
    const campaign: AggregatedCampaign = {
      campaignName: "Screen Shine - Duo | SPA | Cls. | Rsrch",
      totalSpend: 12.34,
      termCount: 1,
      terms: [],
    };
    const matchedProduct: AIPrefillCatalogProduct = {
      childAsin: "B001",
      childSku: "DUO-1",
      productName: "WHOOSH! Screen Shine Duo Kit",
      category: "electronics cleaner",
      itemDescription: "spray plus cloth kit",
    };
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

    const messages = buildPureModelTermTriagePrompt(
      campaign,
      matchedProduct,
      terms,
      "US",
      "HIGH",
      "Campaign name matches the Duo kit.",
    );
    const userMessage = messages.find((message) => message.role === "user");

    expect(userMessage?.content).toContain('"search_term":"laptop cloth"');
    expect(userMessage?.content).toContain('"campaign_scope":"product_family"');
    expect(userMessage?.content).toContain('"client_context"');
    expect(userMessage?.content).toContain('"locked_product_context"');
    expect(userMessage?.content).toContain('"match_confidence":"HIGH"');
    expect(PURE_MODEL_TERM_TRIAGE_SYSTEM_PROMPT).toContain('"exact_negatives"');
    expect(PURE_MODEL_TERM_TRIAGE_SYSTEM_PROMPT).toContain('"phrase_negatives"');
    expect(PURE_MODEL_TERM_TRIAGE_SYSTEM_PROMPT).toContain("matched product context is already locked");
    expect(PURE_MODEL_TERM_TRIAGE_SYSTEM_PROMPT).toContain("Use the provided client_context to interpret broad branded, defensive, or family-level campaign naming");
    expect(PURE_MODEL_TERM_TRIAGE_SYSTEM_PROMPT).toContain("If campaign_scope = brand_portfolio, treat the locked product context as a representative anchor");
    expect(PURE_MODEL_TERM_TRIAGE_SYSTEM_PROMPT).toContain("that is a KEEP, not a REVIEW");
    expect(PURE_MODEL_TERM_TRIAGE_SYSTEM_PROMPT).toContain("REVIEW should represent a small minority of terms, typically 5-10% of the input.");
    expect(PURE_MODEL_TERM_TRIAGE_SYSTEM_PROMPT).toContain('treat "apple" as referring to Apple devices unless the term contains a clear counter-signal such as "juice" or "fruit"');
  });
});
