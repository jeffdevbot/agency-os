import { describe, expect, it } from "vitest";
import { getSearchParam, parseAllowedRange, resolveSearchParams } from "./searchParams";

describe("resolveSearchParams", () => {
  it("returns undefined when no search params are provided", async () => {
    await expect(resolveSearchParams(undefined)).resolves.toBeUndefined();
  });

  it("supports plain-object search params", async () => {
    await expect(resolveSearchParams({ range: "30" })).resolves.toEqual({ range: "30" });
  });

  it("supports promise-based App Router search params", async () => {
    await expect(resolveSearchParams(Promise.resolve({ range: "90" }))).resolves.toEqual({
      range: "90",
    });
  });
});

describe("getSearchParam", () => {
  it("returns string values directly", () => {
    expect(getSearchParam({ range: "30" }, "range")).toBe("30");
  });

  it("returns the first value from array params", () => {
    expect(getSearchParam({ range: ["90", "30"] }, "range")).toBe("90");
  });
});

describe("parseAllowedRange", () => {
  it("returns the parsed range when it is allowed", () => {
    expect(parseAllowedRange("90", [7, 30, 90], 7)).toBe(90);
  });

  it("falls back when the value is invalid or disallowed", () => {
    expect(parseAllowedRange("14", [7, 30, 90], 7)).toBe(7);
    expect(parseAllowedRange("abc", [7, 30, 90], 7)).toBe(7);
  });
});
