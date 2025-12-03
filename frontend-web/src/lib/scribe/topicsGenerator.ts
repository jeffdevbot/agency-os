import { createChatCompletion, parseJSONResponse, type ChatMessage } from "@/lib/composer/ai/openai";

const PROMPT_VERSION = "scribe_topics_v2";

interface SkuData {
  skuCode: string;
  asin: string | null;
  productName: string | null;
  brandTone: string | null;
  targetAudience: string | null;
  wordsToAvoid: string[];
  suppliedContent: string | null;
  keywords: string[];
  questions: string[];
  variantAttributes: Record<string, string>; // { "Color": "Black", "Size": "10L" }
}

interface TopicCandidate {
  title: string;
  description: string;
}

interface TopicsResponse {
  topics: TopicCandidate[];
}

export interface GeneratedTopic {
  topicIndex: number;
  title: string;
  description: string;
}

export interface TopicsGenerationResult {
  topics: GeneratedTopic[];
  tokensIn: number;
  tokensOut: number;
  tokensTotal: number;
  model: string;
  promptVersion: string;
}

const buildPrompt = (skuData: SkuData, locale: string): string => {
  // Format variant attributes: "Color=Black | Capacity=10L"
  const variantAttrsText =
    Object.entries(skuData.variantAttributes)
      .map(([key, value]) => `${key}=${value}`)
      .join(" | ") || "None";

  return `You are an Amazon listing strategist. Generate exactly 7-8 distinct, short, high-intent topic angles for this SKU. These will be shown to the user, who will select the best 5 for Stage C copy generation.

LANGUAGE: Generate all output in ${locale}. Use locale-specific spelling/phrasing. Do NOT translate product/brand names or keywords; keep those as provided. Use measurements/units as supplied.

RULES:
1) CUSTOMER QUESTIONS are the #1 source. Prioritize them above everything else. If no questions, use supplied_content, keywords, brand tone, target audience, and variant attributes.
2) Internally group similar questions into 3–6 themes before ideation (not shown in output).
3) For each theme, propose strong topic angles that:
   - Directly address the underlying concerns in the questions.
   - Incorporate KEYWORDS naturally, never forced.
   - Respect BRAND TONE and TARGET AUDIENCE.
   - Use PRODUCT NAME, VARIANT ATTRIBUTES, and SUPPLIED CONTENT for nuance.
4) Avoid all terms listed in WORDS_TO_AVOID.
5) No safety risks, no prohibited claims.
6) Each topic must have:
   - a short "angle-style" TITLE (max ~8 words)
   - exactly three bullet sentences explaining why that angle matters; prefix each bullet with "• " and separate bullets with newlines
7) No duplicates. No fluff. No generic feature lists.

INPUTS:
Product Name: ${skuData.productName || "N/A"}
SKU: ${skuData.skuCode}
ASIN: ${skuData.asin || "N/A"}
Brand Tone: ${skuData.brandTone || "N/A"}
Target Audience: ${skuData.targetAudience || "N/A"}
Variant Attributes: ${variantAttrsText}
Supplied Content: ${skuData.suppliedContent || "N/A"}
Keywords: ${skuData.keywords.join(", ") || "None"}
Customer Questions: ${skuData.questions.join(" | ") || "None"}
Words to Avoid: ${skuData.wordsToAvoid.join(", ") || "None"}

OUTPUT (valid JSON only):
{
  "topics": [
    { "title": "...", "description": "• ...\\n• ...\\n• ..." }
  ]
}`;
};

export const generateTopicsForSku = async (skuData: SkuData, locale: string): Promise<TopicsGenerationResult> => {
  const prompt = buildPrompt(skuData, locale);

  const messages: ChatMessage[] = [
    {
      role: "user",
      content: prompt,
    },
  ];

  const result = await createChatCompletion(messages, {
    temperature: 0.7,
    maxTokens: 2000,
  });

  // Parse JSON response
  const parsedResponse = parseJSONResponse<TopicsResponse>(result.content);

  if (!parsedResponse.topics || !Array.isArray(parsedResponse.topics)) {
    throw new Error("Invalid topics response: missing topics array");
  }

  // Validate and limit to 8 topics
  const topics = parsedResponse.topics.slice(0, 8).map((topic, index) => ({
    topicIndex: index + 1,
    title: topic.title?.trim() || `Topic ${index + 1}`,
    description: topic.description?.trim() || "",
  }));

  if (topics.length === 0) {
    throw new Error("No topics generated");
  }

  if (topics.length < 7) {
    throw new Error(`Expected 7-8 topics, but only ${topics.length} were generated`);
  }

  return {
    topics,
    tokensIn: result.tokensIn,
    tokensOut: result.tokensOut,
    tokensTotal: result.tokensTotal,
    model: result.model,
    promptVersion: PROMPT_VERSION,
  };
};
