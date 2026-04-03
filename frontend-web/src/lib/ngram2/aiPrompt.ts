import {
  deriveCampaignScope,
  parseCampaignProductIdentifier,
  parseCampaignTheme,
  type AIPrefillBrandContext,
  type AIPrefillCatalogProduct,
  type AggregatedCampaign,
  type AggregatedSearchTerm,
} from "./aiPrefill";

export interface AIPromptMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

const stringifyPromptPayload = (payload: Record<string, unknown>): string => JSON.stringify(payload);

export const NGRAM_AI_PROMPT_VERSION = "ngram_step3_calibrated_v2026_04_02_sparse_keep_rationale";
export const NGRAM_PURE_MODEL_PROMPT_VERSION = "ngram_pure_model_two_step_v2026_04_02_sparse_keep_rationale";

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
      "reason_tag": "one of: core_use_case, wrong_category, wrong_product_form, wrong_size_variant, wrong_audience_theme, competitor_brand, accessory_only_intent, foreign_language, ambiguous_intent",
      "rationale": "one short sentence or null"
    }
  ]
}

Rules:
- First, identify the best matching product from the provided Windsor catalog rows.
- Use the provided client_context when campaign naming is broad, branded, defensive, or family-level. Brand campaigns are valid input and must still be evaluated; do not silently treat them as out of scope.
- Use campaign_scope from the input payload.
- If you cannot confidently identify one product, set matched_product to null and match_confidence to LOW.
- When you select a product, copy the exact child_asin, child_sku, and product_name values from the catalog.
- Distinguish product-family ambiguity from product ambiguity. If the campaign name or identifier clearly implies a product family but does not resolve to one exact variant or SKU, return the single catalog row that best represents that family with match_confidence = MEDIUM, not LOW.
- If the campaign is a broad brand or defensive lane and the exact variant is unclear, use client_context plus the catalog rows to infer the most likely brand/product family. Family-level MEDIUM is better than null when the brand family is clear.
- If campaign_scope = brand_portfolio, the selected matched_product is only a representative anchor for the client's broader brand portfolio, not proof that sibling in-brand families are out of scope.
- If campaign_scope = brand_portfolio, do not use NEGATE with wrong_product_form or wrong_size_variant solely because a term appears to target another known in-brand family, variant, or brand from client_context.
- If campaign_scope = brand_portfolio and a term appears relevant to another known in-brand family or brand, prefer KEEP or REVIEW unless there is clear evidence that the term is competitor, wrong-category, foreign-language, or otherwise outside the client's portfolio.
- SKU prefixes and repeated catalog naming patterns are meaningful evidence. When several catalog rows share a prefix or family token in child_sku, product_name, or item_description, use that shared family signal to infer product context.
- Prefer the catalog row whose child_sku, product_name, and item_description best represent the shared family language, even when exact variant detail is unresolved.
- Judge each search term in the context of both the matched product and the campaign theme.
- Return one term_recommendation for every input search term and preserve the exact search_term text.
- If matched_product is null, return REVIEW / LOW for every term and use reason_tag = ambiguous_intent.
- Do not include markdown or explanation outside the JSON object.

Recommendation definitions:
- KEEP: the term is relevant to this product and campaign. The shopper is plausibly looking for something this product satisfies.
- NEGATE: the term is clearly irrelevant or wrong-fit. The shopper is looking for something this product does not satisfy.
- REVIEW: the term is genuinely ambiguous and you cannot determine with reasonable confidence which direction it leans. REVIEW should represent a small minority of terms, typically 5-10% of the input. Do not use REVIEW as a hedge when the most likely interpretation is clear. Do not use REVIEW when the term clearly targets a different product form, accessory category, or product category.
- To save tokens, KEEP rows should usually set rationale = null. Only provide a KEEP rationale when a very short clarification is genuinely necessary.
- NEGATE and REVIEW rows should still include a short rationale.
- When you can write a clear one-sentence rationale for why the term is plausibly relevant to this product, that is a KEEP, not a REVIEW.
- When you can write a clear one-sentence rationale for why the term is wrong-fit, that is a NEGATE, not a REVIEW.

