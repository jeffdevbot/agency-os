import { describe, expect, it } from "vitest";
import {
  dedupeKeywords,
  mergeKeywords,
  parseKeywordsCsv,
  validateKeywordCount,
} from "@agency/lib/composer/keywords/utils";

describe("dedupeKeywords", () => {
  it("removes case-insensitive duplicates", () => {
    const input = ["Blue Shirt", "blue shirt", "BLUE SHIRT", "Red Shoes"];
    const result = dedupeKeywords(input);
    expect(result).toEqual(["Blue Shirt", "Red Shoes"]);
  });

  it("preserves first occurrence when deduplicating", () => {
    const input = ["Apple", "Banana", "apple", "Cherry"];
    const result = dedupeKeywords(input);
    expect(result).toEqual(["Apple", "Banana", "Cherry"]);
  });

  it("trims whitespace from keywords", () => {
    const input = ["  Blue Shirt  ", " Red Shoes", "Green Hat"];
    const result = dedupeKeywords(input);
    expect(result).toEqual(["Blue Shirt", "Red Shoes", "Green Hat"]);
  });

  it("removes empty strings after trimming", () => {
    const input = ["Apple", "  ", "", "Banana", "   "];
    const result = dedupeKeywords(input);
    expect(result).toEqual(["Apple", "Banana"]);
  });

  it("handles empty array", () => {
    expect(dedupeKeywords([])).toEqual([]);
  });

  it("handles array with only whitespace", () => {
    expect(dedupeKeywords(["  ", "   ", ""])).toEqual([]);
  });

  it("handles special characters and unicode", () => {
    const input = ["Café", "café", "CAFÉ", "Naïve", "naïve"];
    const result = dedupeKeywords(input);
    expect(result).toEqual(["Café", "Naïve"]);
  });
});

describe("mergeKeywords", () => {
  it("merges two arrays without duplicates", () => {
    const existing = ["Apple", "Banana"];
    const incoming = ["Cherry", "Date"];
    const result = mergeKeywords(existing, incoming);
    expect(result).toEqual(["Apple", "Banana", "Cherry", "Date"]);
  });

  it("removes duplicates across arrays (case-insensitive)", () => {
    const existing = ["Apple", "Banana"];
    const incoming = ["apple", "Cherry", "BANANA"];
    const result = mergeKeywords(existing, incoming);
    expect(result).toEqual(["Apple", "Banana", "Cherry"]);
  });

  it("preserves existing keywords first", () => {
    const existing = ["APPLE", "BANANA"];
    const incoming = ["apple", "banana", "Cherry"];
    const result = mergeKeywords(existing, incoming);
    // Existing versions (uppercase) should be preserved
    expect(result).toEqual(["APPLE", "BANANA", "Cherry"]);
  });

  it("handles empty existing array", () => {
    const result = mergeKeywords([], ["Apple", "Banana"]);
    expect(result).toEqual(["Apple", "Banana"]);
  });

  it("handles empty incoming array", () => {
    const result = mergeKeywords(["Apple", "Banana"], []);
    expect(result).toEqual(["Apple", "Banana"]);
  });

  it("handles both arrays empty", () => {
    expect(mergeKeywords([], [])).toEqual([]);
  });

  it("trims whitespace during merge", () => {
    const existing = ["  Apple  ", "Banana"];
    const incoming = ["  apple  ", "  Cherry  "];
    const result = mergeKeywords(existing, incoming);
    expect(result).toEqual(["Apple", "Banana", "Cherry"]);
  });
});

