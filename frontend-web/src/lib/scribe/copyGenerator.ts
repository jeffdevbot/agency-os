import { createChatCompletion, parseJSONResponse, type ChatMessage } from "@/lib/composer/ai/openai";

const PROMPT_VERSION = "scribe_stage_c_v1";

interface ApprovedTopic {
  title: string;
  description: string;
}

interface SkuCopyData {
  skuCode: string;
  asin: string | null;
  productName: string | null;
  brandTone: string | null;
  targetAudience: string | null;
  wordsToAvoid: string[];
  suppliedContent: string | null;
  keywords: string[];
  questions: string[];
  variantAttributes: Record<string, string>;
  approvedTopics: ApprovedTopic[]; // Exactly 5 topics
  attributePreferences?: {
    mode?: "auto" | "overrides";
    rules?: Record<string, { sections: string[] }>;
  };
}

interface CopyResponse {
  title: string;
  bullets: [string, string, string, string, string];
  description: string;
  backend_keywords: string;
}

export interface GeneratedCopy {
  title: string;
  bullets: [string, string, string, string, string];
  description: string;
  backendKeywords: string;
  tokensIn: number;
  tokensOut: number;
  tokensTotal: number;
  model: string;
  promptVersion: string;
}

const buildPrompt = (data: SkuCopyData, locale: string): string => {
  // Format variant attributes
  const variantAttrsText =
    Object.entries(data.variantAttributes)
      .map(([key, value]) => `${key}=${value}`)
      .join(" | ") || "None";

  // Format approved topics with their descriptions
  const topicsText = data.approvedTopics
    .map((topic, i) => `${i + 1}. ${topic.title}\n   ${topic.description}`)
    .join("\n\n");

  // Format attribute usage preferences
  let attributeRulesText = "";
  if (data.attributePreferences?.mode === "overrides" && data.attributePreferences.rules) {
    const sectionNameMap: Record<string, string> = {
      title: "Title",
      bullets: "Bullets",
      description: "Description",
      backend_keywords: "Backend Keywords",
    };
    const rules = Object.entries(data.attributePreferences.rules)
      .map(([attr, rule]) => {
        const displaySections = rule.sections.map((s) => sectionNameMap[s] || s).join(", ");
        const attrValue = data.variantAttributes[attr];
        if (attrValue) {
          return `  ${attr}: MUST use value "${attrValue}" in ${displaySections}`;
        }
        return `  ${attr}: Use in ${displaySections}`;
      })
      .join("\n");
    attributeRulesText = `\nATTRIBUTE USAGE OVERRIDES (MANDATORY - do not deviate):\n${rules}\n\nIMPORTANT: Use ONLY the values provided above. Do NOT use color/size/attribute values from keywords, questions, or other sources.\n`;
  } else {
    attributeRulesText = `\nATTRIBUTE USAGE: Auto mode - use smart defaults (include key attributes naturally; avoid repetition/spam; combine where appropriate; don't repeat in every bullet).\n`;
  }

  return `You are an expert Amazon copywriter. Generate high-quality Amazon listing content for this SKU.

LANGUAGE: Generate all content in ${locale}. Use locale-specific spelling/phrasing/tone.
- Do NOT translate brand names (e.g., "Nike", "Patagonia") or trademarked terms
- Product Name provided is for context - you may rephrase it for clarity and consumer appeal
- Use measurements/units as supplied

INPUTS:
Product Name: ${data.productName || "N/A"}
SKU: ${data.skuCode}
ASIN: ${data.asin || "N/A"}
Brand Tone: ${data.brandTone || "N/A"}
Target Audience: ${data.targetAudience || "N/A"}
Variant Attributes: ${variantAttrsText}
Supplied Content: ${data.suppliedContent || "N/A"}
Keywords (max 10): ${data.keywords.join(", ") || "None"}
Customer Questions: ${data.questions.join(" | ") || "None"}
Words to Avoid: ${data.wordsToAvoid.join(", ") || "None"}

APPROVED TOPICS (use these as the foundation):
${topicsText}
${attributeRulesText}

AMAZON POLICY CONSTRAINTS (CRITICAL - strictly enforce):
1. Title: Maximum 200 characters; no ALL CAPS; no emojis/HTML; safe claims only.
2. Bullets: Exactly 5 bullets; each max 500 characters; no HTML/emojis; no medical/prohibited claims; avoid attribute spam.
3. Description: Maximum 2000 characters; plain text only; safe claims only.
4. Backend Keywords: Maximum 249 bytes; no ASINs/competitor brands; avoid repeating title/bullets terms; no forbidden terms.

CONTENT RULES:
1. Ground all copy on the 5 approved topics - address the concerns and angles they represent.
2. Incorporate keywords naturally (never forced or stuffed).
3. Respect brand tone and target audience throughout.
4. Use variant attributes appropriately (per attribute rules above).
5. Avoid all terms in Words to Avoid list.
6. NEVER include SKU codes, ASINs, or internal identifiers in any content.
7. Be specific, benefit-focused, and address customer questions where relevant.
8. No generic fluff or feature lists - every sentence must add value.

OUTPUT FORMAT (valid JSON only):
{
  "title": "...",
  "bullets": ["bullet 1", "bullet 2", "bullet 3", "bullet 4", "bullet 5"],
  "description": "...",
  "backend_keywords": "..."
}

IMPORTANT:
- bullets MUST be exactly 5 items
- Stay within all character/byte limits
- Follow Amazon's content policies strictly`;
};