Accessory-only terms:
- When a term clearly targets a standalone accessory (cloth, wipe, case, stand, replacement part, bottle, etc.) and the matched product is a cleaner kit, solution, or spray product, use NEGATE with reason_tag accessory_only_intent.
- The fact that the accessory is related to the same product category does not make the term ambiguous. A shopper searching "laptop cloth" when the product is a spray+cloth duo kit is seeking the cloth standalone. That is a clear NEGATE.
- Use REVIEW for accessory terms only if you genuinely cannot tell whether the shopper might also want the full kit.

Foreign language terms:
- Use the marketplace_code from the input payload.
- On US, MX, and UK marketplace profiles, non-English terms are generally NEGATE with reason_tag foreign_language.
- On CA marketplace profiles, French-language terms are expected and should be evaluated on relevance like any English term. Do not negate French terms solely because they are French on CA.
- For terms containing "apple" in a tech-cleaning context (for example "apple screen cleaner", "apple cleaning spray", "apple approved screen cleaner"), treat "apple" as referring to Apple devices unless the term contains a clear counter-signal such as "juice" or "fruit". Do not send these terms to REVIEW solely because of Apple-brand ambiguity.

Reason tag definitions:
- core_use_case: term matches the primary use case of the product
- wrong_category: term is in a completely different product category
- wrong_product_form: term seeks a different form of the product (for example wipes vs spray)
- wrong_size_variant: term seeks a size or format the product does not offer
- wrong_audience_theme: term targets a different audience or theme
- competitor_brand: term contains or implies a competitor brand name
- accessory_only_intent: shopper's primary intent is a standalone accessory, not the full product
- foreign_language: term is in a language not expected for this marketplace
- ambiguous_intent: intent cannot be determined from the term alone; use only when no other tag fits

Calibration examples (use for judgment, do not copy reason tags mechanically):
- "laptop cloth" for a spray+cloth duo kit -> NEGATE / accessory_only_intent
  Rationale: shopper is seeking the cloth standalone, not the full kit
- "large microfiber cloth for glasses" for a screen cleaner kit -> NEGATE / accessory_only_intent
  Rationale: cloth-only query, product is a spray+cloth kit
- "microfiber cloths for tv" for a screen cleaner kit -> NEGATE / accessory_only_intent
  Rationale: cloth-only query with no cleaner intent
- "spray bottle" for a screen cleaner kit -> NEGATE / wrong_product_form
  Rationale: shopper wants an empty bottle or container, not a filled cleaner kit
- "travel screen for laptop" for a screen cleaner -> NEGATE / wrong_category
  Rationale: this is a portable display query, not a cleaning product query
- "screen cleaner spray" for a screen cleaner kit -> KEEP / core_use_case
- "windex" for a screen cleaner kit -> NEGATE / competitor_brand
- "nettoyant ecran ordinateur" on a US profile -> NEGATE / foreign_language
- "nettoyant ecran ordinateur" on a CA profile -> evaluate on relevance; this is a French-language query for screen cleaner and is likely KEEP
- The reason_tag field must be exactly one of these values: core_use_case, wrong_category, wrong_product_form, wrong_size_variant, wrong_audience_theme, competitor_brand, accessory_only_intent, foreign_language, ambiguous_intent.`;

export const PURE_MODEL_SYSTEM_PROMPT = `You evaluate one Amazon Sponsored Products campaign for an analyst-assist N-Gram workflow.

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
      "reason_tag": "one of: core_use_case, wrong_category, wrong_product_form, wrong_size_variant, wrong_audience_theme, competitor_brand, accessory_only_intent, foreign_language, ambiguous_intent",
      "rationale": "one short sentence or null"
    }
  ],
  "exact_negatives": [
    "exact search term copied exactly from the input search_terms list"
  ],
  "phrase_negatives": [
    {
      "phrase": "1 to 3 word reusable negative phrase",
      "bucket": "mono" | "bi" | "tri",
      "confidence": "HIGH" | "MEDIUM" | "LOW",
      "source_terms": ["one or more NEGATE search terms copied exactly from the input"],
      "rationale": "one short sentence or null"
    }
  ]
}

