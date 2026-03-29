import { describe, expect, it } from "vitest";

import {
  aggregateSearchTerms,
  buildNgramsForQuery,
  buildCampaignAggregates,
  chooseBestListingMatch,
  isExpectedAmbiguousCampaign,
  isLegacyExcludedCampaign,
  parseCampaignProductIdentifier,
  parseCampaignTheme,
  synthesizeCampaignScratchpad,
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
    expect(isExpectedAmbiguousCampaign("Screen Shine - Pro | SPM | MKW | Br.M | 2 - computer | Perf")).toBe(
      false,
    );
  });

  it("matches a campaign to the strongest listing title", () => {
    const match = chooseBestListingMatch("Screen Shine - Duo | SPM | SKW | Ex. | screen cleaner | Rank", [
      {
        child_asin: "A1",
        child_product_name: "WHOOSH! Screen Shine Duo 3.4 + 0.3 fl oz",
        parent_title: null,
        category: "electronics cleaner",
        item_description: "bundle",
      },
      {
        child_asin: "A2",
        child_product_name: "WHOOSH! Sport Shine 3.4 fl oz Eye Guard Cleaner",
        parent_title: null,
        category: "eyeglasses cleaner",
        item_description: "sports",
      },
    ]);

    expect(match.status).toBe("matched");
    expect(match.matchedTitle).toContain("Screen Shine Duo");
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
          reason_tag: "travel_size_mismatch",
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
          reason_tag: "travel_size_mismatch",
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
    expect(scratchpad.bi.map((item) => item.gram)).toContain("travel size");
  });
});