export const generateCopyForSku = async (data: SkuCopyData, locale: string): Promise<GeneratedCopy> => {
  // Validate inputs
  if (data.approvedTopics.length !== 5) {
    throw new Error("Exactly 5 approved topics are required for copy generation");
  }

  const prompt = buildPrompt(data, locale);

  const messages: ChatMessage[] = [
    {
      role: "user",
      content: prompt,
    },
  ];

  const result = await createChatCompletion(messages, {
    temperature: 0.7,
    maxTokens: 3000,
  });

  // Parse JSON response
  const parsedResponse = parseJSONResponse<CopyResponse>(result.content ?? "{}");

  // Validate response structure
  if (!parsedResponse.title || !parsedResponse.bullets || !parsedResponse.description || !parsedResponse.backend_keywords) {
    throw new Error("Invalid copy response: missing required fields");
  }

  if (!Array.isArray(parsedResponse.bullets) || parsedResponse.bullets.length !== 5) {
    throw new Error(`Invalid bullets: expected exactly 5, got ${parsedResponse.bullets?.length || 0}`);
  }

  // Validate character limits
  if (parsedResponse.title.length > 200) {
    throw new Error(`Title exceeds 200 characters (${parsedResponse.title.length} chars)`);
  }

  for (let i = 0; i < parsedResponse.bullets.length; i++) {
    if (parsedResponse.bullets[i].length > 500) {
      throw new Error(`Bullet ${i + 1} exceeds 500 characters (${parsedResponse.bullets[i].length} chars)`);
    }
  }

  if (parsedResponse.description.length > 2000) {
    throw new Error(`Description exceeds 2000 characters (${parsedResponse.description.length} chars)`);
  }

  const backendKeywordBytes = new TextEncoder().encode(parsedResponse.backend_keywords).length;
  if (backendKeywordBytes > 249) {
    throw new Error(`Backend keywords exceed 249 bytes (${backendKeywordBytes} bytes)`);
  }

  return {
    title: parsedResponse.title.trim(),
    bullets: parsedResponse.bullets as [string, string, string, string, string],
    description: parsedResponse.description.trim(),
    backendKeywords: parsedResponse.backend_keywords.trim(),
    tokensIn: result.tokensIn,
    tokensOut: result.tokensOut,
    tokensTotal: result.tokensTotal,
    model: result.model,
    promptVersion: PROMPT_VERSION,
  };
};
