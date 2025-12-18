/**
 * Title Blueprint Utility
 *
 * Provides deterministic title assembly for Scribe Stage C.
 * Titles are built from ordered blocks (product name, variant attributes, LLM phrase)
 * joined with a consistent separator, ensuring uniform structure across all SKUs.
 */

// -----------------------------------------------------------------------------
// Constants
// -----------------------------------------------------------------------------

/** Amazon's maximum title length */
export const AMAZON_TITLE_MAX_LEN = 200;

/** Supported separator styles for title blocks */
export const TITLE_SEPARATORS = [" - ", " — ", ", ", " | "] as const;

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

/** Supported separator type derived from TITLE_SEPARATORS */
export type TitleSeparator = (typeof TITLE_SEPARATORS)[number];

/** A block that references a fixed SKU field (currently only product_name) */
export interface SkuFieldBlock {
  type: "sku_field";
  key: "product_name";
}

/** A block that references a variant attribute by its ID */
export interface VariantAttributeBlock {
  type: "variant_attribute";
  attributeId: string;
}

/** A block for the LLM-generated feature phrase (exactly one allowed per blueprint) */
export interface LlmPhraseBlock {
  type: "llm_phrase";
  key: "feature_phrase";
}

/** Union of all block types */
export type TitleBlock = SkuFieldBlock | VariantAttributeBlock | LlmPhraseBlock;

/** Complete title blueprint configuration */
export interface TitleBlueprint {
  separator: TitleSeparator;
  blocks: TitleBlock[];
}

/** SKU data needed for title assembly */
export interface SkuTitleData {
  productName: string | null;
  variantValuesByAttributeId: Record<string, string>;
}

/** Result of computing the fixed title and remaining budget */
export interface FixedTitleResult {
  /** The assembled title from all non-LLM blocks */
  fixedTitle: string;
  /** Characters remaining for the LLM phrase (can be negative if over budget) */
  remainingForPhrase: number;
  /** Whether a separator should precede the phrase (true if fixedTitle is non-empty) */
  needsSeparatorBeforePhrase: boolean;
}

/** Result of parsing/validating a title blueprint */
export interface ParseBlueprintResult {
  /** The validated blueprint (null if invalid) */
  blueprint: TitleBlueprint | null;
  /** Array of validation errors (empty if valid) */
  errors: string[];
}

// -----------------------------------------------------------------------------
// Type Guards
// -----------------------------------------------------------------------------

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isValidSeparator(value: unknown): value is TitleSeparator {
  return typeof value === "string" && TITLE_SEPARATORS.includes(value as TitleSeparator);
}

// -----------------------------------------------------------------------------
// Parsing / Validation
// -----------------------------------------------------------------------------

/**
 * Parses and validates an unknown value as a TitleBlueprint.
 * Use this when reading from JSON (API responses, database, user input).
 *
 * @param value - Unknown value to parse
 * @returns Object with typed blueprint (if valid) and array of errors
 */
