import type { ComposerProject, ComposerSkuVariant } from "@agency/lib/composer/types";

export interface ProductInfoValidationErrors {
  projectName?: string;
  clientName?: string;
  marketplaces?: string;
  variants?: string;
  rows?: Array<{ index: number; sku?: string; asin?: string }>;
}

export interface ProductInfoValidationResult {
  isValid: boolean;
  errors: ProductInfoValidationErrors;
}

export const validateProductInfoForm = (
  _project: ComposerProject | null,
  _variants: ComposerSkuVariant[],
): ProductInfoValidationResult => {
  // Placeholder: future implementation will evaluate required fields and SKU completeness.
  return {
    isValid: true,
    errors: {},
  };
};
