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
  project: ComposerProject | null,
  variants: ComposerSkuVariant[],
): ProductInfoValidationResult => {
  const errors: ProductInfoValidationErrors = {};

  // Check project exists
  if (!project) {
    return {
      isValid: false,
      errors: {
        projectName: "Project data not loaded",
      },
    };
  }

  // Check project name
  if (!project.projectName || project.projectName.trim() === "") {
    errors.projectName = "Project name is required";
  }

  // Check client name
  if (!project.clientName || project.clientName.trim() === "") {
    errors.clientName = "Client name is required";
  }

  // Check marketplaces
  if (!project.marketplaces || project.marketplaces.length === 0) {
    errors.marketplaces = "At least one marketplace is required";
  }

  // Check variants - need at least one with a non-empty SKU
  const validVariants = variants.filter(
    (v) => v.sku && v.sku.trim() !== ""
  );

  if (validVariants.length === 0) {
    errors.variants = "At least one SKU is required";
  }

  // Check for row-level errors (SKUs with empty sku field)
  const rowErrors: Array<{ index: number; sku?: string }> = [];
  variants.forEach((variant, index) => {
    if (!variant.sku || variant.sku.trim() === "") {
      rowErrors.push({ index, sku: "SKU is required" });
    }
  });

  if (rowErrors.length > 0) {
    errors.rows = rowErrors;
  }

  const isValid = Object.keys(errors).length === 0;

  return {
    isValid,
    errors,
  };
};
