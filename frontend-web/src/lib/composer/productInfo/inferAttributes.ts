import type { ComposerSkuVariant } from "../../../../../lib/composer/types";

export interface AttributeSummary {
  key: string;
  filledCount: number;
  totalCount: number;
}

export const inferAttributes = (_variants: ComposerSkuVariant[]): AttributeSummary[] => {
  // Placeholder: will analyze SKU attributes to produce coverage stats.
  return [];
};
