import type { ComposerSkuVariant } from "@agency/lib/composer/types";

export interface AttributeSummary {
  key: string;
  filledCount: number;
  totalCount: number;
}

export const inferAttributes = (variants: ComposerSkuVariant[]): AttributeSummary[] => {
  if (variants.length === 0) {
    return [];
  }

  // Collect all unique attribute keys across all variants
  const attributeKeys = new Set<string>();
  for (const variant of variants) {
    if (variant.attributes) {
      for (const key of Object.keys(variant.attributes)) {
        attributeKeys.add(key);
      }
    }
  }

  // For each attribute key, count how many variants have a non-empty value
  const summaries: AttributeSummary[] = [];
  for (const key of attributeKeys) {
    let filledCount = 0;
    for (const variant of variants) {
      const value = variant.attributes?.[key];
      if (value !== null && value !== undefined && value !== "") {
        filledCount++;
      }
    }
    summaries.push({
      key,
      filledCount,
      totalCount: variants.length,
    });
  }

  // Sort alphabetically by key for consistent display
  summaries.sort((a, b) => a.key.localeCompare(b.key));

  return summaries;
};
