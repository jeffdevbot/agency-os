export type SearchTermFactRow = {
  report_date: string;
  campaign_name: string;
  search_term: string;
  impressions: number | string | null;
  clicks: number | string | null;
  spend: number | string | null;
  orders: number | string | null;
  sales: number | string | null;
  keyword: string | null;
  keyword_type: string | null;
  targeting: string | null;
  match_type: string | null;
};

export type NgramListingRow = {
  child_asin: string | null;
  child_sku: string | null;
  child_product_name: string | null;
  parent_title: string | null;
  category: string | null;
  item_description: string | null;
};

export type AggregatedSearchTerm = {
  campaignName: string;
  searchTerm: string;
  impressions: number;
  clicks: number;
  spend: number;
  orders: number;
  sales: number;
  keyword: string | null;
  keywordType: string | null;
  targeting: string | null;
  matchType: string | null;
};

export type CampaignProductMatch = {
  status: "matched" | "ambiguous" | "intentionally_skipped";
  identifier: string | null;
  matchedTitle: string | null;
  category: string | null;
  itemDescription: string | null;
  score: number | null;
  theme: string | null;
  matchSource: "deterministic" | "ai_fallback" | "ai_combined" | "none";
  skipReason: "brand_mix_defensive" | "missing_identifier" | null;
  candidates: Array<{
    title: string;
    category: string | null;
    itemDescription: string | null;
    score: number;
    familyKey: string;
  }>;
};

export type AIPrefillEvaluation = {
  search_term: string;
  recommendation: "KEEP" | "NEGATE" | "REVIEW";
  confidence: "HIGH" | "MEDIUM" | "LOW";
  reason_tag: string;
  rationale: string | null;
  spend: number;
  clicks: number;
  orders: number;
  sales: number;
  keyword: string | null;
  keywordType: string | null;
  targeting: string | null;
  matchType: string | null;
};

export type SynthesizedGram = {
  gram: string;
  supportTerms: string[];
  negateCount: number;
  keepCount: number;
  reviewCount: number;
  negateSpend: number;
  weightedScore: number;
};

export type CampaignPrefillScratchpad = {
  mono: SynthesizedGram[];
  bi: SynthesizedGram[];
  tri: SynthesizedGram[];
};

export type PhraseNegativeBucket = "mono" | "bi" | "tri";

export type PureModelPhraseNegative = {
  phrase: string;
  bucket: PhraseNegativeBucket;
  confidence: "HIGH" | "MEDIUM" | "LOW";
  sourceTerms: string[];
  rationale: string | null;
};

export type CampaignModelPrefills = {
  exact: string[];
  mono: string[];
  bi: string[];
  tri: string[];
};

export type AIPrefillStrategy = "heuristic_synthesis" | "pure_model_single_campaign";

export type AggregatedCampaign = {
  campaignName: string;
  totalSpend: number;
  termCount: number;
  terms: AggregatedSearchTerm[];
};

export type PreparedListingCatalog = {
  commonTokens: Set<string>;
  tokenFrequency: Map<string, number>;
  listings: Array<{
    title: string;
    normalizedTitle: string;
    familyTokens: string[];
    familyKey: string;
    category: string | null;
    itemDescription: string | null;
  }>;
};

export type AIPrefillCatalogProduct = {
  childAsin: string;
  childSku: string | null;
  productName: string;
  category: string | null;
  itemDescription: string | null;
};

export type AIPrefillRunMode = "preview" | "full";

export const ALLOWED_REASON_TAGS = [
  "core_use_case",
  "wrong_category",
  "wrong_product_form",
  "wrong_size_variant",
  "wrong_audience_theme",
  "competitor_brand",
  "cloth_primary_intent",
  "accessory_only_intent",
  "foreign_language",
  "ambiguous_intent",
] as const;

export type AIPrefillReasonTag = (typeof ALLOWED_REASON_TAGS)[number];

export type AIPrefillTermRecommendation = {
  search_term: string;
  recommendation: "KEEP" | "NEGATE" | "REVIEW";
  confidence: "HIGH" | "MEDIUM" | "LOW";
  reason_tag: AIPrefillReasonTag;
  rationale: string | null;
};

export type ValidatedAIPrefillCampaignResponse = {
  matchedProduct: AIPrefillCatalogProduct | null;
  matchConfidence: "HIGH" | "MEDIUM" | "LOW";
  matchReason: string;
  termRecommendations: AIPrefillTermRecommendation[];
};

export type ValidatedPureModelCampaignResponse = ValidatedAIPrefillCampaignResponse & {
  exactNegatives: string[];
  phraseNegatives: PureModelPhraseNegative[];
  modelPrefills: CampaignModelPrefills;
};

export const AI_PREFILL_PREVIEW_MAX_CAMPAIGNS = 6;
export const AI_PREFILL_PREVIEW_MAX_TERMS_PER_CAMPAIGN = 20;

export const LEGACY_EXCLUSION_MARKERS = ["Ex.", "SDI", "SDV"] as const;
export const ASIN_QUERY_RE = /^[a-z0-9]{10}$/i;

const STOP_WORDS = new Set([
  "the",
  "and",
  "for",
  "with",
  "a",
  "an",
  "of",
  "oz",
  "fl",
  "ml",
  "l",
  "pack",
  "packs",
  "count",
  "ct",
  "bottle",
  "bottles",
]);

