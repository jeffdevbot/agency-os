import { describe, expect, it } from "vitest";
import { cleanKeywords } from "@agency/lib/composer/keywords/cleaning";
import type { KeywordCleanSettings } from "@agency/lib/composer/types";

const project = {
  clientName: "Acme",
  whatNotToSay: ["Contoso", "BrandX"],
};

const variants = [
  { attributes: { color: "Blue/Navy", size: "XL", dimensions: "10x12" } },
  { attributes: { colour: "Red", pack_size: "3 pack" } },
];

const runClean = (keywords: string[], config: KeywordCleanSettings = {}) =>
  cleanKeywords(keywords, config, { project, variants });

describe("cleanKeywords", () => {
  it("dedupes and removes brand + competitor terms from user-supplied fields", () => {
    const { cleaned, removed } = runClean(
      ["Acme Widget", "acme widget", "contoso special", "fresh item"],
      { removeBrandTerms: true, removeCompetitorTerms: true },
    );

    expect(cleaned).toEqual(["fresh item"]);
    expect(removed).toEqual([
      { term: "Acme Widget", reason: "brand" },
      { term: "acme widget", reason: "duplicate" },
      { term: "contoso special", reason: "competitor" },
    ]);
  });

  it("removes colors and sizes using attribute-derived values with fallback heuristics", () => {
    const { cleaned, removed } = runClean(
      ["blue shirt", "navy hoodie", "xl pants", "10x12 frame", "bright yellow case"],
      { removeColors: true, removeSizes: true },
    );

    expect(cleaned).toEqual([]);
    expect(removed.map((r) => r.reason)).toEqual([
      "color",
      "color",
      "size",
      "size",
      "color",
    ]);
  });

  it("keeps color/size terms when toggles are false", () => {
    const { cleaned, removed } = runClean(
      ["blue shirt", "xl pants"],
      { removeColors: false, removeSizes: false },
    );

    expect(cleaned).toEqual(["blue shirt", "xl pants"]);
    expect(removed).toHaveLength(0);
  });

  it("removes stopwords from the curated list", () => {
    const { cleaned, removed } = runClean(["n/a", "valid term", "TBD"], {});

    expect(cleaned).toEqual(["valid term"]);
    expect(removed).toEqual([
      { term: "n/a", reason: "stopword" },
      { term: "TBD", reason: "stopword" },
    ]);
  });

  it("is deterministic for the same input/config", () => {
    const input = ["Blue Shirt", "blue shirt", "BrandX bag", "fresh tote"];
    const config: KeywordCleanSettings = {
      removeColors: true,
      removeSizes: true,
      removeBrandTerms: true,
      removeCompetitorTerms: true,
    };

    const firstRun = runClean(input, config);
    const secondRun = runClean(input, config);

    expect(firstRun).toEqual(secondRun);
  });
});