describe("parseKeywordsCsv", () => {
  it("parses single-column CSV", () => {
    const csv = `blue shirt
red shoes
green hat`;
    const result = parseKeywordsCsv(csv);
    expect(result).toEqual(["blue shirt", "red shoes", "green hat"]);
  });

  it("skips header row (lowercase 'keyword')", () => {
    const csv = `keyword
blue shirt
red shoes`;
    const result = parseKeywordsCsv(csv);
    expect(result).toEqual(["blue shirt", "red shoes"]);
  });

  it("skips header row (case-insensitive)", () => {
    const csv = `KEYWORD
blue shirt
red shoes`;
    const result = parseKeywordsCsv(csv);
    expect(result).toEqual(["blue shirt", "red shoes"]);
  });

  it("skips quoted header row", () => {
    const csv = `"keyword"
"blue shirt"
"red shoes"`;
    const result = parseKeywordsCsv(csv);
    expect(result).toEqual(["blue shirt", "red shoes"]);
  });

  it("removes surrounding quotes from values", () => {
    const csv = `"blue shirt"
'red shoes'
green hat`;
    const result = parseKeywordsCsv(csv);
    expect(result).toEqual(["blue shirt", "red shoes", "green hat"]);
  });

  it("handles Windows line endings (CRLF)", () => {
    const csv = "blue shirt\r\nred shoes\r\ngreen hat";
    const result = parseKeywordsCsv(csv);
    expect(result).toEqual(["blue shirt", "red shoes", "green hat"]);
  });

  it("handles mixed line endings", () => {
    const csv = "blue shirt\nred shoes\r\ngreen hat";
    const result = parseKeywordsCsv(csv);
    expect(result).toEqual(["blue shirt", "red shoes", "green hat"]);
  });

  it("skips empty lines", () => {
    const csv = `blue shirt

red shoes

green hat`;
    const result = parseKeywordsCsv(csv);
    expect(result).toEqual(["blue shirt", "red shoes", "green hat"]);
  });

  it("trims whitespace from each line", () => {
    const csv = `  blue shirt
  red shoes
green hat`;
    const result = parseKeywordsCsv(csv);
    expect(result).toEqual(["blue shirt", "red shoes", "green hat"]);
  });

  it("handles empty CSV", () => {
    expect(parseKeywordsCsv("")).toEqual([]);
    expect(parseKeywordsCsv("  ")).toEqual([]);
    expect(parseKeywordsCsv("\n\n")).toEqual([]);
  });

  it("handles UTF-8 characters", () => {
    const csv = `Café au lait
Naïve approach
Résumé`;
    const result = parseKeywordsCsv(csv);
    expect(result).toEqual(["Café au lait", "Naïve approach", "Résumé"]);
  });

  it("handles emoji", () => {
    const csv = `blue shirt 👕
red shoes 👟`;
    const result = parseKeywordsCsv(csv);
    expect(result).toEqual(["blue shirt 👕", "red shoes 👟"]);
  });
});

describe("validateKeywordCount", () => {
  it("returns error when less than 5 keywords", () => {
    const result = validateKeywordCount(["one", "two", "three"]);
    expect(result.valid).toBe(false);
    expect(result.error).toContain("At least 5 keywords are required");
    expect(result.error).toContain("You have 3");
  });

  it("returns error for 0 keywords", () => {
    const result = validateKeywordCount([]);
    expect(result.valid).toBe(false);
    expect(result.error).toContain("At least 5 keywords are required");
    expect(result.error).toContain("You have 0");
  });

  it("returns error when exactly 4 keywords", () => {
    const result = validateKeywordCount(["one", "two", "three", "four"]);
    expect(result.valid).toBe(false);
    expect(result.error).toBeDefined();
  });

  it("returns valid for exactly 5 keywords", () => {
    const result = validateKeywordCount(["one", "two", "three", "four", "five"]);
    expect(result.valid).toBe(true);
    expect(result.error).toBeUndefined();
  });

  it("returns warning when less than 20 keywords", () => {
    const keywords = Array.from({ length: 10 }, (_, i) => `keyword${i}`);
    const result = validateKeywordCount(keywords);
    expect(result.valid).toBe(true);
    expect(result.error).toBeUndefined();
    expect(result.warning).toContain("only 10 keywords");
    expect(result.warning).toContain("recommend 50-100+");
  });

  it("returns warning for exactly 19 keywords", () => {
    const keywords = Array.from({ length: 19 }, (_, i) => `keyword${i}`);
    const result = validateKeywordCount(keywords);
    expect(result.valid).toBe(true);
    expect(result.warning).toBeDefined();
  });

  it("returns no warning for exactly 20 keywords", () => {
    const keywords = Array.from({ length: 20 }, (_, i) => `keyword${i}`);
    const result = validateKeywordCount(keywords);
    expect(result.valid).toBe(true);
    expect(result.error).toBeUndefined();
    expect(result.warning).toBeUndefined();
  });

  it("returns valid for 100 keywords", () => {
    const keywords = Array.from({ length: 100 }, (_, i) => `keyword${i}`);
    const result = validateKeywordCount(keywords);
    expect(result.valid).toBe(true);
    expect(result.error).toBeUndefined();
    expect(result.warning).toBeUndefined();
  });

  it("returns valid for exactly 5000 keywords", () => {
    const keywords = Array.from({ length: 5000 }, (_, i) => `keyword${i}`);
    const result = validateKeywordCount(keywords);
    expect(result.valid).toBe(true);
    expect(result.error).toBeUndefined();
  });

  it("returns error for 5001 keywords", () => {
    const keywords = Array.from({ length: 5001 }, (_, i) => `keyword${i}`);
    const result = validateKeywordCount(keywords);
    expect(result.valid).toBe(false);
    expect(result.error).toContain("Maximum 5000 keywords allowed");
    expect(result.error).toContain("You have 5001");
  });

  it("returns error for 10000 keywords", () => {
    const keywords = Array.from({ length: 10000 }, (_, i) => `keyword${i}`);
    const result = validateKeywordCount(keywords);
    expect(result.valid).toBe(false);
    expect(result.error).toContain("Maximum 5000 keywords allowed");
  });
});
