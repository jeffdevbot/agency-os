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
  status: "matched" | "ambiguous";
  identifier: string | null;
  matchedTitle: string | null;
  category: string | null;
  itemDescription: string | null;
  score: number | null;
  theme: string | null;
  expectedAmbiguous: boolean;
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

export type AggregatedCampaign = {
  campaignName: string;
  totalSpend: number;
  termCount: number;
  terms: AggregatedSearchTerm[];
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
  "oz",
  "fl",
  "refillable",
  "spray",
  "kit",
  "cleaner",
  "screen",
]);

const QUERY_TOKEN_RE = /[^\w\s\-"'®©™°&+#]+/gu;

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

export const isExpectedAmbiguousCampaign = (campaignName: string): boolean => {
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

const normalizeText = (value: string | null | undefined): string =>
  String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();

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
  normalizeText(value)
    .split(" ")
    .filter((token) => token && !STOP_WORDS.has(token));

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

const overlapScore = (left: string | null | undefined, right: string | null | undefined): number => {
  const leftNormalized = normalizeText(left);
  const rightNormalized = normalizeText(right);
  if (leftNormalized && rightNormalized) {
    if (rightNormalized.includes(leftNormalized) || leftNormalized.includes(rightNormalized)) {
      return 1;
    }
  }

  const leftTokens = new Set(tokenize(left));
  const rightTokens = new Set(tokenize(right));
  if (leftTokens.size === 0 || rightTokens.size === 0) return 0;

  let overlap = 0;
  for (const token of leftTokens) {
    if (rightTokens.has(token)) overlap += 1;
  }

  return overlap / Math.max(leftTokens.size, rightTokens.size);
};

export const chooseBestListingMatch = (
  campaignName: string,
  listings: NgramListingRow[],
): CampaignProductMatch => {
  const identifier = parseCampaignProductIdentifier(campaignName);
  const theme = parseCampaignTheme(campaignName);
  const expectedAmbiguous = isExpectedAmbiguousCampaign(campaignName);

  if (!identifier || expectedAmbiguous) {
    return {
      status: "ambiguous",
      identifier,
      matchedTitle: null,
      category: null,
      itemDescription: null,
      score: null,
      theme,
      expectedAmbiguous,
    };
  }

  const scored = listings
    .map((listing) => {
      const title = listing.child_product_name || listing.parent_title || "";
      return {
        listing,
        score: overlapScore(identifier, title),
      };
    })
    .sort((left, right) => right.score - left.score);

  const best = scored[0];
  const second = scored[1];

  if (!best || best.score < 0.45) {
    return {
      status: "ambiguous",
      identifier,
      matchedTitle: null,
      category: null,
      itemDescription: null,
      score: best?.score ?? null,
      theme,
      expectedAmbiguous,
    };
  }

  if (second && best.score - second.score < 0.12) {
    return {
      status: "ambiguous",
      identifier,
      matchedTitle: null,
      category: null,
      itemDescription: null,
      score: best.score,
      theme,
      expectedAmbiguous,
    };
  }

  return {
    status: "matched",
    identifier,
    matchedTitle: best.listing.child_product_name || best.listing.parent_title || null,
    category: best.listing.category || null,
    itemDescription: best.listing.item_description || null,
    score: best.score,
    theme,
    expectedAmbiguous,
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

const weightedConfidenceScore = (confidence: AIPrefillEvaluation["confidence"]): number => {
  if (confidence === "HIGH") return 2;
  if (confidence === "MEDIUM") return 1;
  return 0;
};

const synthesizeForSize = (
  evaluations: AIPrefillEvaluation[],
  size: 1 | 2 | 3,
  spendThreshold: number,
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

  const minSpendForSingleTerm = Math.max(spendThreshold * 2.5, size === 1 ? 12 : 8);

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

      if (size === 1) {
        return candidate.supportTerms.length >= 2;
      }

      if (candidate.supportTerms.length >= 2) return true;
      return candidate.negateSpend >= minSpendForSingleTerm;
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
  spendThreshold: number,
): CampaignPrefillScratchpad => ({
  mono: synthesizeForSize(evaluations, 1, spendThreshold),
  bi: synthesizeForSize(evaluations, 2, spendThreshold),
  tri: synthesizeForSize(evaluations, 3, spendThreshold),
});
