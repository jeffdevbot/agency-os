import { describe, it, expect } from "vitest";
import { inferAttributes } from "./inferAttributes";
import type { ComposerSkuVariant } from "@agency/lib/composer/types";

const createVariant = (overrides: Partial<ComposerSkuVariant> & { id: string; sku: string }): ComposerSkuVariant => ({
  organizationId: "org-1",
  projectId: "proj-1",
  groupId: null,
  asin: null,
  parentSku: null,
  attributes: {},
  notes: null,
  createdAt: new Date().toISOString(),
  ...overrides,
});

describe.skip("inferAttributes (Composer)", () => {
  it("returns empty array when no variants provided", () => {
    const result = inferAttributes([]);
    expect(result).toEqual([]);
  });

  it("returns empty array when variants have no attributes", () => {
    const variants: ComposerSkuVariant[] = [
      createVariant({ id: "1", sku: "SKU-001" }),
    ];
    const result = inferAttributes(variants);
    expect(result).toEqual([]);
  });

  it("counts filled attributes correctly for single variant", () => {
    const variants: ComposerSkuVariant[] = [
      createVariant({
        id: "1",
        sku: "SKU-001",
        attributes: {
          color: "Red",
          size: "Large",
        },
      }),
    ];
    const result = inferAttributes(variants);
    expect(result).toHaveLength(2);
    expect(result).toContainEqual({ key: "color", filledCount: 1, totalCount: 1 });
    expect(result).toContainEqual({ key: "size", filledCount: 1, totalCount: 1 });
  });

  it("counts filled attributes across multiple variants", () => {
    const variants: ComposerSkuVariant[] = [
      createVariant({
        id: "1",
        sku: "SKU-001",
        attributes: { color: "Red", size: "Large" },
      }),
      createVariant({
        id: "2",
        sku: "SKU-002",
        attributes: { color: "Blue", size: "" },
      }),
      createVariant({
        id: "3",
        sku: "SKU-003",
        attributes: { color: "", size: "Medium" },
      }),
    ];
    const result = inferAttributes(variants);
    expect(result).toHaveLength(2);
    expect(result).toContainEqual({ key: "color", filledCount: 2, totalCount: 3 });
    expect(result).toContainEqual({ key: "size", filledCount: 2, totalCount: 3 });
  });

  it("handles null attribute values as unfilled", () => {
    const variants: ComposerSkuVariant[] = [
      createVariant({
        id: "1",
        sku: "SKU-001",
        attributes: { color: null },
      }),
    ];
    const result = inferAttributes(variants);
    expect(result).toEqual([{ key: "color", filledCount: 0, totalCount: 1 }]);
  });

  it("collects unique keys from all variants", () => {
    const variants: ComposerSkuVariant[] = [
      createVariant({
        id: "1",
        sku: "SKU-001",
        attributes: { color: "Red" },
      }),
      createVariant({
        id: "2",
        sku: "SKU-002",
        attributes: { size: "Large" },
      }),
    ];
    const result = inferAttributes(variants);
    expect(result).toHaveLength(2);
    // color: only first variant has it, so filledCount=1, totalCount=2
    expect(result).toContainEqual({ key: "color", filledCount: 1, totalCount: 2 });
    // size: only second variant has it, so filledCount=1, totalCount=2
    expect(result).toContainEqual({ key: "size", filledCount: 1, totalCount: 2 });
  });

  it("sorts results alphabetically by key", () => {
    const variants: ComposerSkuVariant[] = [
      createVariant({
        id: "1",
        sku: "SKU-001",
        attributes: { zebra: "yes", apple: "red", mango: "yellow" },
      }),
    ];
    const result = inferAttributes(variants);
    expect(result.map((r) => r.key)).toEqual(["apple", "mango", "zebra"]);
  });

  it("handles variants with undefined attributes", () => {
    const variants = [
      {
        ...createVariant({ id: "1", sku: "SKU-001" }),
        attributes: undefined,
      },
    ] as unknown as ComposerSkuVariant[];
    const result = inferAttributes(variants);
    expect(result).toEqual([]);
  });

  it("handles mixed variants with and without attributes", () => {
    const variants = [
      createVariant({
        id: "1",
        sku: "SKU-001",
        attributes: { color: "Red" },
      }),
      {
        ...createVariant({ id: "2", sku: "SKU-002" }),
        attributes: undefined,
      },
    ] as unknown as ComposerSkuVariant[];
    const result = inferAttributes(variants);
    // color exists in first variant, totalCount includes all variants
    expect(result).toEqual([{ key: "color", filledCount: 1, totalCount: 2 }]);
  });
});
