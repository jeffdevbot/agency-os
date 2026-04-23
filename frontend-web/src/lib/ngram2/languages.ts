export const NGRAM_LANGUAGE_OPTIONS = [
  { code: "en", label: "English" },
  { code: "fr", label: "French" },
  { code: "es", label: "Spanish" },
  { code: "de", label: "German" },
  { code: "it", label: "Italian" },
  { code: "nl", label: "Dutch" },
  { code: "pt", label: "Portuguese" },
  { code: "sv", label: "Swedish" },
  { code: "pl", label: "Polish" },
  { code: "ar", label: "Arabic" },
  { code: "ja", label: "Japanese" },
  { code: "ko", label: "Korean" },
  { code: "zh-Hans", label: "Chinese (Simplified)" },
  { code: "zh-Hant", label: "Chinese (Traditional)" },
] as const;

export type NgramLanguageCode = (typeof NGRAM_LANGUAGE_OPTIONS)[number]["code"];

const NGRAM_LANGUAGE_CODE_SET = new Set<string>(NGRAM_LANGUAGE_OPTIONS.map((option) => option.code));

const MARKETPLACE_LANGUAGE_DEFAULTS: Record<string, NgramLanguageCode[]> = {
  US: ["en", "es"],
  CA: ["en", "fr"],
  MX: ["es", "en"],
  UK: ["en"],
  DE: ["de", "en"],
  FR: ["fr", "en"],
  IT: ["it", "en"],
  ES: ["es", "en"],
  NL: ["nl", "en"],
  SE: ["sv", "en"],
};

export const normalizeAllowedLanguages = (values: unknown): NgramLanguageCode[] => {
  if (!Array.isArray(values)) return [];
  const deduped = new Set<NgramLanguageCode>();
  for (const value of values) {
    const code = String(value || "").trim();
    if (!NGRAM_LANGUAGE_CODE_SET.has(code)) continue;
    deduped.add(code as NgramLanguageCode);
  }
  return [...deduped];
};

export const getDefaultAllowedLanguagesForMarketplace = (
  marketplaceCode: string | null | undefined,
): NgramLanguageCode[] => {
  const normalized = String(marketplaceCode || "").trim().toUpperCase();
  return [...(MARKETPLACE_LANGUAGE_DEFAULTS[normalized] ?? ["en"])];
};

export const getLanguageLabel = (code: string): string =>
  NGRAM_LANGUAGE_OPTIONS.find((option) => option.code === code)?.label ?? code;

export const getAllowedLanguageLabels = (codes: string[]): string[] =>
  normalizeAllowedLanguages(codes).map((code) => getLanguageLabel(code));
