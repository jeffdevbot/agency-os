import { describe, expect, it } from "vitest";

import {
  aggregateSearchTerms,
  buildNgramsForQuery,
  buildCampaignAggregates,
  chooseBestListingMatch,
  buildPreparedCatalogProductIndex,
  selectCampaignsForAIPrefill,
  selectCatalogCandidatesForCampaign,
  selectTermsForAIPrefillCampaign,
  isIntentionallySkippedCampaign,
  isExpectedAmbiguousCampaign,
  isLegacyExcludedCampaign,
  mergePureModelCampaignResponses,
  mergePureModelTermTriageResponses,
  parseCampaignProductIdentifier,
  parseCampaignTheme,
  prepareAIPrefillCatalogProducts,
  synthesizeCampaignScratchpad,
  validateAIPrefillCampaignResponse,
  validatePureModelCampaignResponse,
  validatePureModelContextResponse,
  validatePureModelTermTriageResponse,
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
    expect(isIntentionallySkippedCampaign("Brand | SPM | MKW | Br. | Mix. | Def")).toBe(false);
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

  it("classifies brand or mix campaigns as ambiguous instead of intentionally skipped", () => {
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

    expect(match.status).toBe("ambiguous");
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

  it("ranks catalog candidates with SKU and family signals before AI sees the shortlist", () => {
    const catalogProducts = [
      {
        childAsin: "A1",
        childSku: "NGR-001",
        productName: "Ahimsa NGR Ceramic Dinner Plates Set",
        category: "dinnerware",
        itemDescription: "ceramic dinner plates for everyday use",
      },
      {
        childAsin: "A2",
        childSku: "BWL-002",
        productName: "Ahimsa Ceramic Bowls Set",
        category: "dinnerware",
        itemDescription: "ceramic serving bowls",
      },
      {
        childAsin: "A3",
        childSku: "MAT-003",
        productName: "Ahimsa Yoga Mat Carry Strap",
        category: "fitness accessories",
        itemDescription: "adjustable carrying strap",
      },
    ];

    const ranked = selectCatalogCandidatesForCampaign(
      "NGR | SPM | MKW | Br. | 2 - plates | Perf",
      buildPreparedCatalogProductIndex(catalogProducts),
      { limit: 2 },
    );

    expect(ranked).toHaveLength(2);
    expect(ranked[0]?.product.childAsin).toBe("A1");
    expect(ranked[0]?.signals).toEqual(expect.arrayContaining(["sku_phrase"]));
    expect(ranked[0]?.score).toBeGreaterThan(ranked[1]?.score ?? 0);
  });

  it("uses theme and description overlap when the identifier alone is weak", () => {
    const catalogProducts = [
      {
        childAsin: "B1",
        childSku: "CORE-001",
        productName: "Whoosh Screen Cleaner Kit",
        category: "electronics cleaner",
        itemDescription: "screen cleaning spray for laptop and monitor care",
      },
      {
        childAsin: "B2",
        childSku: "SPORT-002",
        productName: "Whoosh Glasses Cleaning Kit",
        category: "eyeglasses cleaner",
        itemDescription: "travel cleaner for glasses and sunglasses",
      },
      {
        childAsin: "B3",
        childSku: "PAD-003",
        productName: "Whoosh Mouse Pad Cleaner",
        category: "computer accessories",
        itemDescription: "foam cleaner for gaming desk mats",
      },
    ];

    const ranked = selectCatalogCandidatesForCampaign(
      "Travel Kit | SPM | MKW | Br. | 2 - laptop | Perf",
      catalogProducts,
      { limit: 3 },
    );

    expect(ranked[0]?.product.childAsin).toBe("B1");
    expect(ranked[0]?.score).toBeGreaterThan(ranked[1]?.score ?? 0);
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

  it("validates pure-model exact and phrase negatives without heuristic synthesis", () => {
    const validated = validatePureModelCampaignResponse(
      {
        matched_product: {
          child_asin: "A1",
          child_sku: "DUO-1",
          product_name: "WHOOSH! Screen Shine Duo",
        },
        match_confidence: "HIGH",
        match_reason: "Best catalog fit.",
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
            rationale: "shopper wants a case",
          },
          {
            search_term: "screen cleaner spray",
            recommendation: "KEEP",
            confidence: "HIGH",
            reason_tag: "core_use_case",
            rationale: "core product query",
          },
        ],
        exact_negatives: ["portable monitor travel case"],
        phrase_negatives: [
          {
            phrase: "laptop cloth",
            bucket: "bi",
            confidence: "HIGH",
            source_terms: ["laptop cloth"],
            rationale: "reusable cloth-only phrase",
          },
        ],
      },
      [
        {
          childAsin: "A1",
          childSku: "DUO-1",
          productName: "WHOOSH! Screen Shine Duo",
          category: "electronics cleaner",
          itemDescription: "spray plus cloth",
        },
      ],
      ["laptop cloth", "portable monitor travel case", "screen cleaner spray"],
    );

    expect(validated.exactNegatives).toEqual(["portable monitor travel case"]);
    expect(validated.modelPrefills).toEqual({
      exact: ["portable monitor travel case"],
      mono: [],
      bi: ["laptop cloth"],
      tri: [],
    });
    expect(validated.phraseNegatives[0]?.sourceTerms).toEqual(["laptop cloth"]);
  });

  it("validates the two-step pure-model context response", () => {
    const validated = validatePureModelContextResponse(
      {
        matched_product: {
          child_asin: "A1",
          child_sku: "DUO-1",
          product_name: "WHOOSH! Screen Shine Duo",
        },
        match_confidence: "HIGH",
        match_reason: "Campaign name aligns with the Duo catalog row.",
      },
      [
        {
          childAsin: "A1",
          childSku: "DUO-1",
          productName: "WHOOSH! Screen Shine Duo",
          category: "electronics cleaner",
          itemDescription: "spray plus cloth",
        },
      ],
    );

    expect(validated.matchConfidence).toBe("HIGH");
    expect(validated.matchedProduct?.productName).toBe("WHOOSH! Screen Shine Duo");
  });

  it("validates the two-step pure-model term-triage response", () => {
    const validated = validatePureModelTermTriageResponse(
      {
        term_recommendations: [
          {
            search_term: "laptop cloth",
            recommendation: "NEGATE",
            confidence: "HIGH",
            reason_tag: "accessory_only_intent",
            rationale: "standalone cloth query",
          },
          {
            search_term: "screen cleaner spray",
            recommendation: "KEEP",
            confidence: "HIGH",
            reason_tag: "core_use_case",
            rationale: "core product query",
          },
        ],
        exact_negatives: [],
        phrase_negatives: [
          {
            phrase: "laptop cloth",
            bucket: "bi",
            confidence: "HIGH",
            source_terms: ["laptop cloth"],
            rationale: "reusable cloth-only phrase",
          },
        ],
      },
      ["laptop cloth", "screen cleaner spray"],
    );

    expect(validated.termRecommendations).toHaveLength(2);
    expect(validated.modelPrefills.bi).toEqual(["laptop cloth"]);
    expect(validated.phraseNegatives[0]?.sourceTerms).toEqual(["laptop cloth"]);
  });

  it("merges chunked pure-model responses into one campaign result", () => {
    const merged = mergePureModelCampaignResponses([
      {
        matchedProduct: {
          childAsin: "A1",
          childSku: "DUO-1",
          productName: "WHOOSH! Screen Shine Duo",
          category: "electronics cleaner",
          itemDescription: "spray plus cloth",
        },
        matchConfidence: "HIGH",
        matchReason: "Best fit.",
        termRecommendations: [
          {
            search_term: "laptop cloth",
            recommendation: "NEGATE",
            confidence: "HIGH",
            reason_tag: "accessory_only_intent",
            rationale: "standalone cloth",
          },
        ],
        exactNegatives: [],
        phraseNegatives: [
          {
            phrase: "laptop cloth",
            bucket: "bi",
            confidence: "HIGH",
            sourceTerms: ["laptop cloth"],
            rationale: "reusable cloth phrase",
          },
        ],
        modelPrefills: {
          exact: [],
          mono: [],
          bi: ["laptop cloth"],
          tri: [],
        },
      },
      {
        matchedProduct: {
          childAsin: "A1",
          childSku: "DUO-1",
          productName: "WHOOSH! Screen Shine Duo",
          category: "electronics cleaner",
          itemDescription: "spray plus cloth",
        },
        matchConfidence: "HIGH",
        matchReason: "Best fit.",
        termRecommendations: [
          {
            search_term: "portable monitor travel case",
            recommendation: "NEGATE",
            confidence: "HIGH",
            reason_tag: "accessory_only_intent",
            rationale: "case intent",
          },
        ],
        exactNegatives: ["portable monitor travel case"],
        phraseNegatives: [
          {
            phrase: "laptop cloth",
            bucket: "bi",
            confidence: "MEDIUM",
            sourceTerms: ["portable monitor travel case"],
            rationale: null,
          },
        ],
        modelPrefills: {
          exact: ["portable monitor travel case"],
          mono: [],
          bi: ["laptop cloth"],
          tri: [],
        },
      },
    ]);

    expect(merged.termRecommendations).toHaveLength(2);
    expect(merged.exactNegatives).toEqual(["portable monitor travel case"]);
    expect(merged.modelPrefills.bi).toEqual(["laptop cloth"]);
    expect(merged.phraseNegatives[0]?.sourceTerms).toEqual([
      "laptop cloth",
      "portable monitor travel case",
    ]);
  });

  it("merges chunked two-step term-triage responses into one result", () => {
    const merged = mergePureModelTermTriageResponses([
      {
        termRecommendations: [
          {
            search_term: "laptop cloth",
            recommendation: "NEGATE",
            confidence: "HIGH",
            reason_tag: "accessory_only_intent",
            rationale: "standalone cloth",
          },
        ],
        exactNegatives: [],
        phraseNegatives: [
          {
            phrase: "laptop cloth",
            bucket: "bi",
            confidence: "HIGH",
            sourceTerms: ["laptop cloth"],
            rationale: "reusable cloth phrase",
          },
        ],
        modelPrefills: {
          exact: [],
          mono: [],
          bi: ["laptop cloth"],
          tri: [],
        },
      },
      {
        termRecommendations: [
          {
            search_term: "portable monitor travel case",
            recommendation: "NEGATE",
            confidence: "HIGH",
            reason_tag: "accessory_only_intent",
            rationale: "case intent",
          },
        ],
        exactNegatives: ["portable monitor travel case"],
        phraseNegatives: [
          {
            phrase: "laptop cloth",
            bucket: "bi",
            confidence: "MEDIUM",
            sourceTerms: ["portable monitor travel case"],
            rationale: null,
          },
        ],
        modelPrefills: {
          exact: ["portable monitor travel case"],
          mono: [],
          bi: ["laptop cloth"],
          tri: [],
        },
      },
    ]);

    expect(merged.termRecommendations).toHaveLength(2);
    expect(merged.exactNegatives).toEqual(["portable monitor travel case"]);
    expect(merged.modelPrefills.bi).toEqual(["laptop cloth"]);
    expect(merged.phraseNegatives[0]?.sourceTerms).toEqual([
      "laptop cloth",
      "portable monitor travel case",
    ]);
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
