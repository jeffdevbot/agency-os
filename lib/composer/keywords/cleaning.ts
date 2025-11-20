import type {
  ComposerProject,
  ComposerSkuVariant,
  KeywordCleanSettings,
  RemovedKeywordEntry,
} from "../types";
import { COLOR_LEXICON, SIZE_PATTERNS, STOP_WORDS } from "./blacklists";

type CleaningContext = {
  project: Pick<ComposerProject, "clientName" | "whatNotToSay">;
  variants?: Array<Pick<ComposerSkuVariant, "attributes">>;
};

export interface CleaningResult {
  cleaned: string[];
  removed: RemovedKeywordEntry[];
  config: KeywordCleanSettings;
}

const normalizeConfig = (config: KeywordCleanSettings): KeywordCleanSettings => ({
  removeColors: config.removeColors ?? false,
  removeSizes: config.removeSizes ?? false,
  removeBrandTerms: config.removeBrandTerms ?? true,
  removeCompetitorTerms: config.removeCompetitorTerms ?? true,
});

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const matchesToken = (term: string, token: string): boolean => {
  if (!token) return false;
  const pattern = new RegExp(`\\b${escapeRegExp(token.toLowerCase())}\\b`, "i");
  return pattern.test(term);
};

const matchesAnyToken = (term: string, tokens: string[]): boolean =>
  tokens.some((token) => matchesToken(term, token));

const matchesAnyPattern = (term: string, patterns: RegExp[]) =>
  patterns.some((pattern) => pattern.test(term));

const splitAttributeValue = (value: string): string[] =>
  value
    .split(/[,/|]+/)
    .map((part) => part.trim())
    .filter(Boolean);

const collectAttributeValues = (
  variants: Array<Pick<ComposerSkuVariant, "attributes">>,
  predicate: (attributeKey: string) => boolean,
): string[] => {
  const values = new Set<string>();

  for (const variant of variants) {
    const attributes = variant.attributes ?? {};
    for (const [key, value] of Object.entries(attributes)) {
      if (!predicate(key.toLowerCase())) continue;
      if (!value) continue;

      const parts = splitAttributeValue(value);
      for (const part of parts) {
        const normalized = part.toLowerCase();
        if (normalized) values.add(normalized);
      }
    }
  }

  return Array.from(values);
};

const deriveColorTerms = (variants: Array<Pick<ComposerSkuVariant, "attributes">>): string[] =>
  collectAttributeValues(
    variants,
    (key) => key.includes("color") || key.includes("colour"),
  );

const deriveSizeTerms = (variants: Array<Pick<ComposerSkuVariant, "attributes">>): string[] =>
  collectAttributeValues(
    variants,
    (key) => key.includes("size") || key.includes("dimension") || key.includes("pack"),
  );

/**
  * Clean keywords using deterministic filters.
  * - Case-insensitive dedupe (keeps first occurrence)
  * - Brand/competitor removal using project client/what_not_to_say
  * - Small stopword list
  * - Optional color/size removal (attribute-driven with fallback lexicons)
  */
export const cleanKeywords = (
  raw: string[],
  settings: KeywordCleanSettings,
  context: CleaningContext,
): CleaningResult => {
  const config = normalizeConfig(settings);
  const cleaned: string[] = [];
  const removed: RemovedKeywordEntry[] = [];
  const seen = new Set<string>();

  const brandTerm = context.project.clientName?.trim().toLowerCase() || null;
  const competitorTerms =
    context.project.whatNotToSay?.map((term) => term?.trim().toLowerCase()).filter(Boolean) ?? [];

  const variants = context.variants ?? [];
  const colorTerms = config.removeColors ? deriveColorTerms(variants) : [];
  const sizeTerms = config.removeSizes ? deriveSizeTerms(variants) : [];

  for (const rawTerm of raw) {
    const trimmed = rawTerm.trim();
    if (!trimmed) continue;

    const normalized = trimmed.toLowerCase();

    if (seen.has(normalized)) {
      removed.push({ term: trimmed, reason: "duplicate" });
      continue;
    }
    seen.add(normalized);

    const removalReason =
      (config.removeBrandTerms && brandTerm && matchesToken(normalized, brandTerm) && "brand") ||
      (config.removeCompetitorTerms &&
        competitorTerms.length > 0 &&
        matchesAnyToken(normalized, competitorTerms) &&
        "competitor") ||
      (matchesAnyToken(normalized, STOP_WORDS) && "stopword") ||
      (config.removeColors &&
        (matchesAnyToken(normalized, colorTerms) ||
          matchesAnyToken(normalized, COLOR_LEXICON)) &&
        "color") ||
      (config.removeSizes &&
        (matchesAnyToken(normalized, sizeTerms) ||
          matchesAnyPattern(normalized, SIZE_PATTERNS)) &&
        "size") ||
      null;

    if (removalReason) {
      removed.push({ term: trimmed, reason: removalReason });
      continue;
    }

    cleaned.push(trimmed);
  }

  return { cleaned, removed, config };
};