const SYNTHESIS_BOUNDARY_TOKENS = new Set([
  ...STOP_WORDS,
  "to",
  "from",
  "in",
  "on",
  "at",
  "by",
  "de",
  "para",
  "y",
  "la",
  "el",
  "los",
  "las",
  "en",
  "con",
]);

const SYNTHESIS_GENERIC_MONOGRAMS = new Set([
  "screen",
  "screens",
  "clean",
  "cleaner",
  "cleaning",
  "cloth",
  "cloths",
  "wipe",
  "wipes",
  "spray",
  "sprays",
  "liquid",
  "liquido",
  "kit",
  "kits",
  "case",
  "cases",
  "remove",
  "remover",
  "scratch",
  "scratches",
  "glass",
  "glasses",
  "monitor",
  "monitors",
  "display",
  "displays",
  "phone",
  "phones",
  "tv",
  "tvs",
  "tablet",
  "tablets",
  "laptop",
  "laptops",
  "computer",
  "computers",
  "ipad",
  "iphone",
  "macbook",
  "touchpad",
  "mousepad",
  "televisor",
  "television",
  "televisión",
  "pantalla",
  "pantallas",
  "limpiador",
  "limpiar",
  "limpieza",
  "de",
  "para",
  "y",
]);

const SYNTHESIS_GENERIC_DESCRIPTOR_TOKENS = new Set([
  ...SYNTHESIS_GENERIC_MONOGRAMS,
  "solution",
  "solutions",
  "polish",
  "polishing",
  "streak",
  "free",
  "dust",
  "duster",
  "foam",
  "foaming",
  "pad",
  "pads",
  "protector",
  "protectors",
  "set",
  "sets",
  "glossy",
  "gloss",
  "anti",
  "cleaned",
  "cleans",
  "microfiber",
  "micro",
  "fiber",
  "flat",
  "smart",
  "large",
  "outside",
]);

