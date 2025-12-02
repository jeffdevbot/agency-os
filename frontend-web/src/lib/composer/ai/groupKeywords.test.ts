import { describe, it, expect, vi, beforeEach } from "vitest";
import type { GroupingConfig } from "@agency/lib/composer/types";
import { groupKeywords } from "./groupKeywords";
import * as openaiModule from "./openai";

vi.mock("./openai");

const mockContext = {
  project: {
    clientName: "Acme Corp",
    category: "Apparel",
  },
  poolType: "body" as const,
  poolId: "pool-123",
};

describe("groupKeywords", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("returns empty array for empty keywords", async () => {
    const result = await groupKeywords([], { basis: "single" }, mockContext);
    expect(result.groups).toEqual([]);
    expect(result.usage.tokensTotal).toBe(0);
  });

  it("returns single group for basis=single", async () => {
    const keywords = ["blue shirt", "red dress", "cotton pants"];
    const config: GroupingConfig = { basis: "single" };

    const result = await groupKeywords(keywords, config, mockContext);

    expect(result.groups).toHaveLength(1);
    expect(result.groups[0].label).toBe("General");
    expect(result.groups[0].phrases).toEqual(keywords);
    expect(result.groups[0].groupIndex).toBe(0);
    expect(result.groups[0].metadata.basis).toBe("single");
  });

  it("returns single group for single keyword", async () => {
    const keywords = ["blue shirt"];
    const config: GroupingConfig = { basis: "custom", groupCount: 3 };

    const result = await groupKeywords(keywords, config, mockContext);

    expect(result.groups).toHaveLength(1);
    expect(result.groups[0].label).toBe("General");
    expect(result.groups[0].phrases).toEqual(keywords);
  });

  it("calls OpenAI for custom grouping and parses response", async () => {
    const keywords = ["blue shirt", "red dress", "green pants"];
    const config: GroupingConfig = { basis: "custom", groupCount: 2 };

    const mockAIResponse = {
      content: JSON.stringify({
        groups: [
          { label: "Blue Items", keywords: ["blue shirt"] },
          { label: "Red/Green Items", keywords: ["red dress", "green pants"] },
        ],
      }),
      tokensIn: 100,
      tokensOut: 50,
      tokensTotal: 150,
      model: "gpt-5.1-nano",
      durationMs: 500,
    };

    vi.spyOn(openaiModule, "createChatCompletion").mockResolvedValue(mockAIResponse);
    vi.spyOn(openaiModule, "parseJSONResponse").mockReturnValue({
      groups: [
        { label: "Blue Items", keywords: ["blue shirt"] },
        { label: "Red/Green Items", keywords: ["red dress", "green pants"] },
      ],
    });

    const result = await groupKeywords(keywords, config, mockContext);

    expect(result.groups).toHaveLength(2);
    expect(result.groups[0].label).toBe("Blue Items");
    expect(result.groups[0].phrases).toEqual(["blue shirt"]);
    expect(result.groups[0].groupIndex).toBe(0);
    expect(result.groups[1].label).toBe("Red/Green Items");
    expect(result.groups[1].phrases).toEqual(["red dress", "green pants"]);
    expect(result.groups[1].groupIndex).toBe(1);

    expect(openaiModule.createChatCompletion).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({ role: "system" }),
        expect.objectContaining({ role: "user" }),
      ]),
      expect.objectContaining({
        temperature: 0.3,
        maxTokens: 4000,
      }),
    );
  });

  it("adds missing keywords to last group if AI doesn't assign all", async () => {
    const keywords = ["blue shirt", "red dress", "green pants"];
    const config: GroupingConfig = { basis: "custom", groupCount: 2 };

    const mockAIResponse = {
      content: JSON.stringify({
        groups: [{ label: "Blue Items", keywords: ["blue shirt"] }],
      }),
      tokensIn: 100,
      tokensOut: 50,
      tokensTotal: 150,
      model: "gpt-5.1-nano",
      durationMs: 500,
    };

    vi.spyOn(openaiModule, "createChatCompletion").mockResolvedValue(mockAIResponse);
    vi.spyOn(openaiModule, "parseJSONResponse").mockReturnValue({
      groups: [{ label: "Blue Items", keywords: ["blue shirt"] }],
    });

    const result = await groupKeywords(keywords, config, mockContext);

    expect(result.groups).toHaveLength(1);
    expect(result.groups[0].phrases).toContain("blue shirt");
    expect(result.groups[0].phrases).toContain("red dress");
    expect(result.groups[0].phrases).toContain("green pants");
  });

  it("falls back to single group when AI call fails", async () => {
    const keywords = ["blue shirt", "red dress", "green pants"];
    const config: GroupingConfig = { basis: "custom", groupCount: 2 };

    vi.spyOn(openaiModule, "createChatCompletion").mockRejectedValue(
      new Error("API error"),
    );

    const result = await groupKeywords(keywords, config, mockContext);

    expect(result.groups).toHaveLength(1);
    expect(result.groups[0].label).toBe("General");
    expect(result.groups[0].phrases).toEqual(keywords);
    expect(result.groups[0].metadata.fallback).toBe(true);
  });

  it("builds correct prompt for per_sku basis", async () => {
    const keywords = ["blue shirt SKU-001", "red dress SKU-002"];
    const config: GroupingConfig = { basis: "per_sku" };

    const mockAIResponse = {
      content: JSON.stringify({
        groups: [
          { label: "SKU-001", keywords: ["blue shirt SKU-001"] },
          { label: "SKU-002", keywords: ["red dress SKU-002"] },
        ],
      }),
      tokensIn: 100,
      tokensOut: 50,
      tokensTotal: 150,
      model: "gpt-5.1-nano",
      durationMs: 500,
    };

    vi.spyOn(openaiModule, "createChatCompletion").mockResolvedValue(mockAIResponse);
    vi.spyOn(openaiModule, "parseJSONResponse").mockReturnValue({
      groups: [
        { label: "SKU-001", keywords: ["blue shirt SKU-001"] },
        { label: "SKU-002", keywords: ["red dress SKU-002"] },
      ],
    });

    const result = await groupKeywords(keywords, config, mockContext);

    expect(result.groups).toHaveLength(2);

    const calls = vi.mocked(openaiModule.createChatCompletion).mock.calls;
    const userMessage = calls[0][0][1].content;
    expect(userMessage).toContain("Create one group per SKU variation");
  });

  it("builds correct prompt for attribute basis", async () => {
    const keywords = ["blue shirt", "red shirt", "blue pants"];
    const config: GroupingConfig = { basis: "attribute", attributeName: "Color" };

    const mockAIResponse = {
      content: JSON.stringify({
        groups: [
          { label: "Blue", keywords: ["blue shirt", "blue pants"] },
          { label: "Red", keywords: ["red shirt"] },
        ],
      }),
      tokensIn: 100,
      tokensOut: 50,
      tokensTotal: 150,
      model: "gpt-5.1-nano",
      durationMs: 500,
    };

    vi.spyOn(openaiModule, "createChatCompletion").mockResolvedValue(mockAIResponse);
    vi.spyOn(openaiModule, "parseJSONResponse").mockReturnValue({
      groups: [
        { label: "Blue", keywords: ["blue shirt", "blue pants"] },
        { label: "Red", keywords: ["red shirt"] },
      ],
    });

    const result = await groupKeywords(keywords, config, mockContext);

    expect(result.groups).toHaveLength(2);

    const calls = vi.mocked(openaiModule.createChatCompletion).mock.calls;
    const userMessage = calls[0][0][1].content;
    expect(userMessage).toContain("Group keywords by the attribute: Color");
  });

  it("falls back to single group when attributeName missing for attribute basis", async () => {
    const keywords = ["blue shirt", "red dress"];
    const config: GroupingConfig = { basis: "attribute" };

    const result = await groupKeywords(keywords, config, mockContext);

    expect(result.groups).toHaveLength(1);
    expect(result.groups[0].label).toBe("General");
    expect(result.groups[0].phrases).toEqual(keywords);
    expect(result.groups[0].metadata.fallback).toBe(true);
  });

  it("falls back to single group when groupCount missing for custom basis", async () => {
    const keywords = ["blue shirt", "red dress"];
    const config: GroupingConfig = { basis: "custom" };

    const result = await groupKeywords(keywords, config, mockContext);

    expect(result.groups).toHaveLength(1);
    expect(result.groups[0].label).toBe("General");
    expect(result.groups[0].phrases).toEqual(keywords);
    expect(result.groups[0].metadata.fallback).toBe(true);
  });

  it("includes phrasesPerGroup hint in prompt when provided", async () => {
    const keywords = ["kw1", "kw2", "kw3", "kw4", "kw5", "kw6"];
    const config: GroupingConfig = {
      basis: "custom",
      groupCount: 2,
      phrasesPerGroup: 3,
    };

    const mockAIResponse = {
      content: JSON.stringify({
        groups: [
          { label: "Group 1", keywords: ["kw1", "kw2", "kw3"] },
          { label: "Group 2", keywords: ["kw4", "kw5", "kw6"] },
        ],
      }),
      tokensIn: 100,
      tokensOut: 50,
      tokensTotal: 150,
      model: "gpt-5.1-nano",
      durationMs: 500,
    };

    vi.spyOn(openaiModule, "createChatCompletion").mockResolvedValue(mockAIResponse);
    vi.spyOn(openaiModule, "parseJSONResponse").mockReturnValue({
      groups: [
        { label: "Group 1", keywords: ["kw1", "kw2", "kw3"] },
        { label: "Group 2", keywords: ["kw4", "kw5", "kw6"] },
      ],
    });

    await groupKeywords(keywords, config, mockContext);

    const calls = vi.mocked(openaiModule.createChatCompletion).mock.calls;
    const userMessage = calls[0][0][1].content;
    expect(userMessage).toContain("approximately 3 phrases");
  });

  it("sets correct metadata on groups", async () => {
    const keywords = ["blue shirt", "red dress"];
    const config: GroupingConfig = { basis: "attribute", attributeName: "Color" };

    const mockAIResponse = {
      content: JSON.stringify({
        groups: [
          { label: "Blue", keywords: ["blue shirt"] },
          { label: "Red", keywords: ["red dress"] },
        ],
      }),
      tokensIn: 100,
      tokensOut: 50,
      tokensTotal: 150,
      model: "gpt-5.1-nano",
      durationMs: 500,
    };

    vi.spyOn(openaiModule, "createChatCompletion").mockResolvedValue(mockAIResponse);
    vi.spyOn(openaiModule, "parseJSONResponse").mockReturnValue({
      groups: [
        { label: "Blue", keywords: ["blue shirt"] },
        { label: "Red", keywords: ["red dress"] },
      ],
    });

    const result = await groupKeywords(keywords, config, mockContext);

    expect(result.groups[0].metadata.basis).toBe("attribute");
    expect(result.groups[0].metadata.attributeName).toBe("Color");
    expect(result.groups[0].metadata.aiGenerated).toBe(true);
  });
});
