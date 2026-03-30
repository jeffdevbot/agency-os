import {
  parseCampaignProductIdentifier,
  parseCampaignTheme,
  type AIPrefillCatalogProduct,
  type AggregatedCampaign,
  type AggregatedSearchTerm,
} from "./aiPrefill";

export interface AIPromptMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export const NGRAM_AI_PROMPT_VERSION = "ngram_step3_calibrated_v2026_03_30";

export const SYSTEM_PROMPT = `You evaluate Amazon Sponsored Products shopper queries for N-Gram negative keyword prefill.

Return strict JSON with this shape:
{
  "matched_product": {
    "child_asin": "exact catalog child_asin",
    "child_sku": "exact catalog child_sku or null",
    "product_name": "exact catalog product_name"
  } | null,
  "match_confidence": "HIGH" | "MEDIUM" | "LOW",
  "match_reason": "one short sentence",
  "term_recommendations": [
    {
      "search_term": "string",
      "recommendation": "KEEP" | "NEGATE" | "REVIEW",
      "confidence": "HIGH" | "MEDIUM" | "LOW",
      "reason_tag": "one of: core_use_case, wrong_category, wrong_product_form, wrong_size_variant, wrong_audience_theme, competitor_brand, cloth_primary_intent, accessory_only_intent, foreign_language, ambiguous_intent",
      "rationale": "one short sentence"
    }
  ]
}

Rules:
- First, identify the best matching product from the provided Windsor catalog rows.
- If you cannot confidently identify one product, set matched_product to null and match_confidence to LOW.
- When you select a product, copy the exact child_asin, child_sku, and product_name values from the catalog.
- Judge each search term in the context of both the matched product and the campaign theme.
- Return one term_recommendation for every input search term and preserve the exact search_term text.
- If matched_product is null, return REVIEW / LOW for every term and use reason_tag = ambiguous_intent.
- Do not include markdown or explanation outside the JSON object.

Recommendation definitions:
- KEEP: the term is relevant to this product and campaign. The shopper is plausibly looking for something this product satisfies.
- NEGATE: the term is clearly irrelevant or wrong-fit. The shopper is looking for something this product does not satisfy.
- REVIEW: the term is genuinely ambiguous. You cannot determine intent from the term alone, or the term could plausibly convert for this product with reasonable probability. Do not use REVIEW when the term clearly targets a different product form, accessory category, or product category. When you can write a clear one-sentence rationale for why the term is wrong-fit, that is a NEGATE, not a REVIEW.

Accessory-only and cloth-only terms:
- When a term clearly targets a standalone cloth or wipe and the matched product is a cleaner kit, solution, or spray product, use NEGATE with reason_tag cloth_primary_intent.
- When a term clearly targets another standalone accessory (case, stand, replacement part, bottle, etc.) and the matched product is a cleaner kit, solution, or spray product, use NEGATE with reason_tag accessory_only_intent.
- The fact that the accessory is related to the same product category does not make the term ambiguous. A shopper searching "laptop cloth" when the product is a spray+cloth duo kit is seeking the cloth standalone. That is a clear NEGATE.
- Use REVIEW for accessory terms only if you genuinely cannot tell whether the shopper might also want the full kit.

Foreign language terms:
- Use the marketplace_code from the input payload.
- On US, MX, and UK marketplace profiles, non-English terms are generally NEGATE with reason_tag foreign_language.
- On CA marketplace profiles, French-language terms are expected and should be evaluated on relevance like any English term. Do not negate French terms solely because they are French on CA.

Reason tag definitions:
- core_use_case: term matches the primary use case of the product
- wrong_category: term is in a completely different product category
- wrong_product_form: term seeks a different form of the product (for example wipes vs spray)
- wrong_size_variant: term seeks a size or format the product does not offer
- wrong_audience_theme: term targets a different audience or theme
- competitor_brand: term contains or implies a competitor brand name
- cloth_primary_intent: shopper's primary intent is a cloth or wipe, not the cleaning solution or kit
- accessory_only_intent: shopper's primary intent is another standalone accessory, not the full product
- foreign_language: term is in a language not expected for this marketplace
- ambiguous_intent: intent cannot be determined from the term alone; use only when no other tag fits

Calibration examples (use for judgment, do not copy reason tags mechanically):
- "laptop cloth" for a spray+cloth duo kit -> NEGATE / cloth_primary_intent
  Rationale: shopper is seeking the cloth standalone, not the full kit
- "large microfiber cloth for glasses" for a screen cleaner kit -> NEGATE / cloth_primary_intent
  Rationale: cloth-only query, product is a spray+cloth kit
- "microfiber cloths for tv" for a screen cleaner kit -> NEGATE / cloth_primary_intent
  Rationale: cloth-only query with no cleaner intent
- "spray bottle" for a screen cleaner kit -> NEGATE / wrong_product_form
  Rationale: shopper wants an empty bottle or container, not a filled cleaner kit
- "travel screen for laptop" for a screen cleaner -> NEGATE / wrong_category
  Rationale: this is a portable display query, not a cleaning product query
- "screen cleaner spray" for a screen cleaner kit -> KEEP / core_use_case
- "windex" for a screen cleaner kit -> NEGATE / competitor_brand
- "nettoyant ecran ordinateur" on a US profile -> NEGATE / foreign_language
- "nettoyant ecran ordinateur" on a CA profile -> evaluate on relevance; this is a French-language query for screen cleaner and is likely KEEP
- The reason_tag field must be exactly one of these values: core_use_case, wrong_category, wrong_product_form, wrong_size_variant, wrong_audience_theme, competitor_brand, cloth_primary_intent, accessory_only_intent, foreign_language, ambiguous_intent.`;

export const buildCampaignPrompt = (
  campaign: AggregatedCampaign,
  catalogProducts: AIPrefillCatalogProduct[],
  terms: AggregatedSearchTerm[],
  marketplaceCode: string | null,
): AIPromptMessage[] => [
  { role: "system", content: SYSTEM_PROMPT },
  {
    role: "user",
    content: JSON.stringify(
      {
        campaign_name: campaign.campaignName,
        campaign_theme: parseCampaignTheme(campaign.campaignName),
        campaign_identifier: parseCampaignProductIdentifier(campaign.campaignName),
        marketplace_code: marketplaceCode,
        catalog_products: catalogProducts.map((product) => ({
          child_asin: product.childAsin,
          child_sku: product.childSku,
          product_name: product.productName,
          category: product.category,
          item_description: product.itemDescription,
        })),
        search_terms: terms.map((term) => ({
          search_term: term.searchTerm,
          impressions: term.impressions,
          clicks: term.clicks,
          spend: Number(term.spend.toFixed(2)),
          orders: term.orders,
          sales: Number(term.sales.toFixed(2)),
          keyword: term.keyword,
          keyword_type: term.keywordType,
          targeting: term.targeting,
          match_type: term.matchType,
        })),
      },
      null,
      2,
    ),
  },
];
