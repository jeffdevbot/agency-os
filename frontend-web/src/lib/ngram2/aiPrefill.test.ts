import { describe, expect, it } from "vitest";

import {
  aggregateSearchTerms,
  buildNgramsForQuery,
  buildCampaignAggregates,
  chooseBestListingMatch,
  selectCampaignsForAIPrefill,
  selectTermsForAIPrefillCampaign,
  isIntentionallySkippedCampaign,
  isExpectedAmbiguousCampaign,
  isLegacyExcludedCampaign,
  parseCampaignProductIdentifier,
  parseCampaignTheme,
  prepareAIPrefillCatalogProducts,
  synthesizeCampaignScratchpad,
  validateAIPrefillCampaignResponse,
  type SearchTermFactRow,
} from "./aiPrefill";

describe("ngram2 aiPrefill helpers", () => {
  it("parses product identifier and theme from campaign names", () => {
    const campaignName = "Screen Shine - Pro | SPM | MKW | Br.M | 2 - computer | Perf";
    expect(parseCampaignProductIdentifier(campaignName)).toBe("Screen Shine - Pro");
    expect(parseCampaignTheme(campaignName)).toBe("computer");
  });

  it("treats brand or defensive lanes as expected ambiguous", () => {
    expect(isExpectedAmbiguousCampaign("Brand | SPM | MKW | Br. | Mix. | Def")).toBe(true);
    expect(isIntentionallySkippedCampaign("Brand | SPM | MKW | Br. | Mix. | Def")).toBe(true);
    expect(isExpectedAmbiguousCampaign("Screen Shine - Pro | SPM | MKW | Br.M | 2 - computer | Perf")).toBe(
      false,
    );
  });

  it("matches a campaign to the strongest listing title", () => {
    const match = chooseBestListingMatch("Screen Shine - Duo | SPM | SKW | Ex. | screen cleaner | Rank", [
      {
        child_asin: "A1",
        child_sku: "DUO-1",
        child_product_name: "WHOOSH! Screen Shine Duo 3.4 + 0.3 fl oz",
        parent_title: null,
        category: "electronics cleaner",
        item_description: "bundle",
      },
      {
        child_asin: "A2",
        child_sku: "SPORT-1",
        child_product_name: "WHOOSH! Sport Shine 3.4 fl oz Eye Guard Cleaner",
        parent_title: null,
        category: "eyeglasses cleaner",
        item_description: "sports",
      },
    ]);

    expect(match.status).toBe("matched");
    expect(match.matchedTitle).toContain("Screen Shine Duo");
  });

  it("classifies brand or mix campaigns as intentionally skipped instead of ambiguous", () => {
    const match = chooseBestListingMatch("Brand | SPM | MKW | Br. | Mix. | Def", [
      {
        child_asin: "A1",
        child_sku: "PRO-1",
        child_product_name: "WHOOSH! Screen Shine Pro 16.9 fl oz",
        parent_title: null,
        category: "electronics cleaner",
        item_description: "large spray",
      },
    ]);

    expect(match.status).toBe("intentionally_skipped");
    expect(match.skipReason).toBe("brand_mix_defensive");
  });

  it("matches normalized family variants for a whoosh-like client without aliases", () => {
    const listings = [
      {
        child_asin: "A1",
        child_sku: "PRO-1",
        child_product_name: "WHOOSH! Screen Shine Pro 16.9 fl oz",
        parent_title: null,
        category: "electronics cleaner",
        item_description: "large spray",
      },
      {
        child_asin: "A2",
        child_sku: "GOXL-1",
        child_product_name: "WHOOSH! Screen Shine Go XL 3.4 fl oz",
        parent_title: null,
        category: "electronics cleaner",
        item_description: "travel spray",
      },
      {
        child_asin: "A3",
        child_sku: "DUO-1",
        child_product_name: "WHOOSH! Screen Shine Duo 3.4 + 0.3 fl oz",
        parent_title: null,
        category: "electronics cleaner",
        item_description: "duo kit",
      },
    ];

    const proMatch = chooseBestListingMatch("Screen Shine - Pro 2 | SPM | MKW | Br.M | 6 - tv | Perf", listings);
    const goMatch = chooseBestListingMatch("Screen Shine - Go XL | SPM | MKW | Br. | 3 - gen | Perf", listings);

    expect(proMatch.status).toBe("matched");
    expect(proMatch.matchedTitle).toContain("Screen Shine Pro");
    expect(goMatch.status).toBe("matched");
    expect(goMatch.matchedTitle).toContain("Screen Shine Go XL");
  });

  it("uses the same matcher logic for a different client structure with no code changes", () => {
    const listings = [
      {
        child_asin: "B1",
        child_sku: "SERUM-NIGHT",
        child_product_name: "Glow Labs Hydrating Serum Night Repair 30 ml",
        parent_title: null,
        category: "skin care",
        item_description: "overnight serum",
      },
      {
        child_asin: "B2",
        child_sku: "SERUM-DAY",
        child_product_name: "Glow Labs Hydrating Serum Day Defense 30 ml",
        parent_title: null,
        category: "skin care",
        item_description: "day serum",
      },
      {
        child_asin: "B3",
        child_sku: "CLEANSER-C",
        child_product_name: "Glow Labs Vitamin C Gel Cleanser 120 ml",
        parent_title: null,
        category: "skin care",
        item_description: "face wash",
      },
    ];

    const serumMatch = chooseBestListingMatch(
      "Hydrating Serum - Night Repair | SPM | MKW | Br. | 4 - overnight | Perf",
      listings,
    );
    const cleanserMatch = chooseBestListingMatch(
      "Vitamin C Gel Cleanser | SPM | MKW | Br. | 1 - face wash | Perf",
      listings,
    );

    expect(serumMatch.status).toBe("matched");
    expect(serumMatch.matchedTitle).toContain("Night Repair");
    expect(cleanserMatch.status).toBe("matched");
    expect(cleanserMatch.matchedTitle).toContain("Vitamin C Gel Cleanser");
  });

  it("aggregates rows and builds campaign totals with threshold and legacy exclusion filters", () => {
    const rows: SearchTermFactRow[] = [
      {
        report_date: "2026-03-20",
        campaign_name: "Screen Shine - Pro | SPM | MKW | Br.M | 2 - computer | Perf",
        search_term: "screen cleaner",
        impressions: 100,
        clicks: 10,
        spend: 8.5,
        orders: 2,
        sales: 50,
        keyword: "screen cleaner",
        keyword_type: "BROAD",
        targeting: null,
        match_type: "broad",
      },
      {
        report_date: "2026-03-21",
        campaign_name: "Screen Shine - Pro | SPM | MKW | Br.M | 2 - computer | Perf",
        search_term: "screen cleaner",
        impressions: 80,
        clicks: 7,
        spend: 4.5,
        orders: 1,
        sales: 22,
        keyword: "screen cleaner",
        keyword_type: "BROAD",
        targeting: null,
        match_type: "broad",
      },
      {
        report_date: "2026-03-20",
        campaign_name: "Brand | SPM | MKW | Br. | Mix. | Def",
        search_term: "whoosh cleaner",
        impressions: 50,
        clicks: 4,
        spend: 7.0,
        orders: 1,
        sales: 15,
        keyword: "whoosh cleaner",
        keyword_type: "EXACT",
        targeting: null,
        match_type: "exact",
      },
      {
        report_date: "2026-03-20",
        campaign_name: "Screen Shine - Pro | SPM | MKW | Ex. | 2 - computer | Perf",
        search_term: "cheap spray",
        impressions: 20,
        clicks: 2,
        spend: 1.25,
        orders: 0,
        sales: 0,
        keyword: "cheap spray",
        keyword_type: "BROAD",
        targeting: null,
        match_type: "broad",
      },
    ];

    const aggregated = aggregateSearchTerms(rows);
    expect(aggregated).toHaveLength(3);
    expect(aggregated.find((row) => row.searchTerm === "screen cleaner")?.spend).toBe(13);

    const campaigns = buildCampaignAggregates(aggregated, {
      spendThreshold: 3,
      respectLegacyExclusions: true,
    });

    expect(campaigns).toHaveLength(2);
    expect(campaigns[0]?.campaignName).toContain("Screen Shine - Pro");
    expect(campaigns[0]?.terms).toHaveLength(1);
    expect(isLegacyExcludedCampaign("Anything | SPM | MKW | Ex. | Rank")).toBe(true);
  });

  it("builds ngrams and synthesizes conservative scratchpad suggestions", () => {
    expect(buildNgramsForQuery("Travel-size screen cleaner", 2)).toEqual([
      "travel-size screen",
      "screen cleaner",
    ]);

    const scratchpad = synthesizeCampaignScratchpad(
      [
        {
          search_term: "travel size screen cleaner",
          recommendation: "NEGATE",
          confidence: "HIGH",
          reason_tag: "wrong_size_variant",
          rationale: null,
          spend: 9,
          clicks: 4,
          orders: 0,
          sales: 0,
          keyword: null,
          keywordType: null,
          targeting: null,
          matchType: null,
        },
        {
          search_term: "travel screen spray",
          recommendation: "NEGATE",
          confidence: "HIGH",
          reason_tag: "wrong_size_variant",
          rationale: null,
          spend: 7,
          clicks: 3,
          orders: 0,
          sales: 0,
          keyword: null,
          keywordType: null,
          targeting: null,
          matchType: null,
        },
        {
          search_term: "screen cleaner",
          recommendation: "KEEP",
          confidence: "HIGH",
          reason_tag: "core_use_case",
          rationale: null,
          spend: 20,
          clicks: 8,
          orders: 2,
          sales: 40,
          keyword: null,
          keywordType: null,
          targeting: null,
          matchType: null,
        },
      ],
      3,
    );

    expect(scratchpad.mono.map((item) => item.gram)).toContain("travel");
    expect(scratchpad.mono.map((item) => item.gram)).not.toContain("screen");
    expect(scratchpad.bi).toHaveLength(0);
  });

  it("prunes fragment monograms when a stronger repeated phrase exists", () => {
    const scratchpad = synthesizeCampaignScratchpad(
      [
        {
          search_term: "stardew valley for nintendo switch",
          recommendation: "NEGATE",
          confidence: "HIGH",
          reason_tag: "wrong_category",
          rationale: null,
          spend: 4,
          clicks: 2,
          orders: 0,
          sales: 0,
          keyword: null,
          keywordType: null,
          targeting: null,
          matchType: null,
        },
        {
          search_term: "stardew valley switch edition",
          recommendation: "NEGATE",
          confidence: "HIGH",
          reason_tag: "wrong_category",
          rationale: null,
          spend: 4,
          clicks: 2,
          orders: 0,
          sales: 0,
          keyword: null,
          keywordType: null,
          targeting: null,
          matchType: null,
        },
        {
          search_term: "stardew valley nintendo switch release",
          recommendation: "NEGATE",
          confidence: "HIGH",
          reason_tag: "wrong_category",
          rationale: null,
          spend: 4,
          clicks: 2,
          orders: 0,
          sales: 0,
          keyword: null,
          keywordType: null,
          targeting: null,
          matchType: null,
        },
      ],
      0,
    );

    expect(scratchpad.bi.map((item) => item.gram)).toContain("stardew valley");
    expect(scratchpad.mono.map((item) => item.gram)).not.toContain("stardew");
    expect(scratchpad.mono.map((item) => item.gram)).not.toContain("valley");
    expect(scratchpad.mono.map((item) => item.gram)).not.toContain("nintendo");
    expect(scratchpad.mono.map((item) => item.gram)).not.toContain("switch");
  });

  it("blocks weak glue-word grams and single-support trigrams", () => {
    const scratchpad = synthesizeCampaignScratchpad(
      [
        {
          search_term: "spray para limpiar pantalla de televisor y monitor",
          recommendation: "NEGATE",
          confidence: "HIGH",
          reason_tag: "foreign_language",
          rationale: null,
          spend: 12,
          clicks: 3,
          orders: 0,
          sales: 0,
          keyword: null,
          keywordType: null,
          targeting: null,
          matchType: null,
        },
        {
          search_term: "belkin display cleaner",
          recommendation: "NEGATE",
          confidence: "HIGH",
          reason_tag: "competitor_brand",
          rationale: null,
          spend: 10,
          clicks: 3,
          orders: 0,
          sales: 0,
          keyword: null,
          keywordType: null,
          targeting: null,
          matchType: null,
        },
      ],
      0,
    );

    expect(scratchpad.mono.map((item) => item.gram)).not.toContain("de");
    expect(scratchpad.mono.map((item) => item.gram)).not.toContain("para");
    expect(scratchpad.mono.map((item) => item.gram)).not.toContain("y");
    expect(scratchpad.mono.map((item) => item.gram)).not.toContain("limpiador");
    expect(scratchpad.bi.map((item) => item.gram)).not.toContain("para limpiar");
    expect(scratchpad.tri).toHaveLength(0);
  });

  it("keeps distinctive repeated phrases while blocking repeated generic cleaner/device phrases", () => {
    const scratchpad = synthesizeCampaignScratchpad(
      [
        {
          search_term: "flat screen tv cleaner",
          recommendation: "NEGATE",
          confidence: "HIGH",
          reason_tag: "wrong_category",
          rationale: null,
          spend: 9,
          clicks: 2,
          orders: 0,
          sales: 0,
          keyword: null,
          keywordType: null,
          targeting: null,
          matchType: null,
        },
        {
          search_term: "tv screen cleaner for smart tv streak free",
          recommendation: "NEGATE",
          confidence: "HIGH",
          reason_tag: "wrong_category",
          rationale: null,
          spend: 9,
          clicks: 2,
          orders: 0,
          sales: 0,
          keyword: null,
          keywordType: null,
          targeting: null,
          matchType: null,
        },
        {
          search_term: "cleaning cloth for computer screen",
          recommendation: "NEGATE",
          confidence: "HIGH",
          reason_tag: "accessory_only_intent",
          rationale: null,
          spend: 7,
          clicks: 2,
          orders: 0,
          sales: 0,
          keyword: null,
          keywordType: null,
          targeting: null,
          matchType: null,
        },
        {
          search_term: "phone cloths anti scratch and cleaner",
          recommendation: "NEGATE",
          confidence: "HIGH",
          reason_tag: "accessory_only_intent",
          rationale: null,
          spend: 7,
          clicks: 2,
          orders: 0,
          sales: 0,
          keyword: null,
          keywordType: null,
          targeting: null,
          matchType: null,
        },
        {
          search_term: "screen doctor professional screen cleaner",
          recommendation: "NEGATE",
          confidence: "HIGH",
          reason_tag: "competitor_brand",
          rationale: null,
          spend: 6,
          clicks: 2,
          orders: 0,
          sales: 0,
          keyword: null,
          keywordType: null,
          targeting: null,
          matchType: null,
        },
        {
          search_term: "screen doctor tv screen cleaner",
          recommendation: "NEGATE",
          confidence: "HIGH",
          reason_tag: "competitor_brand",
          rationale: null,
          spend: 6,
          clicks: 2,
          orders: 0,
          sales: 0,
          keyword: null,
          keywordType: null,
          targeting: null,
          matchType: null,
        },
      ],
      0,
    );

    expect(scratchpad.mono.map((item) => item.gram)).not.toContain("from");
    expect(scratchpad.mono.map((item) => item.gram)).not.toContain("televisor");
    expect(scratchpad.bi.map((item) => item.gram)).toContain("screen doctor");
    expect(scratchpad.bi.map((item) => item.gram)).not.toContain("tv screen");
    expect(scratchpad.bi.map((item) => item.gram)).not.toContain("cleaning cloth");
    expect(scratchpad.bi.map((item) => item.gram)).not.toContain("phone screen");
    expect(scratchpad.tri.map((item) => item.gram)).not.toContain("tv screen cleaner");
    expect(scratchpad.tri.map((item) => item.gram)).not.toContain("screen cleaning cloth");
  });

  it("caps preview mode but leaves full mode uncapped", () => {
    const campaigns = Array.from({ length: 8 }, (_, campaignIndex) => ({
      campaignName: `Campaign ${campaignIndex + 1}`,
      totalSpend: 100 - campaignIndex,
      termCount: 25,
      terms: Array.from({ length: 25 }, (_, termIndex) => ({
        campaignName: `Campaign ${campaignIndex + 1}`,
        searchTerm: `term ${termIndex + 1}`,
        impressions: 10,
        clicks: 1,
        spend: 25 - termIndex,
        orders: 0,
        sales: 0,
        keyword: null,
        keywordType: null,
        targeting: null,
        matchType: null,
      })),
    }));

    const previewCampaigns = selectCampaignsForAIPrefill(campaigns, "preview");
    const fullCampaigns = selectCampaignsForAIPrefill(campaigns, "full");

    expect(previewCampaigns).toHaveLength(6);
    expect(fullCampaigns).toHaveLength(8);
    expect(selectTermsForAIPrefillCampaign(previewCampaigns[0], "preview")).toHaveLength(20);
    expect(selectTermsForAIPrefillCampaign(fullCampaigns[0], "full")).toHaveLength(25);
  });

  it("respects requested campaign subsets and bypasses preview term caps for them", () => {
    const campaigns = Array.from({ length: 3 }, (_, campaignIndex) => ({
      campaignName: `Campaign ${campaignIndex + 1}`,
      totalSpend: 100 - campaignIndex,
      termCount: 25,
      terms: Array.from({ length: 25 }, (_, termIndex) => ({
        campaignName: `Campaign ${campaignIndex + 1}`,
        searchTerm: `term ${termIndex + 1}`,
        impressions: 10,
        clicks: 1,
        spend: 25 - termIndex,
        orders: 0,
        sales: 0,
        keyword: null,
        keywordType: null,
        targeting: null,
        matchType: null,
      })),
    }));

    const requestedCampaigns = selectCampaignsForAIPrefill(campaigns, "preview", [
      "Campaign 3",
      "Campaign 1",
      "Missing Campaign",
    ]);

    expect(requestedCampaigns.map((campaign) => campaign.campaignName)).toEqual([
      "Campaign 3",
      "Campaign 1",
    ]);
    expect(selectTermsForAIPrefillCampaign(requestedCampaigns[0], "preview", true)).toHaveLength(25);
  });

  it("prepares catalog rows and validates the strict AI response contract", () => {
    const catalog = prepareAIPrefillCatalogProducts([
      {
        child_asin: "A1",
        child_sku: "1FGAMZ500US",
        child_product_name: "WHOOSH! Screen Shine Pro 16.9 fl oz Refillable Screen Cleaner",
        parent_title: null,
        category: "electronics cleaner",
        item_description: "large screen cleaner",
      },
      {
        child_asin: "A2",
        child_sku: "1FG100MLAMZ",
        child_product_name: "WHOOSH! Screen Shine Go XL 3.4 fl oz",
        parent_title: null,
        category: "electronics cleaner",
        item_description: "travel cleaner",
      },
    ]);

    const validated = validateAIPrefillCampaignResponse(
      {
        matched_product: {
          child_asin: "A1",
          child_sku: "1FGAMZ500US",
          product_name: "WHOOSH! Screen Shine Pro 16.9 fl oz Refillable Screen Cleaner",
        },
        match_confidence: "HIGH",
        match_reason: "Campaign family name maps directly to the Pro listing.",
        term_recommendations: [
          {
            search_term: "screen cleaner",
            recommendation: "KEEP",
            confidence: "HIGH",
            reason_tag: "core_use_case",
            rationale: "Direct fit.",
          },
          {
            search_term: "travel size screen cleaner",
            recommendation: "NEGATE",
            confidence: "HIGH",
            reason_tag: "wrong_size_variant",
            rationale: "This campaign maps to the larger Pro bottle.",
          },
        ],
      },
      catalog,
      ["screen cleaner", "travel size screen cleaner"],
    );

    expect(validated.matchedProduct?.childAsin).toBe("A1");
    expect(validated.termRecommendations).toHaveLength(2);
    expect(validated.termRecommendations[1]?.reason_tag).toBe("wrong_size_variant");
  });

  it("fails loudly when the AI response is missing a term recommendation or returns a bad product", () => {
    const catalog = prepareAIPrefillCatalogProducts([
      {
        child_asin: "A1",
        child_sku: "1FGAMZ500US",
        child_product_name: "WHOOSH! Screen Shine Pro 16.9 fl oz Refillable Screen Cleaner",
        parent_title: null,
        category: "electronics cleaner",
        item_description: "large screen cleaner",
      },
    ]);

    expect(() =>
      validateAIPrefillCampaignResponse(
        {
          matched_product: {
            child_asin: "BAD-ASIN",
            child_sku: "1FGAMZ500US",
            product_name: "WHOOSH! Screen Shine Pro 16.9 fl oz Refillable Screen Cleaner",
          },
          match_confidence: "HIGH",
          match_reason: "wrong",
          term_recommendations: [
            {
              search_term: "screen cleaner",
              recommendation: "KEEP",
              confidence: "HIGH",
              reason_tag: "core_use_case",
              rationale: "fit",
            },
          ],
        },
        catalog,
        ["screen cleaner", "travel size screen cleaner"],
      ),
    ).toThrow();
  });

  it("fails loudly when the AI response returns a reason tag outside the allowed enum", () => {
    const catalog = prepareAIPrefillCatalogProducts([
      {
        child_asin: "A1",
        child_sku: "1FGAMZ500US",
        child_product_name: "WHOOSH! Screen Shine Pro 16.9 fl oz Refillable Screen Cleaner",
        parent_title: null,
        category: "electronics cleaner",
        item_description: "large screen cleaner",
      },
    ]);

    expect(() =>
      validateAIPrefillCampaignResponse(
        {
          matched_product: {
            child_asin: "A1",
            child_sku: "1FGAMZ500US",
            product_name: "WHOOSH! Screen Shine Pro 16.9 fl oz Refillable Screen Cleaner",
          },
          match_confidence: "HIGH",
          match_reason: "right product",
          term_recommendations: [
            {
              search_term: "screen cleaner",
              recommendation: "KEEP",
              confidence: "HIGH",
              reason_tag: "travel_size_mismatch",
              rationale: "fit",
            },
          ],
        },
        catalog,
        ["screen cleaner"],
      ),
    ).toThrow(/Invalid reason_tag/);
  });
});