export function parseTitleBlueprint(value: unknown): ParseBlueprintResult {
  const errors: string[] = [];

  // Check top-level shape
  if (!isObject(value)) {
    return { blueprint: null, errors: ["Blueprint must be an object"] };
  }

  // Validate separator
  if (!("separator" in value)) {
    errors.push("Blueprint must have a separator");
  } else if (!isValidSeparator(value.separator)) {
    errors.push(
      `Invalid separator: "${value.separator}" (must be one of: ${TITLE_SEPARATORS.map((s) => `"${s}"`).join(", ")})`
    );
  }

  // Validate blocks array exists
  if (!("blocks" in value)) {
    errors.push("Blueprint must have a blocks array");
    return { blueprint: null, errors };
  }

  if (!Array.isArray(value.blocks)) {
    errors.push("blocks must be an array");
    return { blueprint: null, errors };
  }

  if (value.blocks.length === 0) {
    errors.push("Blueprint must have at least one block");
  }

  // Validate each block
  const validatedBlocks: TitleBlock[] = [];
  let llmPhraseCount = 0;
  const seenBlockKeys = new Set<string>();

  for (let i = 0; i < value.blocks.length; i++) {
    const block = value.blocks[i];
    const blockNum = i + 1;

    if (!isObject(block)) {
      errors.push(`Block ${blockNum}: must be an object`);
      continue;
    }

    if (!("type" in block) || typeof block.type !== "string") {
      errors.push(`Block ${blockNum}: must have a type string`);
      continue;
    }

    switch (block.type) {
      case "sku_field":
        if (!("key" in block) || block.key !== "product_name") {
          errors.push(`Block ${blockNum}: sku_field must have key "product_name"`);
        } else {
          const dedupeKey = "sku_field:product_name";
          if (seenBlockKeys.has(dedupeKey)) {
            errors.push(`Block ${blockNum}: duplicate sku_field "product_name"`);
          } else {
            seenBlockKeys.add(dedupeKey);
            validatedBlocks.push({ type: "sku_field", key: "product_name" });
          }
        }
        break;

      case "variant_attribute":
        if (!("attributeId" in block) || typeof block.attributeId !== "string" || !block.attributeId) {
          errors.push(`Block ${blockNum}: variant_attribute must have a non-empty attributeId string`);
        } else {
          const dedupeKey = `variant_attribute:${block.attributeId}`;
          if (seenBlockKeys.has(dedupeKey)) {
            errors.push(`Block ${blockNum}: duplicate variant_attribute "${block.attributeId}"`);
          } else {
            seenBlockKeys.add(dedupeKey);
            validatedBlocks.push({ type: "variant_attribute", attributeId: block.attributeId });
          }
        }
        break;

      case "llm_phrase":
        llmPhraseCount++;
        if (!("key" in block) || block.key !== "feature_phrase") {
          errors.push(`Block ${blockNum}: llm_phrase must have key "feature_phrase"`);
        } else {
          const dedupeKey = "llm_phrase:feature_phrase";
          if (seenBlockKeys.has(dedupeKey)) {
            errors.push(`Block ${blockNum}: duplicate llm_phrase "feature_phrase"`);
          } else {
            seenBlockKeys.add(dedupeKey);
            validatedBlocks.push({ type: "llm_phrase", key: "feature_phrase" });
          }
        }
        break;

      default:
        errors.push(`Block ${blockNum}: unknown type "${block.type}"`);
    }
  }

  // Check max 1 LLM phrase block
  if (llmPhraseCount > 1) {
    errors.push(`Only one llm_phrase block is allowed (found ${llmPhraseCount})`);
  }

  // Return result
  if (errors.length > 0) {
    return { blueprint: null, errors };
  }

  return {
    blueprint: {
      separator: value.separator as TitleSeparator,
      blocks: validatedBlocks,
    },
    errors: [],
  };
}

/**
 * Validates an unknown value as a TitleBlueprint.
 * Convenience wrapper around parseTitleBlueprint that returns just errors.
 *
 * @param value - Unknown value to validate
 * @returns Array of error messages (empty if valid)
 */
export function validateBlueprint(value: unknown): string[] {
  return parseTitleBlueprint(value).errors;
}

// -----------------------------------------------------------------------------
// Block Resolution
// -----------------------------------------------------------------------------

/**
 * Resolves a single block to its string value for a given SKU.
 * Returns empty string if the value is missing/null.
 */
function resolveBlockValue(block: TitleBlock, skuData: SkuTitleData): string {
  switch (block.type) {
    case "sku_field":
      if (block.key === "product_name") {
        return skuData.productName?.trim() ?? "";
      }
      return "";

    case "variant_attribute":
      return skuData.variantValuesByAttributeId[block.attributeId]?.trim() ?? "";

    case "llm_phrase":
      // LLM phrase is not resolved here - it's handled separately
      return "";

    default:
      return "";
  }
}