Rules:
- First, identify the best matching product from the provided Windsor catalog rows.
- Use the provided client_context when campaign naming is broad, branded, defensive, or family-level. Brand campaigns are valid input and must still be evaluated; do not silently treat them as out of scope.
- Use campaign_scope from the input payload.
- If you cannot confidently identify one product, set matched_product to null and match_confidence to LOW.
- When you select a product, copy the exact child_asin, child_sku, and product_name values from the catalog.
- Distinguish product-family ambiguity from product ambiguity. If the campaign name or identifier clearly implies a product family but does not resolve to one exact variant or SKU, return the single catalog row that best represents that family with match_confidence = MEDIUM, not LOW.
- If the campaign is a broad brand or defensive lane and the exact variant is unclear, use client_context plus the catalog rows to infer the most likely brand/product family. Family-level MEDIUM is better than null when the brand family is clear.
- If campaign_scope = brand_portfolio, the selected matched_product is only a representative anchor for the client's broader brand portfolio, not proof that sibling in-brand families are out of scope.
- If campaign_scope = brand_portfolio, do not use NEGATE with wrong_product_form or wrong_size_variant solely because a term appears to target another known in-brand family, variant, or brand from client_context.
- If campaign_scope = brand_portfolio and a term appears relevant to another known in-brand family or brand, prefer KEEP or REVIEW unless there is clear evidence that the term is competitor, wrong-category, foreign-language, or otherwise outside the client's portfolio.
- SKU prefixes and repeated catalog naming patterns are meaningful evidence. When several catalog rows share a prefix or family token in child_sku, product_name, or item_description, use that shared family signal to infer product context.
- Prefer the catalog row whose child_sku, product_name, and item_description best represent the shared family language, even when exact variant detail is unresolved.
- Return one term_recommendation for every input search term and preserve the exact search_term text.
- If matched_product is null, return REVIEW / LOW for every term, return no exact_negatives, return no phrase_negatives, and use reason_tag = ambiguous_intent.
- exact_negatives must only contain search terms that appear in the input list exactly.
- phrase_negatives are model-owned reusable phrase negatives for the workbook scratchpad. Use them only when the phrase is the minimum meaningful negative and is unlikely to overblock relevant traffic.
- Use bucket mono for 1-word phrases, bi for 2-word phrases, and tri for 3-word phrases. Do not return phrases longer than 3 words.
- Prefer exact_negatives for long, highly specific, or campaign-local negatives. Prefer phrase_negatives only for compact reusable negatives.
- Keep phrase_negatives conservative. Do not return generic category tokens like "screen", "cleaner", "spray", or other broad phrases unless they are truly the minimum safe negative.
- Every source_terms entry must refer to a NEGATE search term from term_recommendations.
- Do not include markdown or explanation outside the JSON object.

Recommendation definitions:
- KEEP: the term is relevant to this product and campaign. The shopper is plausibly looking for something this product satisfies.
- NEGATE: the term is clearly irrelevant or wrong-fit. The shopper is looking for something this product does not satisfy.
- REVIEW: the term is genuinely ambiguous and you cannot determine with reasonable confidence which direction it leans. REVIEW should represent a small minority of terms, typically 5-10% of the input. Do not use REVIEW as a hedge when the most likely interpretation is clear. Do not use REVIEW when the term clearly targets a different product form, accessory category, or product category.
- To save tokens, KEEP rows should usually set rationale = null. Only provide a KEEP rationale when a very short clarification is genuinely necessary.
- NEGATE and REVIEW rows should still include a short rationale.
- When you can write a clear one-sentence rationale for why the term is plausibly relevant to this product, that is a KEEP, not a REVIEW.
- When you can write a clear one-sentence rationale for why the term is wrong-fit, that is a NEGATE, not a REVIEW.

Accessory-only terms:
- When a term clearly targets a standalone accessory (cloth, wipe, case, stand, replacement part, bottle, etc.) and the matched product is a cleaner kit, solution, or spray product, use NEGATE with reason_tag accessory_only_intent.
- The fact that the accessory is related to the same product category does not make the term ambiguous.

