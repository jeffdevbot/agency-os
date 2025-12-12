import { createChatCompletion, parseJSONResponse, type ChatMessage } from "@/lib/composer/ai/openai";

const PROMPT_VERSION = "scribe_stage_c_v2";

interface ApprovedTopic {
  title: string;
  description: string;
}

interface FormatPreferences {
  bulletCapsHeaders?: boolean;
  descriptionParagraphs?: boolean;
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
  formatPreferences?: FormatPreferences;
}

// Helper: count words in a string
const countWords = (text: string): number => {
  return text.trim().split(/\s+/).filter(w => w.length > 0).length;
};

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

  // Format preferences
  const useCapsHeaders = data.formatPreferences?.bulletCapsHeaders ?? false;
  const useParagraphs = data.formatPreferences?.descriptionParagraphs ?? true;

  // Build bullet format instructions
  let bulletFormatInstructions = "";
  if (useCapsHeaders) {
    bulletFormatInstructions = `
BULLET FORMAT (MANDATORY):
Each bullet MUST begin with an ALL CAPS header (2-4 words) followed by a colon, then the description.
Example: "UNMATCHED QUALITY: Our premium aluminum photo frame features a 0.4 inch wide and 0.8 inch deep profile for a contemporary sleek look that complements any home decor style."
`;
  }

  // Build description format instructions
  let descriptionFormatInstructions = "";
  if (useParagraphs) {
    descriptionFormatInstructions = `
DESCRIPTION FORMAT:
Separate key topics with double line breaks (blank lines) for readability. Each paragraph should cover a distinct benefit or topic. Use 3-5 paragraphs.
`;
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
1. Title: 100-150 characters (target range); maximum 200 characters; no emojis/HTML; safe claims only.
2. Bullets: Exactly 5 bullets; each bullet must be 40-50 words (count carefully!); max 500 characters; no HTML/emojis; no medical/prohibited claims.
3. Description: 800-1500 characters (target range); maximum 2000 characters; safe claims only.
4. Backend Keywords: Maximum 249 bytes; no ASINs/competitor brands; avoid repeating title/bullets terms; no forbidden terms.
${bulletFormatInstructions}${descriptionFormatInstructions}
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

CRITICAL LENGTH REQUIREMENTS:
- Title: Aim for 100-150 characters
- Each bullet: MUST be 40-50 words. Count words carefully. This is non-negotiable.
- Description: Aim for 800-1500 characters
- bullets MUST be exactly 5 items
- Stay within all maximum limits
- Follow Amazon's content policies strictly`;
};

// Word count requirements for bullets
const MIN_BULLET_WORDS = 40;
const MAX_BULLET_WORDS = 50;
const MAX_RETRIES = 2;

// Build a retry prompt for bullets that don't meet word count
const buildRetryPrompt = (
  originalBullets: string[],
  bulletIssues: { index: number; wordCount: number; direction: "too_short" | "too_long" }[]
): string => {
  const issueDescriptions = bulletIssues.map(issue => {
    const bullet = originalBullets[issue.index];
    const action = issue.direction === "too_short"
      ? `expand to 40-50 words (currently ${issue.wordCount} words)`
      : `condense to 40-50 words (currently ${issue.wordCount} words)`;
    return `Bullet ${issue.index + 1}: "${bullet.substring(0, 80)}..." - ${action}`;
  }).join("\n");

  return `The following bullets do not meet the 40-50 word requirement. Please rewrite ONLY the bullets listed below, keeping the same format and topic but adjusting length.

ISSUES:
${issueDescriptions}

IMPORTANT:
- Keep the same ALL CAPS header format if present
- Maintain the same topic/benefit angle
- Each bullet MUST be exactly 40-50 words
- Return ONLY a JSON object with the format: {"bullets": ["bullet1", "bullet2", "bullet3", "bullet4", "bullet5"]}
- Include ALL 5 bullets in the response, even unchanged ones`;
};

// Validate bullets meet word count, returns issues if any
const validateBulletWordCount = (bullets: string[]): { index: number; wordCount: number; direction: "too_short" | "too_long" }[] => {
  const issues: { index: number; wordCount: number; direction: "too_short" | "too_long" }[] = [];

  for (let i = 0; i < bullets.length; i++) {
    const wordCount = countWords(bullets[i]);
    if (wordCount < MIN_BULLET_WORDS) {
      issues.push({ index: i, wordCount, direction: "too_short" });
    } else if (wordCount > MAX_BULLET_WORDS) {
      issues.push({ index: i, wordCount, direction: "too_long" });
    }
  }

  return issues;
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

  // Track total tokens across retries
  let totalTokensIn = result.tokensIn;
  let totalTokensOut = result.tokensOut;

  // Parse JSON response
  let parsedResponse = parseJSONResponse<CopyResponse>(result.content ?? "{}");

  // Validate response structure
  if (!parsedResponse.title || !parsedResponse.bullets || !parsedResponse.description || !parsedResponse.backend_keywords) {
    throw new Error("Invalid copy response: missing required fields");
  }

  if (!Array.isArray(parsedResponse.bullets) || parsedResponse.bullets.length !== 5) {
    throw new Error(`Invalid bullets: expected exactly 5, got ${parsedResponse.bullets?.length || 0}`);
  }

  // Validate and retry for word count if needed
  let bulletIssues = validateBulletWordCount(parsedResponse.bullets);
  let retryCount = 0;

  while (bulletIssues.length > 0 && retryCount < MAX_RETRIES) {
    retryCount++;
    console.log(`[Scribe] Bullet word count issues detected, retry ${retryCount}/${MAX_RETRIES}:`,
      bulletIssues.map(i => `Bullet ${i.index + 1}: ${i.wordCount} words (${i.direction})`));

    const retryPrompt = buildRetryPrompt(parsedResponse.bullets, bulletIssues);

    const retryResult = await createChatCompletion([
      { role: "user", content: prompt },
      { role: "assistant", content: result.content ?? "" },
      { role: "user", content: retryPrompt },
    ], {
      temperature: 0.5, // Lower temperature for more consistent output
      maxTokens: 2000,
    });

    totalTokensIn += retryResult.tokensIn;
    totalTokensOut += retryResult.tokensOut;

    try {
      const retryParsed = parseJSONResponse<{ bullets: string[] }>(retryResult.content ?? "{}");
      if (retryParsed.bullets && Array.isArray(retryParsed.bullets) && retryParsed.bullets.length === 5) {
        parsedResponse.bullets = retryParsed.bullets as [string, string, string, string, string];
        bulletIssues = validateBulletWordCount(parsedResponse.bullets);
      }
    } catch (e) {
      console.warn(`[Scribe] Failed to parse retry response:`, e);
      break;
    }
  }

  // Log final word counts for monitoring
  const finalWordCounts = parsedResponse.bullets.map((b, i) => `B${i + 1}: ${countWords(b)}`).join(", ");
  console.log(`[Scribe] Final bullet word counts: ${finalWordCounts}`);

  // Validate character limits (hard limits)
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
    tokensIn: totalTokensIn,
    tokensOut: totalTokensOut,
    tokensTotal: totalTokensIn + totalTokensOut,
    model: result.model,
    promptVersion: PROMPT_VERSION,
  };
};