// -----------------------------------------------------------------------------
// Title Assembly Functions
// -----------------------------------------------------------------------------

/**
 * Computes the fixed portion of the title (all blocks except llm_phrase)
 * and calculates how much character budget remains for the LLM phrase.
 *
 * @param skuData - The SKU's product name and variant attribute values
 * @param blueprint - The title blueprint configuration
 * @param maxLen - Maximum title length (default: 200 for Amazon)
 * @returns Fixed title, remaining budget, and whether separator is needed before phrase
 */
export function computeFixedTitleAndRemaining(
  skuData: SkuTitleData,
  blueprint: TitleBlueprint,
  maxLen: number = AMAZON_TITLE_MAX_LEN
): FixedTitleResult {
  // Collect values from all non-LLM blocks
  const fixedValues: string[] = [];
  let hasLlmPhraseBlock = false;

  for (const block of blueprint.blocks) {
    if (block.type === "llm_phrase") {
      hasLlmPhraseBlock = true;
      continue; // Skip LLM phrase blocks for fixed title
    }

    const value = resolveBlockValue(block, skuData);
    if (value) {
      fixedValues.push(value);
    }
  }

  // Join non-empty values with separator
  const fixedTitle = fixedValues.join(blueprint.separator);

  // Calculate remaining budget for LLM phrase
  let remainingForPhrase: number;
  let needsSeparatorBeforePhrase: boolean;

  if (!hasLlmPhraseBlock) {
    // No LLM phrase block in blueprint - no budget needed
    remainingForPhrase = 0;
    needsSeparatorBeforePhrase = false;
  } else if (fixedTitle.length === 0) {
    // Empty fixed title - full budget available, no separator needed
    remainingForPhrase = maxLen;
    needsSeparatorBeforePhrase = false;
  } else {
    // Fixed title exists - account for separator before phrase
    remainingForPhrase = maxLen - fixedTitle.length - blueprint.separator.length;
    needsSeparatorBeforePhrase = true;
  }

  return {
    fixedTitle,
    remainingForPhrase,
    needsSeparatorBeforePhrase,
  };
}

/**
 * Assembles the final title from the fixed portion and LLM-generated feature phrase.
 * Safely handles empty values by omitting them (no dangling separators).
 *
 * @param fixedTitle - The pre-computed fixed portion of the title
 * @param separator - The separator to use between parts
 * @param featurePhrase - The LLM-generated feature phrase (can be empty/null)
 * @returns The complete assembled title
 */
export function assembleTitle(
  fixedTitle: string,
  separator: TitleSeparator,
  featurePhrase: string | null | undefined
): string {
  const trimmedFixed = fixedTitle.trim();
  const trimmedPhrase = featurePhrase?.trim() ?? "";

  // Handle empty cases
  if (!trimmedFixed && !trimmedPhrase) {
    return "";
  }
  if (!trimmedFixed) {
    return trimmedPhrase;
  }
  if (!trimmedPhrase) {
    return trimmedFixed;
  }

  // Both parts present - join with separator
  return `${trimmedFixed}${separator}${trimmedPhrase}`;
}

/**
 * Enforces a maximum length by trimming at a word boundary.
 * Used as a last resort when the LLM phrase exceeds the budget.
 *
 * @param text - The text to potentially trim
 * @param maxLen - Maximum allowed length
 * @returns The text trimmed at a word boundary if necessary
 */
export function enforceMaxLenAtWordBoundary(text: string, maxLen: number): string {
  if (text.length <= maxLen) {
    return text;
  }

  // Find the last space before or at maxLen
  const truncated = text.slice(0, maxLen);
  const lastSpaceIndex = truncated.lastIndexOf(" ");

  if (lastSpaceIndex === -1) {
    // No space found - just truncate (edge case: single very long word)
    return truncated;
  }

  // Trim at word boundary and remove any trailing punctuation/whitespace
  return truncated.slice(0, lastSpaceIndex).replace(/[\s,\-—|]+$/, "");
}