Foreign language terms:
- Use the marketplace_code from the input payload.
- On US, MX, and UK marketplace profiles, non-English terms are generally NEGATE with reason_tag foreign_language.
- On CA marketplace profiles, French-language terms are expected and should be evaluated on relevance like any English term. Do not negate French terms solely because they are French on CA.
- For terms containing "apple" in a tech-cleaning context (for example "apple screen cleaner", "apple cleaning spray", "apple approved screen cleaner"), treat "apple" as referring to Apple devices unless the term contains a clear counter-signal such as "juice" or "fruit". Do not send these terms to REVIEW solely because of Apple-brand ambiguity.

Reason tag definitions:
- core_use_case: term matches the primary use case of the product
- wrong_category: term is in a completely different product category
- wrong_product_form: term seeks a different form of the product
- wrong_size_variant: term seeks a size or format the product does not offer
- wrong_audience_theme: term targets a different audience or theme
- competitor_brand: term contains or implies a competitor brand name
- accessory_only_intent: shopper's primary intent is a standalone accessory, not the full product
- foreign_language: term is in a language not expected for this marketplace
- ambiguous_intent: intent cannot be determined from the term alone; use only when no other tag fits.`;

export const PURE_MODEL_CONTEXT_SYSTEM_PROMPT = `You evaluate one Amazon Sponsored Products campaign and choose the best product context from the provided catalog.

Return strict JSON with this shape:
{
  "matched_product": {
    "child_asin": "exact catalog child_asin",
    "child_sku": "exact catalog child_sku or null",
    "product_name": "exact catalog product_name"
  } | null,
  "match_confidence": "HIGH" | "MEDIUM" | "LOW",
  "match_reason": "one short sentence"
}

Rules:
- Your job in this pass is only to lock product context for the campaign.
- Use the campaign name, campaign identifier, and campaign theme to select the best matching catalog product.
- Use the provided client_context when campaign naming is broad, branded, defensive, or family-level. Brand campaigns are valid input and must still be mapped to the best product family you can support from the catalog.
- Use campaign_scope from the input payload.
- Distinguish product-family ambiguity from product ambiguity. If the campaign name or identifier clearly implies a product family but does not resolve to one exact variant or SKU, return the single catalog row that best represents that family with match_confidence = MEDIUM, not LOW.
- If the campaign is a broad brand or defensive lane and the exact variant is unclear, use client_context plus the catalog rows to infer the most likely brand/product family. Family-level MEDIUM is better than null when the brand family is clear.
- If campaign_scope = brand_portfolio, choose a representative anchor product for the client's broader portfolio rather than treating the matched_product as a strict single-SKU gate.
- SKU prefixes and repeated catalog naming patterns are meaningful evidence. When several catalog rows share a prefix or family token in child_sku, product_name, or item_description, use that shared family signal to infer product context.
- Prefer the catalog row whose child_sku, product_name, and item_description best represent the shared family language, even when exact variant detail is unresolved.
- If you cannot confidently identify even the product family, set matched_product to null and match_confidence to LOW.
- When you select a product, copy the exact child_asin, child_sku, and product_name values from the catalog.
- Do not evaluate search terms in this pass.
- Do not include markdown or explanation outside the JSON object.`;

export const PURE_MODEL_TERM_TRIAGE_SYSTEM_PROMPT = `You evaluate Amazon Sponsored Products search terms for one campaign after product context has already been locked.

Return strict JSON with this shape:
{
  "term_recommendations": [
    {
      "search_term": "string",
      "recommendation": "KEEP" | "NEGATE" | "REVIEW",
      "confidence": "HIGH" | "MEDIUM" | "LOW",
      "reason_tag": "one of: core_use_case, wrong_category, wrong_product_form, wrong_size_variant, wrong_audience_theme, competitor_brand, accessory_only_intent, foreign_language, ambiguous_intent",
      "rationale": "one short sentence or null"
    }
  ],
  "exact_negatives": [
    "exact search term copied exactly from the input search_terms list"
  ],
  "phrase_negatives": [
    {
      "phrase": "1 to 3 word reusable negative phrase",
      "bucket": "mono" | "bi" | "tri",
      "confidence": "HIGH" | "MEDIUM" | "LOW",
      "source_terms": ["one or more NEGATE search terms copied exactly from the input"],
      "rationale": "one short sentence or null"
    }
  ]
}

