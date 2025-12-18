import { describe, it, expect, vi, beforeEach } from "vitest";
import * as openaiModule from "@/lib/composer/ai/openai";
import { generateCopyForSku, getFeaturePhraseLengthTargets } from "@/lib/scribe/copyGenerator";

const makeBullet = (header: string): string => {
  const words = Array.from({ length: 44 }, (_, i) => `w${i + 1}`).join(" ");
  return `${header}: ${words}`;
};

const baseSkuData = () => ({
  skuCode: "SKU-1",
  asin: "B000000000",
  productName: "Test Product",
  brandTone: "Friendly",
  targetAudience: "Everyone",
  wordsToAvoid: [],
  suppliedContent: null,
  keywords: ["keyword1", "keyword2"],
  questions: ["question1"],
  variantAttributes: { Color: "Black", Size: "Large" },
  approvedTopics: [
    { title: "Topic 1", description: "Desc 1" },
    { title: "Topic 2", description: "Desc 2" },
    { title: "Topic 3", description: "Desc 3" },
    { title: "Topic 4", description: "Desc 4" },
    { title: "Topic 5", description: "Desc 5" },
  ],
});

describe("copyGenerator", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("computes sane feature phrase targets", () => {
    const targets = getFeaturePhraseLengthTargets(144);
    expect(targets.minChars).toBeGreaterThan(0);
    expect(targets.targetMinChars).toBeGreaterThanOrEqual(targets.minChars);
    expect(targets.targetMaxChars).toBeGreaterThanOrEqual(targets.targetMinChars);
    expect(targets.targetMaxChars).toBeLessThanOrEqual(144);
  });

  it("retries when feature phrase is too short", async () => {
    const featurePhraseMaxChars = 144;
    const targets = getFeaturePhraseLengthTargets(featurePhraseMaxChars);

    const bullets = [
      makeBullet("ONE"),
      makeBullet("TWO"),
      makeBullet("THREE"),
      makeBullet("FOUR"),
      makeBullet("FIVE"),
    ] as [string, string, string, string, string];

    const createSpy = vi
      .spyOn(openaiModule, "createChatCompletion")
      .mockResolvedValueOnce({
        content: JSON.stringify({
          feature_phrase: "Short phrase",
          bullets,
          description: "Test description",
          backend_keywords: "kw1 kw2 kw3",
        }),
        tokensIn: 10,
        tokensOut: 10,
        tokensTotal: 20,
        model: "gpt-test",
        durationMs: 1,
      })
      .mockResolvedValueOnce({
        content: JSON.stringify({
          feature_phrase:
            "Durable everyday comfort with hidden storage and stylish modern look for living rooms bedrooms nurseries and small spaces",
        }),
        tokensIn: 10,
        tokensOut: 10,
        tokensTotal: 20,
        model: "gpt-test",
        durationMs: 1,
      });

    const result = await generateCopyForSku(baseSkuData(), "en-US", {
      titleMode: "feature_phrase",
      featurePhraseMaxChars,
      fixedTitleBase: "Brand - Product Name - Size",
      titleSeparator: " - ",
    });

    expect(createSpy).toHaveBeenCalledTimes(2);
    expect(result.featurePhrase).toBeTruthy();
    expect(result.featurePhrase!.length).toBeLessThanOrEqual(featurePhraseMaxChars);
    expect(result.featurePhrase!.length).toBeGreaterThanOrEqual(targets.minChars);
  });
});