const QUERY_TOKEN_RE = /[^\w\s\-"'®©™°&+#]+/gu;
const PRODUCT_TOKEN_RE = /[^\w\s]+/g;
const PRODUCT_ABBREVIATIONS: Array<[RegExp, string]> = [
  [/\bxxl\b/g, "extra extra large"],
  [/\bxl\b/g, "extra large"],
  [/\bpk\b/g, "pack"],
];

const toNumber = (value: number | string | null | undefined): number => {
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  if (typeof value === "string") {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
};

export const parseCampaignProductIdentifier = (campaignName: string): string | null => {
  const firstChunk = String(campaignName || "")
    .split("|")[0]
    ?.trim();
  if (!firstChunk) return null;
  if (/^brand$/i.test(firstChunk)) return null;
  return firstChunk;
};

export const isIntentionallySkippedCampaign = (campaignName: string): boolean => {
  const parts = String(campaignName || "")
    .split("|")
    .map((part) => part.trim().toLowerCase())
    .filter(Boolean);

  const firstChunk = parts[0] ?? "";
  if (firstChunk === "brand") return true;
  if (parts.includes("mix.") || parts.includes("mix")) return true;
  if (parts.includes("def") || parts.includes("def.")) return true;
  return false;
};

export const isExpectedAmbiguousCampaign = (campaignName: string): boolean =>
  isIntentionallySkippedCampaign(campaignName);

export const parseCampaignTheme = (campaignName: string): string | null => {
  const parts = String(campaignName || "")
    .split("|")
    .map((part) => part.trim())
    .filter(Boolean);

  for (const part of parts) {
    if (/^\d+\s*-\s*/.test(part)) {
      return part.replace(/^\d+\s*-\s*/, "").trim() || null;
    }
  }

  const mixPart = parts.find((part) => /^mix\.?$/i.test(part));
  if (mixPart) return mixPart.toLowerCase();

  return null;
};

export const isLegacyExcludedCampaign = (campaignName: string): boolean =>
  LEGACY_EXCLUSION_MARKERS.some((marker) => String(campaignName || "").includes(marker));

export const isAsinQuery = (query: string | null | undefined): boolean =>
  ASIN_QUERY_RE.test(String(query || "").trim());

export const normalizeProductMatcherText = (value: string | null | undefined): string => {
  let normalized = String(value || "")
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(PRODUCT_TOKEN_RE, " ")
    .replace(/\s+/g, " ")
    .trim();

  for (const [pattern, replacement] of PRODUCT_ABBREVIATIONS) {
    normalized = normalized.replace(pattern, replacement);
  }

  return normalized.replace(/\s+/g, " ").trim();
};

const isMeaningfulProductToken = (token: string): boolean =>
  Boolean(token) && !STOP_WORDS.has(token) && !/^\d+$/.test(token);

export const cleanQueryForNgrams = (value: string | null | undefined): string =>
  String(value || "")
    .trim()
    .toLowerCase()
    .replace(QUERY_TOKEN_RE, " ")
    .replace(/_+/g, " ")
    .replace(/-{2,}/g, "-")
    .replace(/\s+/g, " ")
    .trim();

const tokenize = (value: string | null | undefined): string[] =>
  normalizeProductMatcherText(value)
    .split(" ")
    .filter(isMeaningfulProductToken);

export const buildNgramsForQuery = (query: string | null | undefined, size: 1 | 2 | 3): string[] => {
  const tokens = cleanQueryForNgrams(query)
    .split(" ")
    .filter(Boolean);

  if (tokens.length < size) return [];
  const grams: string[] = [];
  for (let index = 0; index <= tokens.length - size; index += 1) {
    grams.push(tokens.slice(index, index + size).join(" "));
  }
  return grams;
};

const dedupeTokens = (tokens: string[]): string[] => [...new Set(tokens)];

const toNonEmptyString = (value: unknown): string => String(value || "").trim();

const parseRecommendationStrict = (value: unknown): "KEEP" | "NEGATE" | "REVIEW" => {
  const normalized = toNonEmptyString(value).toUpperCase();
  if (normalized === "KEEP" || normalized === "NEGATE" || normalized === "REVIEW") {
    return normalized;
  }
  throw new Error(`Invalid recommendation: ${String(value || "")}`);
};

const parseConfidenceStrict = (value: unknown): "HIGH" | "MEDIUM" | "LOW" => {
  const normalized = toNonEmptyString(value).toUpperCase();
  if (normalized === "HIGH" || normalized === "MEDIUM" || normalized === "LOW") {
    return normalized;
  }
  throw new Error(`Invalid confidence: ${String(value || "")}`);
};

const normalizeReasonTag = (value: unknown): AIPrefillReasonTag => {
  const raw = toNonEmptyString(value).toLowerCase();
  if (!raw) throw new Error("Missing reason_tag");
  if ((ALLOWED_REASON_TAGS as readonly string[]).includes(raw)) {
    return raw as AIPrefillReasonTag;
  }
  throw new Error(
    `Invalid reason_tag: ${raw}. Allowed values: ${ALLOWED_REASON_TAGS.join(", ")}`,
  );
};

const normalizeRationale = (value: unknown): string | null => {
  const raw = toNonEmptyString(value);
  return raw ? raw.slice(0, 240) : null;
};

const normalizePhraseBucket = (value: unknown): PhraseNegativeBucket => {
  const raw = toNonEmptyString(value).toLowerCase();
  if (raw === "mono" || raw === "bi" || raw === "tri") {
    return raw;
  }
  throw new Error(`Invalid phrase bucket: ${String(value || "")}`);
};

const expectedPhraseTokenCount = (bucket: PhraseNegativeBucket): 1 | 2 | 3 => {
  if (bucket === "mono") return 1;
  if (bucket === "bi") return 2;
  return 3;
};

const normalizePhraseNegative = (value: unknown, bucket: PhraseNegativeBucket): string => {
  const cleaned = cleanQueryForNgrams(toNonEmptyString(value));
  if (!cleaned) {
    throw new Error("Phrase negative cannot be blank.");
  }

  const tokenCount = cleaned.split(" ").filter(Boolean).length;
  if (tokenCount !== expectedPhraseTokenCount(bucket)) {
    throw new Error(
      `Phrase negative "${cleaned}" does not match bucket ${bucket} (${expectedPhraseTokenCount(bucket)} token(s) required).`,
    );
  }

  return cleaned;
};

const buildFamilyTokens = (normalized: string, commonTokens: Set<string>): string[] => {
  const tokens = dedupeTokens(normalized.split(" ").filter(isMeaningfulProductToken));
  const withoutCommon = tokens.filter((token) => !commonTokens.has(token));
  return withoutCommon.length > 0 ? withoutCommon : tokens;
};

export const buildPreparedListingCatalog = (listings: NgramListingRow[]): PreparedListingCatalog => {
  const baseListings = listings
    .map((listing) => {
      const title = String(listing.child_product_name || listing.parent_title || "").trim();
      if (!title) return null;
      return {
        title,
        normalizedTitle: normalizeProductMatcherText(title),
        category: listing.category || null,
        itemDescription: listing.item_description || null,
      };
    })
    .filter((listing): listing is NonNullable<typeof listing> => Boolean(listing));

  const tokenFrequency = new Map<string, number>();
  for (const listing of baseListings) {
    const tokens = dedupeTokens(listing.normalizedTitle.split(" ").filter(isMeaningfulProductToken));
    for (const token of tokens) {
      tokenFrequency.set(token, (tokenFrequency.get(token) ?? 0) + 1);
    }
  }

  const commonTokenThreshold = Math.max(2, Math.ceil(baseListings.length * 0.6));
  const commonTokens = new Set(
    [...tokenFrequency.entries()]
      .filter(([, count]) => count >= commonTokenThreshold)
      .map(([token]) => token),
  );

  return {
    commonTokens,
    tokenFrequency,
    listings: baseListings.map((listing) => {
      const familyTokens = buildFamilyTokens(listing.normalizedTitle, commonTokens);
      return {
        ...listing,
        familyTokens,
        familyKey: familyTokens.join(" "),
      };
    }),
  };
};

export const prepareAIPrefillCatalogProducts = (listings: NgramListingRow[]): AIPrefillCatalogProduct[] => {
  const deduped = new Map<string, AIPrefillCatalogProduct>();

  for (const listing of listings) {
    const childAsin = toNonEmptyString(listing.child_asin);
    const productName = toNonEmptyString(listing.child_product_name || listing.parent_title);
    if (!childAsin || !productName) continue;

    const existing = deduped.get(childAsin);
    const candidate: AIPrefillCatalogProduct = {
      childAsin,
      childSku: toNonEmptyString(listing.child_sku) || null,
      productName,
      category: toNonEmptyString(listing.category) || null,
      itemDescription: toNonEmptyString(listing.item_description) || null,
    };

    if (!existing) {
      deduped.set(childAsin, candidate);
      continue;
    }

    if (!existing.itemDescription && candidate.itemDescription) {
      deduped.set(childAsin, candidate);
    }
  }

  return [...deduped.values()].sort((left, right) => left.productName.localeCompare(right.productName));
};

export const validateAIPrefillCampaignResponse = (
  payload: unknown,
  catalogProducts: AIPrefillCatalogProduct[],
  expectedSearchTerms: string[],
): ValidatedAIPrefillCampaignResponse => {
  if (!payload || typeof payload !== "object") {
    throw new Error("AI response must be a JSON object.");
  }

  const raw = payload as Record<string, unknown>;
  const matchConfidence = parseConfidenceStrict(raw.match_confidence);
  const matchReason = toNonEmptyString(raw.match_reason).slice(0, 240);
  if (!matchReason) {
    throw new Error("AI response is missing match_reason.");
  }

  let matchedProduct: AIPrefillCatalogProduct | null = null;
  if (raw.matched_product != null) {
    if (typeof raw.matched_product !== "object") {
      throw new Error("matched_product must be an object or null.");
    }

    const matchedRaw = raw.matched_product as Record<string, unknown>;
    const childAsin = toNonEmptyString(matchedRaw.child_asin);
    if (!childAsin) {
      throw new Error("matched_product.child_asin is required when matched_product is present.");
    }

    const catalogRow = catalogProducts.find((product) => product.childAsin === childAsin);
    if (!catalogRow) {
      throw new Error(`matched_product.child_asin does not exist in catalog: ${childAsin}`);
    }

    const childSku = toNonEmptyString(matchedRaw.child_sku);
    const productName = toNonEmptyString(matchedRaw.product_name);
    if (childSku && catalogRow.childSku && childSku !== catalogRow.childSku) {
      throw new Error(`matched_product.child_sku does not match catalog row for ${childAsin}`);
    }
    if (productName && productName !== catalogRow.productName) {
      throw new Error(`matched_product.product_name does not match catalog row for ${childAsin}`);
    }

    matchedProduct = catalogRow;
  }

  if (matchConfidence !== "LOW" && !matchedProduct) {
    throw new Error("AI response must return a matched_product when match_confidence is HIGH or MEDIUM.");
  }
  if (matchConfidence === "LOW" && matchedProduct) {
    throw new Error("AI response must set matched_product to null when match_confidence is LOW.");
  }

  if (!Array.isArray(raw.term_recommendations)) {
    throw new Error("AI response is missing term_recommendations array.");
  }

  if (raw.term_recommendations.length !== expectedSearchTerms.length) {
    throw new Error(
      `AI response returned ${raw.term_recommendations.length} term recommendations for ${expectedSearchTerms.length} input terms.`,
    );
  }

  const expectedByKey = new Map(
    expectedSearchTerms.map((term) => [term.trim().toLowerCase(), term.trim()]),
  );
  const seen = new Set<string>();
  const recommendationsByKey = new Map<string, AIPrefillTermRecommendation>();

  for (const recommendation of raw.term_recommendations as Array<Record<string, unknown>>) {
    if (!recommendation || typeof recommendation !== "object") {
      throw new Error("Each term recommendation must be an object.");
    }

    const searchTerm = toNonEmptyString(recommendation.search_term);
    const key = searchTerm.toLowerCase();
    if (!searchTerm || !expectedByKey.has(key)) {
      throw new Error(`AI response included an unexpected search_term: ${searchTerm || "<empty>"}`);
    }
    if (seen.has(key)) {
      throw new Error(`AI response included a duplicate search_term: ${searchTerm}`);
    }
    seen.add(key);

    recommendationsByKey.set(key, {
      search_term: expectedByKey.get(key) || searchTerm,
      recommendation: parseRecommendationStrict(recommendation.recommendation),
      confidence: parseConfidenceStrict(recommendation.confidence),
      reason_tag: normalizeReasonTag(recommendation.reason_tag),
      rationale: normalizeRationale(recommendation.rationale),
    });
  }

  if (seen.size !== expectedSearchTerms.length) {
    const missingTerms = expectedSearchTerms.filter((term) => !seen.has(term.trim().toLowerCase()));
    throw new Error(`AI response is missing recommendations for: ${missingTerms.join(", ")}`);
  }

  return {
    matchedProduct,
    matchConfidence,
    matchReason,
    termRecommendations: expectedSearchTerms.map((term) => {
      const recommendation = recommendationsByKey.get(term.trim().toLowerCase());
      if (!recommendation) {
        throw new Error(`AI response is missing recommendation for ${term}`);
      }
      return recommendation;
    }),
  };
};

const validateSharedCampaignResponseBase = (
  payload: unknown,
  catalogProducts: AIPrefillCatalogProduct[],
  expectedSearchTerms: string[],
): {
  matchedProduct: AIPrefillCatalogProduct | null;
  matchConfidence: "HIGH" | "MEDIUM" | "LOW";
  matchReason: string;
  termRecommendations: AIPrefillTermRecommendation[];
  raw: Record<string, unknown>;
  expectedByKey: Map<string, string>;
  recommendationsByKey: Map<string, AIPrefillTermRecommendation>;
} => {
  if (!payload || typeof payload !== "object") {
    throw new Error("AI response must be a JSON object.");
  }

  const raw = payload as Record<string, unknown>;
  const validated = validateAIPrefillCampaignResponse(payload, catalogProducts, expectedSearchTerms);
  const expectedByKey = new Map(
    expectedSearchTerms.map((term) => [term.trim().toLowerCase(), term.trim()]),
  );
  const recommendationsByKey = new Map(
    validated.termRecommendations.map((recommendation) => [
      recommendation.search_term.trim().toLowerCase(),
      recommendation,
    ]),
  );

  return {
    ...validated,
    raw,
    expectedByKey,
    recommendationsByKey,
  };
};

export const validatePureModelCampaignResponse = (
  payload: unknown,
  catalogProducts: AIPrefillCatalogProduct[],
  expectedSearchTerms: string[],
): ValidatedPureModelCampaignResponse => {
  const {
    matchedProduct,
    matchConfidence,
    matchReason,
    termRecommendations,
    raw,
    expectedByKey,
    recommendationsByKey,
  } = validateSharedCampaignResponseBase(payload, catalogProducts, expectedSearchTerms);

  if (!Array.isArray(raw.exact_negatives)) {
    throw new Error("AI response is missing exact_negatives array.");
  }
  if (!Array.isArray(raw.phrase_negatives)) {
    throw new Error("AI response is missing phrase_negatives array.");
  }

  const exactSeen = new Set<string>();
  const exactNegatives: string[] = [];
  for (const value of raw.exact_negatives) {
    const searchTerm = toNonEmptyString(value);
    const key = searchTerm.toLowerCase();
    if (!searchTerm || !expectedByKey.has(key)) {
      throw new Error(`AI response included an unexpected exact negative: ${searchTerm || "<empty>"}`);
    }
    if (exactSeen.has(key)) {
      throw new Error(`AI response included a duplicate exact negative: ${searchTerm}`);
    }
    if (recommendationsByKey.get(key)?.recommendation !== "NEGATE") {
      throw new Error(`Exact negative must correspond to a NEGATE term recommendation: ${searchTerm}`);
    }
    exactSeen.add(key);
    exactNegatives.push(expectedByKey.get(key) || searchTerm);
  }

  const phraseSeen = new Set<string>();
  const phraseNegatives: PureModelPhraseNegative[] = [];
  for (const entry of raw.phrase_negatives as unknown[]) {
    if (!entry || typeof entry !== "object") {
      throw new Error("Each phrase negative must be an object.");
    }

    const phraseRaw = entry as Record<string, unknown>;
    const bucket = normalizePhraseBucket(phraseRaw.bucket);
    const phrase = normalizePhraseNegative(phraseRaw.phrase, bucket);
    const phraseKey = `${bucket}:${phrase.toLowerCase()}`;
    if (phraseSeen.has(phraseKey)) {
      throw new Error(`AI response included a duplicate phrase negative: ${phrase}`);
    }

    const rawSourceTerms = Array.isArray(phraseRaw.source_terms) ? phraseRaw.source_terms : null;
    if (!rawSourceTerms || rawSourceTerms.length === 0) {
      throw new Error(`Phrase negative "${phrase}" must include at least one source term.`);
    }

    const sourceTerms: string[] = [];
    const sourceSeen = new Set<string>();
    for (const sourceValue of rawSourceTerms) {
      const sourceTerm = toNonEmptyString(sourceValue);
      const key = sourceTerm.toLowerCase();
      if (!sourceTerm || !expectedByKey.has(key)) {
        throw new Error(`Phrase negative "${phrase}" referenced an unknown source term: ${sourceTerm || "<empty>"}`);
      }
      if (sourceSeen.has(key)) {
        throw new Error(`Phrase negative "${phrase}" repeated source term: ${sourceTerm}`);
      }
      if (recommendationsByKey.get(key)?.recommendation !== "NEGATE") {
        throw new Error(`Phrase negative "${phrase}" source term must be NEGATE: ${sourceTerm}`);
      }
      sourceSeen.add(key);
      sourceTerms.push(expectedByKey.get(key) || sourceTerm);
    }

    phraseSeen.add(phraseKey);
    phraseNegatives.push({
      phrase,
      bucket,
      confidence: parseConfidenceStrict(phraseRaw.confidence),
      sourceTerms,
      rationale: normalizeRationale(phraseRaw.rationale),
    });
  }

  const modelPrefills = buildCampaignModelPrefills(exactNegatives, phraseNegatives);

  return {
    matchedProduct,
    matchConfidence,
    matchReason,
    termRecommendations,
    exactNegatives,
    phraseNegatives,
    modelPrefills,
  };
};

const confidenceRank = (value: "HIGH" | "MEDIUM" | "LOW"): number => {
  if (value === "HIGH") return 3;
  if (value === "MEDIUM") return 2;
  return 1;
};

export const buildCampaignModelPrefills = (
  exactNegatives: string[],
  phraseNegatives: PureModelPhraseNegative[],
): CampaignModelPrefills => ({
  exact: [...exactNegatives],
  mono: phraseNegatives.filter((entry) => entry.bucket === "mono").map((entry) => entry.phrase),
  bi: phraseNegatives.filter((entry) => entry.bucket === "bi").map((entry) => entry.phrase),
  tri: phraseNegatives.filter((entry) => entry.bucket === "tri").map((entry) => entry.phrase),
});

export const mergePureModelCampaignResponses = (
  responses: ValidatedPureModelCampaignResponse[],
): ValidatedPureModelCampaignResponse => {
  if (responses.length === 0) {
    throw new Error("Cannot merge zero pure-model campaign responses.");
  }

  const canonical = [...responses].sort((left, right) => {
    const confidenceDelta = confidenceRank(right.matchConfidence) - confidenceRank(left.matchConfidence);
    if (confidenceDelta !== 0) return confidenceDelta;
    if (left.matchedProduct && !right.matchedProduct) return -1;
    if (!left.matchedProduct && right.matchedProduct) return 1;
    return 0;
  })[0];

  const exactSeen = new Set<string>();
  const exactNegatives: string[] = [];
  for (const response of responses) {
    for (const searchTerm of response.exactNegatives) {
      const key = searchTerm.trim().toLowerCase();
      if (!key || exactSeen.has(key)) continue;
      exactSeen.add(key);
      exactNegatives.push(searchTerm);
    }
  }

  const phraseMap = new Map<string, PureModelPhraseNegative>();
  for (const response of responses) {
    for (const phrase of response.phraseNegatives) {
      const key = `${phrase.bucket}:${phrase.phrase.toLowerCase()}`;
      const existing = phraseMap.get(key);
      if (!existing) {
        phraseMap.set(key, {
          ...phrase,
          sourceTerms: [...phrase.sourceTerms],
        });
        continue;
      }

      const sourceTermSeen = new Set(existing.sourceTerms.map((term) => term.toLowerCase()));
      for (const sourceTerm of phrase.sourceTerms) {
        const sourceKey = sourceTerm.toLowerCase();
        if (sourceTermSeen.has(sourceKey)) continue;
        sourceTermSeen.add(sourceKey);
        existing.sourceTerms.push(sourceTerm);
      }

      if (confidenceRank(phrase.confidence) > confidenceRank(existing.confidence)) {
        existing.confidence = phrase.confidence;
      }
      if (!existing.rationale && phrase.rationale) {
        existing.rationale = phrase.rationale;
      }
    }
  }

  const phraseNegatives = [...phraseMap.values()].sort(
    (left, right) =>
      left.bucket.localeCompare(right.bucket) || left.phrase.localeCompare(right.phrase),
  );

  return {
    matchedProduct: canonical?.matchedProduct ?? null,
    matchConfidence: canonical?.matchConfidence ?? "LOW",
    matchReason: canonical?.matchReason ?? "Merged pure-model campaign response.",
    termRecommendations: responses.flatMap((response) => response.termRecommendations),
    exactNegatives,
    phraseNegatives,
    modelPrefills: buildCampaignModelPrefills(exactNegatives, phraseNegatives),
  };
};

const buildIdentifierFamily = (identifier: string | null, catalog: PreparedListingCatalog) => {
  const normalizedIdentifier = normalizeProductMatcherText(identifier);
  const familyTokens = buildFamilyTokens(normalizedIdentifier, catalog.commonTokens);
  return {
    normalizedIdentifier,
    familyTokens,
    familyKey: familyTokens.join(" "),
  };
};

const tokenWeight = (token: string, tokenFrequency: Map<string, number>): number =>
  1 / Math.max(1, tokenFrequency.get(token) ?? 1);

const scorePreparedListingMatch = (
  identifierFamily: ReturnType<typeof buildIdentifierFamily>,
  listing: PreparedListingCatalog["listings"][number],
  tokenFrequency: Map<string, number>,
): number => {
  if (!identifierFamily.familyTokens.length || !listing.familyTokens.length) return 0;
  if (identifierFamily.familyKey && identifierFamily.familyKey === listing.familyKey) return 1;

  const identifierSet = new Set(identifierFamily.familyTokens);
  const listingSet = new Set(listing.familyTokens);
  const matchedTokens = identifierFamily.familyTokens.filter((token) => listingSet.has(token));
  if (matchedTokens.length === 0) return 0;

  const identifierWeight = identifierFamily.familyTokens.reduce(
    (sum, token) => sum + tokenWeight(token, tokenFrequency),
    0,
  );
  const listingWeight = listing.familyTokens.reduce((sum, token) => sum + tokenWeight(token, tokenFrequency), 0);
  const matchedWeight = matchedTokens.reduce((sum, token) => sum + tokenWeight(token, tokenFrequency), 0);

  const coverage = identifierWeight > 0 ? matchedWeight / identifierWeight : 0;
  const precision = listingWeight > 0 ? matchedWeight / listingWeight : 0;
  const orderedContainment =
    listing.familyKey.includes(identifierFamily.familyKey) ||
    identifierFamily.familyKey.includes(listing.familyKey);

  if (coverage === 1 && precision >= 0.72) return 0.96;
  if (orderedContainment && coverage >= 0.75) return 0.9 + Math.min(0.06, precision * 0.06);

  const jaccard =
    matchedWeight /
    (identifierWeight + listingWeight - matchedWeight || 1);

  return coverage * 0.72 + precision * 0.18 + jaccard * 0.1;
};

export const chooseBestListingMatch = (
  campaignName: string,
  listings: NgramListingRow[] | PreparedListingCatalog,
): CampaignProductMatch => {
  const identifier = parseCampaignProductIdentifier(campaignName);
  const theme = parseCampaignTheme(campaignName);
  const intentionallySkipped = isIntentionallySkippedCampaign(campaignName);
  const catalog = Array.isArray(listings) ? buildPreparedListingCatalog(listings) : listings;

  if (!identifier || intentionallySkipped) {
    return {
      status: intentionallySkipped ? "intentionally_skipped" : "ambiguous",
      identifier,
      matchedTitle: null,
      category: null,
      itemDescription: null,
      score: null,
      theme,
      matchSource: "none",
      skipReason: intentionallySkipped ? "brand_mix_defensive" : "missing_identifier",
      candidates: [],
    };
  }

  const identifierFamily = buildIdentifierFamily(identifier, catalog);
  if (!identifierFamily.familyTokens.length) {
    return {
      status: "ambiguous",
      identifier,
      matchedTitle: null,
      category: null,
      itemDescription: null,
      score: null,
      theme,
      matchSource: "none",
      skipReason: null,
      candidates: [],
    };
  }

  const scored = catalog.listings
    .map((listing) => {
      return {
        listing,
        score: scorePreparedListingMatch(identifierFamily, listing, catalog.tokenFrequency),
      };
    })
    .sort((left, right) => right.score - left.score);

  const best = scored[0];
  const second = scored[1];
  const candidates = scored.slice(0, 3).map(({ listing, score }) => ({
    title: listing.title,
    category: listing.category,
    itemDescription: listing.itemDescription,
    score: Number(score.toFixed(3)),
    familyKey: listing.familyKey,
  }));

  if (!best || best.score < 0.5) {
    return {
      status: "ambiguous",
      identifier,
      matchedTitle: null,
      category: null,
      itemDescription: null,
      score: best?.score ?? null,
      theme,
      matchSource: "none",
      skipReason: null,
      candidates,
    };
  }

  const bestGap = second ? best.score - second.score : best.score;
  const confidentDeterministicMatch =
    best.score >= 0.96 ||
    (best.score >= 0.84 && bestGap >= 0.12) ||
    (best.score >= 0.74 && bestGap >= 0.2);

  if (!confidentDeterministicMatch) {
    return {
      status: "ambiguous",
      identifier,
      matchedTitle: null,
      category: null,
      itemDescription: null,
      score: best.score,
      theme,
      matchSource: "none",
      skipReason: null,
      candidates,
    };
  }

  return {
    status: "matched",
    identifier,
    matchedTitle: best.listing.title,
    category: best.listing.category || null,
    itemDescription: best.listing.itemDescription || null,
    score: best.score,
    theme,
    matchSource: "deterministic",
    skipReason: null,
    candidates,
  };
};

export const aggregateSearchTerms = (rows: SearchTermFactRow[]): AggregatedSearchTerm[] => {
  const grouped = new Map<string, AggregatedSearchTerm>();

  for (const row of rows) {
    const campaignName = String(row.campaign_name || "").trim();
    const searchTerm = String(row.search_term || "").trim();
    if (!campaignName || !searchTerm) continue;

    const key = `${campaignName}__${searchTerm.toLowerCase()}`;
    const current = grouped.get(key);
    if (current) {
      current.impressions += toNumber(row.impressions);
      current.clicks += toNumber(row.clicks);
      current.spend += toNumber(row.spend);
      current.orders += toNumber(row.orders);
      current.sales += toNumber(row.sales);
      continue;
    }

    grouped.set(key, {
      campaignName,
      searchTerm,
      impressions: toNumber(row.impressions),
      clicks: toNumber(row.clicks),
      spend: toNumber(row.spend),
      orders: toNumber(row.orders),
      sales: toNumber(row.sales),
      keyword: row.keyword || null,
      keywordType: row.keyword_type || null,
      targeting: row.targeting || null,
      matchType: row.match_type || null,
    });
  }

  return [...grouped.values()].sort(
    (left, right) =>
      left.campaignName.localeCompare(right.campaignName) ||
      right.spend - left.spend ||
      left.searchTerm.localeCompare(right.searchTerm),
  );
};

export const buildCampaignAggregates = (
  rows: AggregatedSearchTerm[],
  options?: {
    spendThreshold?: number;
    respectLegacyExclusions?: boolean;
  },
): AggregatedCampaign[] => {
  const grouped = new Map<string, AggregatedCampaign>();
  const spendThreshold = options?.spendThreshold ?? 0;
  const respectLegacyExclusions = options?.respectLegacyExclusions ?? true;

  for (const row of rows) {
    if (!row.campaignName || !row.searchTerm) continue;
    if (respectLegacyExclusions && isLegacyExcludedCampaign(row.campaignName)) continue;
    if (isAsinQuery(row.searchTerm)) continue;
    if (row.spend < spendThreshold) continue;

    const current = grouped.get(row.campaignName);
    if (current) {
      current.totalSpend += row.spend;
      current.termCount += 1;
      current.terms.push(row);
      continue;
    }

    grouped.set(row.campaignName, {
      campaignName: row.campaignName,
      totalSpend: row.spend,
      termCount: 1,
      terms: [row],
    });
  }

  return [...grouped.values()]
    .map((campaign) => ({
      ...campaign,
      terms: [...campaign.terms].sort(
        (left, right) => right.spend - left.spend || left.searchTerm.localeCompare(right.searchTerm),
      ),
    }))
    .sort((left, right) => right.totalSpend - left.totalSpend || left.campaignName.localeCompare(right.campaignName));
};

export const selectCampaignsForAIPrefill = (
  campaigns: AggregatedCampaign[],
  runMode: AIPrefillRunMode,
  requestedCampaignNames: string[] = [],
): AggregatedCampaign[] =>
  requestedCampaignNames.length > 0
    ? requestedCampaignNames
        .map((campaignName) => campaigns.find((campaign) => campaign.campaignName === campaignName) ?? null)
        .filter((campaign): campaign is AggregatedCampaign => Boolean(campaign))
    : runMode === "preview"
      ? campaigns.slice(0, AI_PREFILL_PREVIEW_MAX_CAMPAIGNS)
      : campaigns;

export const selectTermsForAIPrefillCampaign = (
  campaign: AggregatedCampaign,
  runMode: AIPrefillRunMode,
  hasRequestedCampaigns = false,
): AggregatedSearchTerm[] =>
  runMode === "preview" && !hasRequestedCampaigns
    ? campaign.terms.slice(0, AI_PREFILL_PREVIEW_MAX_TERMS_PER_CAMPAIGN)
    : campaign.terms;

const weightedConfidenceScore = (confidence: AIPrefillEvaluation["confidence"]): number => {
  if (confidence === "HIGH") return 2;
  if (confidence === "MEDIUM") return 1;
  return 0;
};

const tokenizeSynthesizedGram = (gram: string): string[] =>
  cleanQueryForNgrams(gram)
    .split(" ")
    .filter(Boolean);

const countDistinctiveSynthesizedTokens = (gram: string): number =>
  tokenizeSynthesizedGram(gram).filter(
    (token) => !SYNTHESIS_BOUNDARY_TOKENS.has(token) && !SYNTHESIS_GENERIC_DESCRIPTOR_TOKENS.has(token),
  ).length;

const isAllowedSynthesizedGram = (gram: string, size: 1 | 2 | 3): boolean => {
  const tokens = tokenizeSynthesizedGram(gram);
  if (tokens.length !== size) return false;

  if (size === 1) {
    return !SYNTHESIS_GENERIC_MONOGRAMS.has(tokens[0] || "");
  }

  const first = tokens[0] || "";
  const last = tokens[tokens.length - 1] || "";
  if (SYNTHESIS_BOUNDARY_TOKENS.has(first) || SYNTHESIS_BOUNDARY_TOKENS.has(last)) {
    return false;
  }

  return countDistinctiveSynthesizedTokens(gram) > 0;
};

const pruneRedundantMonograms = (
  monoCandidates: SynthesizedGram[],
  longerCandidates: SynthesizedGram[],
): SynthesizedGram[] =>
  monoCandidates.filter((candidate) => {
    const token = tokenizeSynthesizedGram(candidate.gram)[0] || "";
    if (!token) return false;

    return !longerCandidates.some((longer) => {
      const longerTokens = tokenizeSynthesizedGram(longer.gram);
      return longer.negateCount >= 2 && longerTokens.includes(token);
    });
  });

const synthesizeForSize = (
  evaluations: AIPrefillEvaluation[],
  size: 1 | 2 | 3,
): SynthesizedGram[] => {
  const byGram = new Map<
    string,
    {
      supportTerms: Set<string>;
      negateCount: number;
      keepCount: number;
      reviewCount: number;
      negateSpend: number;
      weightedScore: number;
    }
  >();

  for (const evaluation of evaluations) {
    const grams = buildNgramsForQuery(evaluation.search_term, size);
    for (const gram of grams) {
      const current = byGram.get(gram) ?? {
        supportTerms: new Set<string>(),
        negateCount: 0,
        keepCount: 0,
        reviewCount: 0,
        negateSpend: 0,
        weightedScore: 0,
      };

      if (evaluation.recommendation === "NEGATE") {
        current.negateCount += 1;
        current.negateSpend += evaluation.spend;
        current.weightedScore += weightedConfidenceScore(evaluation.confidence);
        current.supportTerms.add(evaluation.search_term);
      } else if (evaluation.recommendation === "KEEP") {
        current.keepCount += 1;
      } else {
        current.reviewCount += 1;
      }

      byGram.set(gram, current);
    }
  }

  return [...byGram.entries()]
    .map(([gram, stats]) => ({
      gram,
      supportTerms: [...stats.supportTerms].sort(),
      negateCount: stats.negateCount,
      keepCount: stats.keepCount,
      reviewCount: stats.reviewCount,
      negateSpend: Number(stats.negateSpend.toFixed(2)),
      weightedScore: stats.weightedScore,
    }))
    .filter((candidate) => {
      if (!candidate.gram) return false;
      if (candidate.keepCount > 0) return false;
      if (candidate.reviewCount > 0) return false;
      if (candidate.weightedScore < 2) return false;
      if (!isAllowedSynthesizedGram(candidate.gram, size)) return false;

      if (size === 1) {
        return candidate.supportTerms.length >= 2;
      }

      return candidate.supportTerms.length >= 2;
    })
    .sort(
      (left, right) =>
        right.weightedScore - left.weightedScore ||
        right.negateSpend - left.negateSpend ||
        left.gram.localeCompare(right.gram),
    )
    .slice(0, 25);
};

export const synthesizeCampaignScratchpad = (
  evaluations: AIPrefillEvaluation[],
  _spendThreshold: number,
): CampaignPrefillScratchpad => {
  const tri = synthesizeForSize(evaluations, 3);
  const bi = synthesizeForSize(evaluations, 2);
  const mono = pruneRedundantMonograms(
    synthesizeForSize(evaluations, 1),
    [...bi, ...tri],
  );

  return { mono, bi, tri };
};