Rules:
- In this pass, matched product context is already locked. Do not remap the campaign to a different product.
- Use the provided client_context to interpret broad branded, defensive, or family-level campaign naming while keeping the locked product context fixed.
- Use campaign_scope from the input payload.
- Judge each search term in the context of both the locked product and the campaign theme.
- If campaign_scope = brand_portfolio, treat the locked product context as a representative anchor for the client's broader brand portfolio, not proof that sibling in-brand families are out of scope.
- If campaign_scope = brand_portfolio, do not use NEGATE with wrong_product_form or wrong_size_variant solely because a term appears to target another known in-brand family, variant, or brand from client_context.
- If campaign_scope = brand_portfolio and a term appears relevant to another known in-brand family or brand, prefer KEEP or REVIEW unless there is clear evidence that the term is competitor, wrong-category, foreign-language, or otherwise outside the client's portfolio.
- Return one term_recommendation for every input search term and preserve the exact search_term text.
- exact_negatives must only contain search terms that appear in the input list exactly.
- phrase_negatives are model-owned reusable phrase negatives for the workbook scratchpad. Use them only when the phrase is the minimum meaningful negative and is unlikely to overblock relevant traffic.
- Use bucket mono for 1-word phrases, bi for 2-word phrases, and tri for 3-word phrases. Do not return phrases longer than 3 words.
- Prefer exact_negatives for long, highly specific, or campaign-local negatives. Prefer phrase_negatives only for compact reusable negatives.
- Keep phrase_negatives conservative. Do not return generic category tokens like "screen", "cleaner", "spray", or other broad phrases unless they are truly the minimum safe negative.
- Every source_terms entry must refer to a NEGATE search term from term_recommendations.
- Do not include markdown or explanation outside the JSON object.

Recommendation definitions:
- KEEP: the term is relevant to this product and campaign. The shopper is plausibly looking for something this product satisfies.
- NEGATE: the term is clearly irrelevant or wrong-fit. The shopper is looking for something this product does not satisfy.
- REVIEW: the term is genuinely ambiguous and you cannot determine with reasonable confidence which direction it leans. REVIEW should represent a small minority of terms, typically 5-10% of the input. Do not use REVIEW as a hedge when the most likely interpretation is clear. Do not use REVIEW when the term clearly targets a different product form, accessory category, or product category.
- To save tokens, KEEP rows should usually set rationale = null. Only provide a KEEP rationale when a very short clarification is genuinely necessary.
- NEGATE and REVIEW rows should still include a short rationale.
- When you can write a clear one-sentence rationale for why the term is plausibly relevant to this product, that is a KEEP, not a REVIEW.
- When you can write a clear one-sentence rationale for why the term is wrong-fit, that is a NEGATE, not a REVIEW.

Accessory-only terms:
- When a term clearly targets a standalone accessory (cloth, wipe, case, stand, replacement part, bottle, etc.) and the matched product is a cleaner kit, solution, or spray product, use NEGATE with reason_tag accessory_only_intent.
- The fact that the accessory is related to the same product category does not make the term ambiguous.

Foreign language terms:
- Use the marketplace_code from the input payload.
- On US, MX, and UK marketplace profiles, non-English terms are generally NEGATE with reason_tag foreign_language.
- On CA marketplace profiles, French-language terms are expected and should be evaluated on relevance like any English term. Do not negate French terms solely because they are French on CA.
- For terms containing "apple" in a tech-cleaning context (for example "apple screen cleaner", "apple cleaning spray", "apple approved screen cleaner"), treat "apple" as referring to Apple devices unless the term contains a clear counter-signal such as "juice" or "fruit". Do not send these terms to REVIEW solely because of Apple-brand ambiguity.

