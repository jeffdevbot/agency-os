import { describe, it, expect } from "vitest";
import {
  computeFixedTitleAndRemaining,
  assembleTitle,
  enforceMaxLenAtWordBoundary,
  validateBlueprint,
  parseTitleBlueprint,
  AMAZON_TITLE_MAX_LEN,
  TITLE_SEPARATORS,
  type TitleBlueprint,
  type TitleSeparator,
  type SkuTitleData,
} from "./titleBlueprint";

describe("titleBlueprint", () => {
  // ---------------------------------------------------------------------------
  // TITLE_SEPARATORS constant
  // ---------------------------------------------------------------------------
  describe("TITLE_SEPARATORS", () => {
    it("contains all expected separators", () => {
      expect(TITLE_SEPARATORS).toEqual([" - ", " — ", ", ", " | "]);
    });

    it("is readonly", () => {
      // TypeScript enforces this at compile time via `as const`
      // Runtime check that it's an array with expected length
      expect(TITLE_SEPARATORS.length).toBe(4);
    });
  });

  // ---------------------------------------------------------------------------
  // parseTitleBlueprint
  // ---------------------------------------------------------------------------
  describe("parseTitleBlueprint", () => {
    it("returns valid blueprint for correct input", () => {
      const input = {
        separator: " - ",
        blocks: [
          { type: "sku_field", key: "product_name" },
          { type: "variant_attribute", attributeId: "uuid-123" },
          { type: "llm_phrase", key: "feature_phrase" },
        ],
      };

      const result = parseTitleBlueprint(input);

      expect(result.errors).toEqual([]);
      expect(result.blueprint).not.toBeNull();
      expect(result.blueprint?.separator).toBe(" - ");
      expect(result.blueprint?.blocks).toHaveLength(3);
    });

    it("returns typed blocks in the blueprint", () => {
      const input = {
        separator: ", ",
        blocks: [
          { type: "sku_field", key: "product_name" },
          { type: "variant_attribute", attributeId: "size-id" },
        ],
      };

      const result = parseTitleBlueprint(input);

      expect(result.blueprint?.blocks[0]).toEqual({ type: "sku_field", key: "product_name" });
      expect(result.blueprint?.blocks[1]).toEqual({ type: "variant_attribute", attributeId: "size-id" });
    });

    it("rejects non-object input", () => {
      expect(parseTitleBlueprint(null).errors).toContain("Blueprint must be an object");
      expect(parseTitleBlueprint(undefined).errors).toContain("Blueprint must be an object");
      expect(parseTitleBlueprint("string").errors).toContain("Blueprint must be an object");
      expect(parseTitleBlueprint(123).errors).toContain("Blueprint must be an object");
      expect(parseTitleBlueprint([]).errors).toContain("Blueprint must be an object");
    });

    it("rejects missing separator", () => {
      const input = {
        blocks: [{ type: "sku_field", key: "product_name" }],
      };

      const result = parseTitleBlueprint(input);

      expect(result.blueprint).toBeNull();
      expect(result.errors).toContain("Blueprint must have a separator");
    });

    it("rejects invalid separator", () => {
      const input = {
        separator: " -- ",
        blocks: [{ type: "sku_field", key: "product_name" }],
      };

      const result = parseTitleBlueprint(input);

      expect(result.blueprint).toBeNull();
      expect(result.errors.some((e) => e.includes("Invalid separator"))).toBe(true);
    });

    it("rejects missing blocks", () => {
      const input = {
        separator: " - ",
      };

      const result = parseTitleBlueprint(input);

      expect(result.blueprint).toBeNull();
      expect(result.errors).toContain("Blueprint must have a blocks array");
    });

    it("rejects non-array blocks", () => {
      const input = {
        separator: " - ",
        blocks: "not an array",
      };

      const result = parseTitleBlueprint(input);

      expect(result.blueprint).toBeNull();
      expect(result.errors).toContain("blocks must be an array");
    });

    it("rejects empty blocks array", () => {
      const input = {
        separator: " - ",
        blocks: [],
      };

      const result = parseTitleBlueprint(input);

      expect(result.blueprint).toBeNull();
      expect(result.errors).toContain("Blueprint must have at least one block");
    });

    it("rejects block that is not an object", () => {
      const input = {
        separator: " - ",
        blocks: ["not an object"],
      };

      const result = parseTitleBlueprint(input);

      expect(result.blueprint).toBeNull();
      expect(result.errors).toContain("Block 1: must be an object");
    });

    it("rejects block without type", () => {
      const input = {
        separator: " - ",
        blocks: [{ key: "product_name" }],
      };

      const result = parseTitleBlueprint(input);

      expect(result.blueprint).toBeNull();
      expect(result.errors).toContain("Block 1: must have a type string");
    });

    it("rejects unknown block type", () => {
      const input = {
        separator: " - ",
        blocks: [{ type: "unknown_type" }],
      };

      const result = parseTitleBlueprint(input);

      expect(result.blueprint).toBeNull();
      expect(result.errors.some((e) => e.includes('unknown type "unknown_type"'))).toBe(true);
    });

    it("rejects sku_field with wrong key", () => {
      const input = {
        separator: " - ",
        blocks: [{ type: "sku_field", key: "wrong_key" }],
      };

      const result = parseTitleBlueprint(input);

      expect(result.blueprint).toBeNull();
      expect(result.errors.some((e) => e.includes('sku_field must have key "product_name"'))).toBe(true);
    });

    it("rejects variant_attribute without attributeId", () => {
      const input = {
        separator: " - ",
        blocks: [{ type: "variant_attribute" }],
      };

      const result = parseTitleBlueprint(input);

      expect(result.blueprint).toBeNull();
      expect(result.errors.some((e) => e.includes("non-empty attributeId"))).toBe(true);
    });

    it("rejects variant_attribute with empty attributeId", () => {
      const input = {
        separator: " - ",
        blocks: [{ type: "variant_attribute", attributeId: "" }],
      };

      const result = parseTitleBlueprint(input);

      expect(result.blueprint).toBeNull();
      expect(result.errors.some((e) => e.includes("non-empty attributeId"))).toBe(true);
    });

    it("rejects llm_phrase with wrong key", () => {
      const input = {
        separator: " - ",
        blocks: [{ type: "llm_phrase", key: "wrong_key" }],
      };

      const result = parseTitleBlueprint(input);

      expect(result.blueprint).toBeNull();
      expect(result.errors.some((e) => e.includes('llm_phrase must have key "feature_phrase"'))).toBe(true);
    });

    it("rejects multiple llm_phrase blocks", () => {
      const input = {
        separator: " - ",
        blocks: [
          { type: "llm_phrase", key: "feature_phrase" },
          { type: "sku_field", key: "product_name" },
          { type: "llm_phrase", key: "feature_phrase" },
        ],
      };

      const result = parseTitleBlueprint(input);

      expect(result.blueprint).toBeNull();
      expect(result.errors).toContain("Only one llm_phrase block is allowed (found 2)");
    });

    it("rejects duplicate blocks (same attribute repeated)", () => {
      const input = {
        separator: " - ",
        blocks: [
          { type: "variant_attribute", attributeId: "size-id" },
          { type: "variant_attribute", attributeId: "size-id" },
        ],
      };

      const result = parseTitleBlueprint(input);

      expect(result.blueprint).toBeNull();
      expect(result.errors.some((e) => e.includes('duplicate variant_attribute "size-id"'))).toBe(true);
    });

    it("collects multiple errors", () => {
      const input = {
        separator: "invalid",
        blocks: [
          { type: "unknown" },
          { type: "sku_field", key: "wrong" },
        ],
      };

      const result = parseTitleBlueprint(input);

      expect(result.blueprint).toBeNull();
      expect(result.errors.length).toBeGreaterThanOrEqual(3);
    });
  });

  // ---------------------------------------------------------------------------
  // validateBlueprint (wrapper)
  // ---------------------------------------------------------------------------
  describe("validateBlueprint", () => {
    it("returns empty array for valid blueprint", () => {
      const input = {
        separator: " - ",
        blocks: [
          { type: "sku_field", key: "product_name" },
          { type: "variant_attribute", attributeId: "uuid-123" },
          { type: "llm_phrase", key: "feature_phrase" },
        ],
      };

      expect(validateBlueprint(input)).toEqual([]);
    });

    it("validates blueprint without LLM phrase block", () => {
      const input = {
        separator: ", ",
        blocks: [
          { type: "sku_field", key: "product_name" },
          { type: "variant_attribute", attributeId: "uuid-123" },
        ],
      };

      expect(validateBlueprint(input)).toEqual([]);
    });

    it("rejects invalid separator", () => {
      const input = {
        separator: " -- ",
        blocks: [{ type: "sku_field", key: "product_name" }],
      };

      const errors = validateBlueprint(input);

      expect(errors.some((e) => e.includes("Invalid separator"))).toBe(true);
    });

    it("rejects empty blocks array", () => {
      const input = {
        separator: " - ",
        blocks: [],
      };

      const errors = validateBlueprint(input);

      expect(errors).toContain("Blueprint must have at least one block");
    });

    it("rejects multiple LLM phrase blocks", () => {
      const input = {
        separator: " - ",
        blocks: [
          { type: "llm_phrase", key: "feature_phrase" },
          { type: "sku_field", key: "product_name" },
          { type: "llm_phrase", key: "feature_phrase" },
        ],
      };

      const errors = validateBlueprint(input);

      expect(errors).toContain("Only one llm_phrase block is allowed (found 2)");
    });

    it("rejects invalid sku_field key", () => {
      const input = {
        separator: " - ",
        blocks: [{ type: "sku_field", key: "invalid_key" }],
      };

      const errors = validateBlueprint(input);

      expect(errors.some((e) => e.includes('sku_field must have key "product_name"'))).toBe(true);
    });

    it("rejects variant_attribute without attributeId", () => {
      const input = {
        separator: " - ",
        blocks: [{ type: "variant_attribute", attributeId: "" }],
      };

      const errors = validateBlueprint(input);

      expect(errors.some((e) => e.includes("non-empty attributeId"))).toBe(true);
    });

    it("rejects invalid llm_phrase key", () => {
      const input = {
        separator: " - ",
        blocks: [{ type: "llm_phrase", key: "wrong_key" }],
      };

      const errors = validateBlueprint(input);

      expect(errors.some((e) => e.includes('llm_phrase must have key "feature_phrase"'))).toBe(true);
    });

    it("reports multiple errors at once", () => {
      const input = {
        separator: "invalid",
        blocks: [
          { type: "llm_phrase", key: "feature_phrase" },
          { type: "llm_phrase", key: "feature_phrase" },
        ],
      };

      const errors = validateBlueprint(input);

      expect(errors.length).toBeGreaterThanOrEqual(2);
    });
  });

  // ---------------------------------------------------------------------------
  // computeFixedTitleAndRemaining
  // ---------------------------------------------------------------------------
  describe("computeFixedTitleAndRemaining", () => {
    describe("join rules", () => {
      it("joins multiple blocks with separator", () => {
        const blueprint: TitleBlueprint = {
          separator: " - ",
          blocks: [
            { type: "sku_field", key: "product_name" },
            { type: "variant_attribute", attributeId: "size-id" },
            { type: "variant_attribute", attributeId: "color-id" },
          ],
        };
        const skuData: SkuTitleData = {
          productName: "Premium Widget",
          variantValuesByAttributeId: {
            "size-id": "Large",
            "color-id": "Blue",
          },
        };

        const result = computeFixedTitleAndRemaining(skuData, blueprint);

        expect(result.fixedTitle).toBe("Premium Widget - Large - Blue");
        expect(result.needsSeparatorBeforePhrase).toBe(false); // No LLM block
      });

      it("drops empty values from the join", () => {
        const blueprint: TitleBlueprint = {
          separator: ", ",
          blocks: [
            { type: "sku_field", key: "product_name" },
            { type: "variant_attribute", attributeId: "size-id" },
            { type: "variant_attribute", attributeId: "missing-id" },
            { type: "variant_attribute", attributeId: "color-id" },
          ],
        };
        const skuData: SkuTitleData = {
          productName: "Widget",
          variantValuesByAttributeId: {
            "size-id": "Medium",
            "color-id": "Red",
            // missing-id not present
          },
        };

        const result = computeFixedTitleAndRemaining(skuData, blueprint);

        expect(result.fixedTitle).toBe("Widget, Medium, Red");
      });

      it("handles blocks with whitespace-only values as empty", () => {
        const blueprint: TitleBlueprint = {
          separator: " | ",
          blocks: [
            { type: "sku_field", key: "product_name" },
            { type: "variant_attribute", attributeId: "size-id" },
          ],
        };
        const skuData: SkuTitleData = {
          productName: "Widget",
          variantValuesByAttributeId: {
            "size-id": "   ", // whitespace only
          },
        };

        const result = computeFixedTitleAndRemaining(skuData, blueprint);

        expect(result.fixedTitle).toBe("Widget");
      });
    });

    describe("missing values", () => {
      it("handles null product name", () => {
        const blueprint: TitleBlueprint = {
          separator: " - ",
          blocks: [
            { type: "sku_field", key: "product_name" },
            { type: "variant_attribute", attributeId: "size-id" },
          ],
        };
        const skuData: SkuTitleData = {
          productName: null,
          variantValuesByAttributeId: {
            "size-id": "Large",
          },
        };

        const result = computeFixedTitleAndRemaining(skuData, blueprint);

        expect(result.fixedTitle).toBe("Large");
      });

      it("handles empty product name string", () => {
        const blueprint: TitleBlueprint = {
          separator: " - ",
          blocks: [
            { type: "sku_field", key: "product_name" },
            { type: "variant_attribute", attributeId: "color-id" },
          ],
        };
        const skuData: SkuTitleData = {
          productName: "",
          variantValuesByAttributeId: {
            "color-id": "Green",
          },
        };

        const result = computeFixedTitleAndRemaining(skuData, blueprint);

        expect(result.fixedTitle).toBe("Green");
      });

      it("handles all missing values resulting in empty title", () => {
        const blueprint: TitleBlueprint = {
          separator: " - ",
          blocks: [
            { type: "sku_field", key: "product_name" },
            { type: "variant_attribute", attributeId: "missing-id" },
            { type: "llm_phrase", key: "feature_phrase" },
          ],
        };
        const skuData: SkuTitleData = {
          productName: null,
          variantValuesByAttributeId: {},
        };

        const result = computeFixedTitleAndRemaining(skuData, blueprint);

        expect(result.fixedTitle).toBe("");
        expect(result.remainingForPhrase).toBe(200);
        expect(result.needsSeparatorBeforePhrase).toBe(false);
      });
    });

    describe("separator handling", () => {
      const testSeparators: TitleSeparator[] = [" - ", " — ", ", ", " | "];

      testSeparators.forEach((separator) => {
        it(`correctly uses separator "${separator}"`, () => {
          const blueprint: TitleBlueprint = {
            separator,
            blocks: [
              { type: "sku_field", key: "product_name" },
              { type: "variant_attribute", attributeId: "attr-id" },
            ],
          };
          const skuData: SkuTitleData = {
            productName: "Product",
            variantValuesByAttributeId: { "attr-id": "Value" },
          };

          const result = computeFixedTitleAndRemaining(skuData, blueprint);

          expect(result.fixedTitle).toBe(`Product${separator}Value`);
        });
      });
    });

    describe("remaining budget math", () => {
      it("calculates remaining budget with LLM phrase block", () => {
        const blueprint: TitleBlueprint = {
          separator: " - ", // 3 chars
          blocks: [
            { type: "sku_field", key: "product_name" },
            { type: "llm_phrase", key: "feature_phrase" },
          ],
        };
        const skuData: SkuTitleData = {
          productName: "Premium Widget Pro", // 18 chars
          variantValuesByAttributeId: {},
        };

        const result = computeFixedTitleAndRemaining(skuData, blueprint);

        expect(result.fixedTitle).toBe("Premium Widget Pro");
        expect(result.fixedTitle.length).toBe(18);
        // remaining = 200 - 18 - 3 = 179
        expect(result.remainingForPhrase).toBe(179);
        expect(result.needsSeparatorBeforePhrase).toBe(true);
      });

      it("returns full budget when fixed title is empty", () => {
        const blueprint: TitleBlueprint = {
          separator: " - ",
          blocks: [
            { type: "sku_field", key: "product_name" },
            { type: "llm_phrase", key: "feature_phrase" },
          ],
        };
        const skuData: SkuTitleData = {
          productName: null,
          variantValuesByAttributeId: {},
        };

        const result = computeFixedTitleAndRemaining(skuData, blueprint);

        expect(result.fixedTitle).toBe("");
        expect(result.remainingForPhrase).toBe(200);
        expect(result.needsSeparatorBeforePhrase).toBe(false);
      });

      it("returns zero remaining when no LLM phrase block exists", () => {
        const blueprint: TitleBlueprint = {
          separator: " - ",
          blocks: [{ type: "sku_field", key: "product_name" }],
        };
        const skuData: SkuTitleData = {
          productName: "Widget",
          variantValuesByAttributeId: {},
        };

        const result = computeFixedTitleAndRemaining(skuData, blueprint);

        expect(result.remainingForPhrase).toBe(0);
        expect(result.needsSeparatorBeforePhrase).toBe(false);
      });

      it("handles negative remaining budget (fixed title too long)", () => {
        const blueprint: TitleBlueprint = {
          separator: " - ",
          blocks: [
            { type: "sku_field", key: "product_name" },
            { type: "llm_phrase", key: "feature_phrase" },
          ],
        };
        // Create a very long product name
        const longName = "A".repeat(199);
        const skuData: SkuTitleData = {
          productName: longName,
          variantValuesByAttributeId: {},
        };

        const result = computeFixedTitleAndRemaining(skuData, blueprint);

        expect(result.fixedTitle).toBe(longName);
        // remaining = 200 - 199 - 3 = -2
        expect(result.remainingForPhrase).toBe(-2);
        expect(result.needsSeparatorBeforePhrase).toBe(true);
      });

      it("respects custom maxLen parameter", () => {
        const blueprint: TitleBlueprint = {
          separator: " - ",
          blocks: [
            { type: "sku_field", key: "product_name" },
            { type: "llm_phrase", key: "feature_phrase" },
          ],
        };
        const skuData: SkuTitleData = {
          productName: "Widget", // 6 chars
          variantValuesByAttributeId: {},
        };

        const result = computeFixedTitleAndRemaining(skuData, blueprint, 100);

        // remaining = 100 - 6 - 3 = 91
        expect(result.remainingForPhrase).toBe(91);
      });

      it("accounts for multiple variant attributes in budget", () => {
        const blueprint: TitleBlueprint = {
          separator: " | ", // 3 chars
          blocks: [
            { type: "sku_field", key: "product_name" },
            { type: "variant_attribute", attributeId: "size" },
            { type: "variant_attribute", attributeId: "color" },
            { type: "variant_attribute", attributeId: "material" },
            { type: "llm_phrase", key: "feature_phrase" },
          ],
        };
        const skuData: SkuTitleData = {
          productName: "Frame", // 5 chars
          variantValuesByAttributeId: {
            size: "8x10", // 4 chars
            color: "Black", // 5 chars
            material: "Wood", // 4 chars
          },
        };

        const result = computeFixedTitleAndRemaining(skuData, blueprint);

        // Fixed: "Frame | 8x10 | Black | Wood" = 27 chars
        expect(result.fixedTitle).toBe("Frame | 8x10 | Black | Wood");
        expect(result.fixedTitle.length).toBe(27);
        // remaining = 200 - 27 - 3 = 170
        expect(result.remainingForPhrase).toBe(170);
      });
    });

    it("preserves block order from blueprint", () => {
      const blueprint: TitleBlueprint = {
        separator: " - ",
        blocks: [
          { type: "variant_attribute", attributeId: "brand" },
          { type: "sku_field", key: "product_name" },
          { type: "variant_attribute", attributeId: "size" },
        ],
      };
      const skuData: SkuTitleData = {
        productName: "Widget",
        variantValuesByAttributeId: {
          brand: "Acme",
          size: "Large",
        },
      };

      const result = computeFixedTitleAndRemaining(skuData, blueprint);

      expect(result.fixedTitle).toBe("Acme - Widget - Large");
    });
  });

  // ---------------------------------------------------------------------------
  // assembleTitle
  // ---------------------------------------------------------------------------
  describe("assembleTitle", () => {
    it("joins fixed title and phrase with separator", () => {
      const result = assembleTitle("Premium Widget", " - ", "Durable and Stylish");

      expect(result).toBe("Premium Widget - Durable and Stylish");
    });

    it("returns only fixed title when phrase is empty", () => {
      expect(assembleTitle("Premium Widget", " - ", "")).toBe("Premium Widget");
      expect(assembleTitle("Premium Widget", " - ", null)).toBe("Premium Widget");
      expect(assembleTitle("Premium Widget", " - ", undefined)).toBe("Premium Widget");
    });

    it("returns only phrase when fixed title is empty", () => {
      expect(assembleTitle("", " - ", "Great Feature")).toBe("Great Feature");
      expect(assembleTitle("   ", " - ", "Great Feature")).toBe("Great Feature");
    });

    it("returns empty string when both parts are empty", () => {
      expect(assembleTitle("", " - ", "")).toBe("");
      expect(assembleTitle("", " - ", null)).toBe("");
      expect(assembleTitle("   ", " - ", "   ")).toBe("");
    });

    it("trims whitespace from both parts", () => {
      const result = assembleTitle("  Widget  ", " - ", "  Feature  ");

      expect(result).toBe("Widget - Feature");
    });

    it("works with all separator types", () => {
      expect(assembleTitle("A", " - ", "B")).toBe("A - B");
      expect(assembleTitle("A", " — ", "B")).toBe("A — B");
      expect(assembleTitle("A", ", ", "B")).toBe("A, B");
      expect(assembleTitle("A", " | ", "B")).toBe("A | B");
    });
  });

  // ---------------------------------------------------------------------------
  // enforceMaxLenAtWordBoundary
  // ---------------------------------------------------------------------------
  describe("enforceMaxLenAtWordBoundary", () => {
    it("returns unchanged text when under max length", () => {
      const text = "Short text";
      expect(enforceMaxLenAtWordBoundary(text, 200)).toBe(text);
    });

    it("returns unchanged text when exactly at max length", () => {
      const text = "Exact";
      expect(enforceMaxLenAtWordBoundary(text, 5)).toBe(text);
    });

    it("trims at word boundary when over max length", () => {
      const text = "The quick brown fox jumps over the lazy dog";
      const result = enforceMaxLenAtWordBoundary(text, 20);

      expect(result).toBe("The quick brown fox");
      expect(result.length).toBeLessThanOrEqual(20);
    });

    it("handles single long word by truncating", () => {
      const text = "Supercalifragilisticexpialidocious";
      const result = enforceMaxLenAtWordBoundary(text, 10);

      expect(result).toBe("Supercalif");
    });

    it("removes trailing punctuation after trim", () => {
      const text = "Premium Widget - High Quality Materials";
      const result = enforceMaxLenAtWordBoundary(text, 18);

      // Would be "Premium Widget - H" but trims to word boundary
      // "Premium Widget -" then removes trailing " -"
      expect(result).toBe("Premium Widget");
    });

    it("removes trailing separators after trim", () => {
      const text = "Widget | Feature | Benefit";
      const result = enforceMaxLenAtWordBoundary(text, 9);

      // "Widget | " -> "Widget |" -> trim trailing -> "Widget"
      expect(result).toBe("Widget");
    });

    it("handles em dash separator in trim", () => {
      const text = "Widget — Great for home use";
      const result = enforceMaxLenAtWordBoundary(text, 10);

      // "Widget — G" -> "Widget —" -> trim trailing -> "Widget"
      expect(result).toBe("Widget");
    });

    it("handles comma separator in trim", () => {
      const text = "Widget, Durable, Stylish";
      const result = enforceMaxLenAtWordBoundary(text, 8);

      // "Widget, " -> "Widget," -> trim trailing -> "Widget"
      expect(result).toBe("Widget");
    });
  });

  // ---------------------------------------------------------------------------
  // Integration / Edge Cases
  // ---------------------------------------------------------------------------
  describe("integration scenarios", () => {
    it("handles realistic e-commerce title assembly", () => {
      const blueprint: TitleBlueprint = {
        separator: " - ",
        blocks: [
          { type: "variant_attribute", attributeId: "brand" },
          { type: "sku_field", key: "product_name" },
          { type: "variant_attribute", attributeId: "size" },
          { type: "variant_attribute", attributeId: "color" },
          { type: "llm_phrase", key: "feature_phrase" },
        ],
      };
      const skuData: SkuTitleData = {
        productName: "Picture Frame",
        variantValuesByAttributeId: {
          brand: "ArtDisplay",
          size: '8x10"',
          color: "Black",
        },
      };

      const { fixedTitle, remainingForPhrase, needsSeparatorBeforePhrase } =
        computeFixedTitleAndRemaining(skuData, blueprint);

      expect(fixedTitle).toBe('ArtDisplay - Picture Frame - 8x10" - Black');

      const featurePhrase = "Perfect for displaying cherished memories";
      const finalTitle = assembleTitle(fixedTitle, blueprint.separator, featurePhrase);

      expect(finalTitle).toBe(
        'ArtDisplay - Picture Frame - 8x10" - Black - Perfect for displaying cherished memories'
      );
      expect(finalTitle.length).toBeLessThanOrEqual(AMAZON_TITLE_MAX_LEN);
      expect(needsSeparatorBeforePhrase).toBe(true);
      expect(remainingForPhrase).toBeGreaterThan(featurePhrase.length);
    });

    it("handles SKU with minimal data", () => {
      const blueprint: TitleBlueprint = {
        separator: " | ",
        blocks: [
          { type: "sku_field", key: "product_name" },
          { type: "variant_attribute", attributeId: "brand" },
          { type: "variant_attribute", attributeId: "category" },
          { type: "llm_phrase", key: "feature_phrase" },
        ],
      };
      const skuData: SkuTitleData = {
        productName: "Generic Item",
        variantValuesByAttributeId: {}, // No variant attributes filled
      };

      const { fixedTitle, remainingForPhrase } = computeFixedTitleAndRemaining(
        skuData,
        blueprint
      );

      expect(fixedTitle).toBe("Generic Item");
      // remaining = 200 - 12 - 3 = 185
      expect(remainingForPhrase).toBe(185);
    });

    it("correctly calculates when fixed title nearly fills max length", () => {
      const blueprint: TitleBlueprint = {
        separator: " - ",
        blocks: [
          { type: "sku_field", key: "product_name" },
          { type: "llm_phrase", key: "feature_phrase" },
        ],
      };
      // Product name that leaves very little room
      const skuData: SkuTitleData = {
        productName: "A".repeat(190), // 190 chars
        variantValuesByAttributeId: {},
      };

      const { fixedTitle, remainingForPhrase } = computeFixedTitleAndRemaining(
        skuData,
        blueprint
      );

      expect(fixedTitle.length).toBe(190);
      // remaining = 200 - 190 - 3 = 7
      expect(remainingForPhrase).toBe(7);
    });

    it("round-trip: parse then use blueprint", () => {
      const rawInput = {
        separator: " - ",
        blocks: [
          { type: "sku_field", key: "product_name" },
          { type: "variant_attribute", attributeId: "color" },
          { type: "llm_phrase", key: "feature_phrase" },
        ],
      };

      const { blueprint } = parseTitleBlueprint(rawInput);
      expect(blueprint).not.toBeNull();

      const skuData: SkuTitleData = {
        productName: "Gadget",
        variantValuesByAttributeId: { color: "Silver" },
      };

      const { fixedTitle, remainingForPhrase } = computeFixedTitleAndRemaining(skuData, blueprint!);

      expect(fixedTitle).toBe("Gadget - Silver");
      expect(remainingForPhrase).toBe(200 - 15 - 3); // 182

      const finalTitle = assembleTitle(fixedTitle, blueprint!.separator, "Sleek and Modern");
      expect(finalTitle).toBe("Gadget - Silver - Sleek and Modern");
    });
  });
});