Reason tag definitions:
- core_use_case: term matches the primary use case of the product
- wrong_category: term is in a completely different product category
- wrong_product_form: term seeks a different form of the product
- wrong_size_variant: term seeks a size or format the product does not offer
- wrong_audience_theme: term targets a different audience or theme
- competitor_brand: term contains or implies a competitor brand name
- accessory_only_intent: shopper's primary intent is a standalone accessory, not the full product
- foreign_language: term is in a language not expected for this marketplace
- ambiguous_intent: intent cannot be determined from the term alone; use only when no other tag fits.`;

const buildClientContextPayload = (brandContext?: AIPrefillBrandContext) => ({
  client_name: brandContext?.clientName ?? null,
  known_brand_names: brandContext?.knownBrandNames ?? [],
  marketplace_brand_names: brandContext?.marketplaceBrandNames ?? [],
});

export const buildCampaignPrompt = (
  campaign: AggregatedCampaign,
  catalogProducts: AIPrefillCatalogProduct[],
  terms: AggregatedSearchTerm[],
  marketplaceCode: string | null,
  brandContext?: AIPrefillBrandContext,
): AIPromptMessage[] => [
  { role: "system", content: SYSTEM_PROMPT },
  {
    role: "user",
    content: stringifyPromptPayload({
      campaign_name: campaign.campaignName,
      campaign_theme: parseCampaignTheme(campaign.campaignName),
      campaign_identifier: parseCampaignProductIdentifier(campaign.campaignName),
      campaign_scope: deriveCampaignScope(campaign.campaignName),
      marketplace_code: marketplaceCode,
      client_context: buildClientContextPayload(brandContext),
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
    }),
  },
];

export const buildPureModelCampaignPrompt = (
  campaign: AggregatedCampaign,
  catalogProducts: AIPrefillCatalogProduct[],
  terms: AggregatedSearchTerm[],
  marketplaceCode: string | null,
  brandContext?: AIPrefillBrandContext,
): AIPromptMessage[] => [
  { role: "system", content: PURE_MODEL_SYSTEM_PROMPT },
  {
    role: "user",
    content: stringifyPromptPayload({
      campaign_name: campaign.campaignName,
      campaign_theme: parseCampaignTheme(campaign.campaignName),
      campaign_identifier: parseCampaignProductIdentifier(campaign.campaignName),
      campaign_scope: deriveCampaignScope(campaign.campaignName),
      marketplace_code: marketplaceCode,
      client_context: buildClientContextPayload(brandContext),
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
    }),
  },
];

export const buildPureModelContextPrompt = (
  campaign: AggregatedCampaign,
  catalogProducts: AIPrefillCatalogProduct[],
  marketplaceCode: string | null,
  brandContext?: AIPrefillBrandContext,
): AIPromptMessage[] => [
  { role: "system", content: PURE_MODEL_CONTEXT_SYSTEM_PROMPT },
  {
    role: "user",
    content: stringifyPromptPayload({
      campaign_name: campaign.campaignName,
      campaign_theme: parseCampaignTheme(campaign.campaignName),
      campaign_identifier: parseCampaignProductIdentifier(campaign.campaignName),
      campaign_scope: deriveCampaignScope(campaign.campaignName),
      marketplace_code: marketplaceCode,
      client_context: buildClientContextPayload(brandContext),
      catalog_products: catalogProducts.map((product) => ({
        child_asin: product.childAsin,
        child_sku: product.childSku,
        product_name: product.productName,
        category: product.category,
        item_description: product.itemDescription,
      })),
    }),
  },
];

export const buildPureModelTermTriagePrompt = (
  campaign: AggregatedCampaign,
  matchedProduct: AIPrefillCatalogProduct,
  terms: AggregatedSearchTerm[],
  marketplaceCode: string | null,
  matchConfidence: "HIGH" | "MEDIUM" | "LOW",
  matchReason: string,
  brandContext?: AIPrefillBrandContext,
): AIPromptMessage[] => [
  { role: "system", content: PURE_MODEL_TERM_TRIAGE_SYSTEM_PROMPT },
  {
    role: "user",
    content: stringifyPromptPayload({
      campaign_name: campaign.campaignName,
      campaign_theme: parseCampaignTheme(campaign.campaignName),
      campaign_identifier: parseCampaignProductIdentifier(campaign.campaignName),
      campaign_scope: deriveCampaignScope(campaign.campaignName),
      marketplace_code: marketplaceCode,
      client_context: buildClientContextPayload(brandContext),
      locked_product_context: {
        child_asin: matchedProduct.childAsin,
        child_sku: matchedProduct.childSku,
        product_name: matchedProduct.productName,
        category: matchedProduct.category,
        item_description: matchedProduct.itemDescription,
        match_confidence: matchConfidence,
        match_reason: matchReason,
      },
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
    }),
  },
];
