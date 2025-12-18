import { createChatCompletion, parseJSONResponse, type ChatMessage } from "@/lib/composer/ai/openai";
import { enforceMaxLenAtWordBoundary, type TitleSeparator } from "@/lib/scribe/titleBlueprint";

const PROMPT_VERSION = "scribe_stage_c_v4_title_blueprint_fill_budget";

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

type AttributeSection = "title" | "bullets" | "description" | "backend_keywords";

export type TitleGenerationMode = "full" | "feature_phrase" | "none";

export interface GenerateCopyOptions {
  titleMode?: TitleGenerationMode;
  featurePhraseMaxChars?: number;
  fixedTitleBase?: string;
  titleSeparator?: TitleSeparator;
}

type NormalizedGenerateCopyOptions = {
  titleMode: TitleGenerationMode;
  featurePhraseMaxChars: number;
  fixedTitleBase?: string;
  titleSeparator: TitleSeparator;
};

export const getFeaturePhraseLengthTargets = (
  maxChars: number,
): { minChars: number; targetMinChars: number; targetMaxChars: number } => {
  const max = Math.max(0, Math.floor(maxChars));
  if (max === 0) {
    return { minChars: 0, targetMinChars: 0, targetMaxChars: 0 };
  }

  const targetMinChars = Math.min(max, Math.max(0, Math.floor(max * 0.85)));
  const targetMaxChars = Math.min(max, Math.max(targetMinChars, Math.floor(max * 0.95)));
  const minChars = Math.min(targetMinChars, Math.max(0, Math.floor(max * 0.7)));

  return { minChars, targetMinChars, targetMaxChars };
};

// Helper: count words in a string
const countWords = (text: string): number => {
  return text.trim().split(/\s+/).filter((w) => w.length > 0).length;
};

interface CopyResponseFull {
  title: string;
  bullets: [string, string, string, string, string];
  description: string;
  backend_keywords: string;
}

interface CopyResponseWithFeaturePhrase {
  feature_phrase: string;
  bullets: [string, string, string, string, string];
  description: string;
  backend_keywords: string;
}

interface CopyResponseNoTitle {
  bullets: [string, string, string, string, string];
  description: string;
  backend_keywords: string;
}

export interface GeneratedCopy {
  title?: string;
  featurePhrase?: string;
  bullets: [string, string, string, string, string];
  description: string;
  backendKeywords: string;
  tokensIn: number;
  tokensOut: number;
  tokensTotal: number;
  model: string;
  promptVersion: string;
}

const buildPrompt = (data: SkuCopyData, locale: string, options: NormalizedGenerateCopyOptions): string => {
  const variantAttrsText =
    Object.entries(data.variantAttributes)
      .map(([key, value]) => `${key}=${value}`)
      .join(" | ") || "None";

  const topicsText = data.approvedTopics
    .map((topic, i) => `${i + 1}. ${topic.title}\n   ${topic.description}`)
    .join("\n\n");

  // Attribute usage preferences: ignore "title" overrides when title is deterministic
  let attributeRulesText = "";
  if (data.attributePreferences?.mode === "overrides" && data.attributePreferences.rules) {
    const sectionNameMap: Record<string, string> = {
      ...(options.titleMode === "full" ? { title: "Title" } : {}),
      bullets: "Bullets",
      description: "Description",
      backend_keywords: "Backend Keywords",
    };

    const rules = Object.entries(data.attributePreferences.rules)
      .map(([attr, rule]) => {
        const filteredSections = (rule.sections ?? []).filter((s): s is AttributeSection => s in sectionNameMap);
        if (filteredSections.length === 0) return null;

        const displaySections = filteredSections.map((s) => sectionNameMap[s] || s).join(", ");
        const attrValue = data.variantAttributes[attr];
        if (attrValue) {
          return `  ${attr}: MUST use value "${attrValue}" in ${displaySections}`;
        }
        return `  ${attr}: Use in ${displaySections}`;
      })
      .filter((line): line is string => Boolean(line))
      .join("\n");

    attributeRulesText = `\nATTRIBUTE USAGE OVERRIDES (MANDATORY - do not deviate):\n${rules}\n\nIMPORTANT: Use ONLY the values provided above. Do NOT use color/size/attribute values from keywords, questions, or other sources.\n`;
  } else {
    attributeRulesText = `\nATTRIBUTE USAGE: Auto mode - use smart defaults (include key attributes naturally; avoid repetition/spam; combine where appropriate; don't repeat in every bullet).\n`;
  }

  const useCapsHeaders = data.formatPreferences?.bulletCapsHeaders ?? false;
  const useParagraphs = data.formatPreferences?.descriptionParagraphs ?? true;

  let bulletFormatInstructions = "";
  if (useCapsHeaders) {
    bulletFormatInstructions = `
BULLET FORMAT (MANDATORY):
Each bullet MUST begin with an ALL CAPS header (2-4 words) followed by a colon, then the description.
Example: "UNMATCHED QUALITY: Our premium aluminum photo frame features a 0.4 inch wide and 0.8 inch deep profile for a contemporary sleek look that complements any home decor style."
`;
  }

  let descriptionFormatInstructions = "";
  if (useParagraphs) {
    descriptionFormatInstructions = `
DESCRIPTION FORMAT:
Separate key topics with double line breaks (blank lines) for readability. Each paragraph should cover a distinct benefit or topic. Use 3-5 paragraphs.
`;
  }

  const fixedTitleBase = options.fixedTitleBase?.trim() || "";
  const phraseTargets =
    options.titleMode === "feature_phrase" ? getFeaturePhraseLengthTargets(options.featurePhraseMaxChars) : null;

  const titleInstructions =
    options.titleMode === "full"
      ? `TITLE:
- Generate the full Amazon title. Aim for 100-150 characters (target range); maximum 200 characters; no emojis/HTML; safe claims only.`
      : options.titleMode === "feature_phrase"
        ? `TITLE (BLUEPRINT MODE):
- The title base is already determined by the project blueprint. Do NOT generate a full title.
- Write a single short FEATURE PHRASE to append to the existing title base.
- FEATURE PHRASE MUST be <= ${options.featurePhraseMaxChars} characters (including spaces).
- Aim for ${phraseTargets?.targetMinChars}-${phraseTargets?.targetMaxChars} characters; minimum ${phraseTargets?.minChars} characters (unless that is impossible).
- Use as much of the available space as possible while staying natural and readable.
- Include 2-4 concrete, high-signal benefits or differentiators (materials, build quality, compatibility, use cases, durability, comfort, safety, etc.).
- Do NOT include the exact project separator string "${options.titleSeparator}" anywhere in the phrase.
- Avoid using these separator characters: "-", "—", "|", ",".
- Do not start or end with punctuation.
${fixedTitleBase ? `- Existing title base (do not repeat it): ${fixedTitleBase}` : ""}`
        : `TITLE (BLUEPRINT MODE):
- The title is already fully determined by the project blueprint. Do NOT generate any title or feature phrase.
${fixedTitleBase ? `- Existing title base (for context): ${fixedTitleBase}` : ""}`;

  const outputSchema =
    options.titleMode === "full"
      ? `{
  "title": "...",
  "bullets": ["bullet 1", "bullet 2", "bullet 3", "bullet 4", "bullet 5"],
  "description": "...",
  "backend_keywords": "..."
}`
      : options.titleMode === "feature_phrase"
        ? `{
  "feature_phrase": "...",
  "bullets": ["bullet 1", "bullet 2", "bullet 3", "bullet 4", "bullet 5"],
  "description": "...",
  "backend_keywords": "..."
}`
        : `{
  "bullets": ["bullet 1", "bullet 2", "bullet 3", "bullet 4", "bullet 5"],
  "description": "...",
  "backend_keywords": "..."
}`;

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
1. Title: maximum 200 characters; no emojis/HTML; safe claims only.
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

${titleInstructions}

OUTPUT FORMAT (valid JSON only):
${outputSchema}

CRITICAL LENGTH REQUIREMENTS:
- Title: Maximum 200 characters
- Each bullet: MUST be 40-50 words. Count words carefully. This is non-negotiable.
- Description: Aim for 800-1500 characters
- bullets MUST be exactly 5 items
- Stay within all maximum limits
- Follow Amazon's content policies strictly`;
};

const MIN_BULLET_WORDS = 40;
const MAX_BULLET_WORDS = 50;
const MAX_RETRIES = 2;
const FEATURE_PHRASE_MAX_RETRIES = 1;

const buildRetryPrompt = (
  originalBullets: string[],
  bulletIssues: { index: number; wordCount: number; direction: "too_short" | "too_long" }[],
): string => {
  const issueDescriptions = bulletIssues
    .map((issue) => {
      const bullet = originalBullets[issue.index];
      const action =
        issue.direction === "too_short"
          ? `expand to 40-50 words (currently ${issue.wordCount} words)`
          : `condense to 40-50 words (currently ${issue.wordCount} words)`;
      return `Bullet ${issue.index + 1}: "${bullet.substring(0, 80)}..." - ${action}`;
    })
    .join("\n");

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

const buildFeaturePhraseRetryPrompt = (
  params: {
    maxChars: number;
    minChars: number;
    targetMinChars: number;
    targetMaxChars: number;
    titleSeparator: TitleSeparator;
    currentPhrase: string;
    direction: "too_short" | "too_long";
  },
): string => {
  const goal =
    params.direction === "too_long"
      ? `The feature phrase exceeds the character limit. Rewrite ONLY the feature phrase to fit the limit.`
      : `The feature phrase is too short. Rewrite ONLY the feature phrase to be more detailed.`;

  return `${goal}

CURRENT FEATURE PHRASE:
"${params.currentPhrase}"

RULES:
- Must be <= ${params.maxChars} characters (including spaces)
- Aim for ${params.targetMinChars}-${params.targetMaxChars} characters; minimum ${params.minChars} characters (unless impossible)
- Do NOT include the exact project separator string "${params.titleSeparator}"
- Avoid using these separator characters: "-", "—", "|", ","
- Do not start or end with punctuation
- Return ONLY valid JSON: {"feature_phrase": "..."}`;
};

const validateBulletWordCount = (
  bullets: string[],
): { index: number; wordCount: number; direction: "too_short" | "too_long" }[] => {
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

export const generateCopyForSku = async (
  data: SkuCopyData,
  locale: string,
  options?: GenerateCopyOptions,
): Promise<GeneratedCopy> => {
  if (data.approvedTopics.length !== 5) {
    throw new Error("Exactly 5 approved topics are required for copy generation");
  }

  const mergedOptions: NormalizedGenerateCopyOptions = {
    titleMode: options?.titleMode ?? "full",
    featurePhraseMaxChars: options?.featurePhraseMaxChars ?? 0,
    fixedTitleBase: options?.fixedTitleBase,
    titleSeparator: options?.titleSeparator ?? " - ",
  };

  if (mergedOptions.titleMode === "feature_phrase" && mergedOptions.featurePhraseMaxChars <= 0) {
    throw new Error("featurePhraseMaxChars must be provided when titleMode is feature_phrase");
  }

  const prompt = buildPrompt(data, locale, mergedOptions);

  const result = await createChatCompletion([{ role: "user", content: prompt }], {
    temperature: 0.7,
    maxTokens: 3000,
  });

  let totalTokensIn = result.tokensIn;
  let totalTokensOut = result.tokensOut;

  const parsedResponse = parseJSONResponse<Record<string, unknown>>(result.content ?? "{}");
  const bullets = (parsedResponse as { bullets?: unknown }).bullets;
  const description = (parsedResponse as { description?: unknown }).description;
  const backendKeywords = (parsedResponse as { backend_keywords?: unknown }).backend_keywords;

  if (!Array.isArray(bullets) || bullets.length !== 5 || !bullets.every((b) => typeof b === "string")) {
    throw new Error(`Invalid bullets: expected exactly 5, got ${Array.isArray(bullets) ? bullets.length : 0}`);
  }

  if (typeof description !== "string" || !description) {
    throw new Error("Invalid copy response: missing description");
  }

  if (typeof backendKeywords !== "string" || !backendKeywords) {
    throw new Error("Invalid copy response: missing backend_keywords");
  }

  let title: string | undefined;
  let featurePhrase: string | undefined;

  if (mergedOptions.titleMode === "full") {
    const maybeTitle = parsedResponse.title;
    if (typeof maybeTitle !== "string" || !maybeTitle.trim()) {
      throw new Error("Invalid copy response: missing title");
    }
    title = maybeTitle;
  } else if (mergedOptions.titleMode === "feature_phrase") {
    const maybePhrase = parsedResponse.feature_phrase;
    if (typeof maybePhrase !== "string" || !maybePhrase.trim()) {
      throw new Error("Invalid copy response: missing feature_phrase");
    }
    featurePhrase = maybePhrase;
  }

  // Validate and retry for word count if needed
  let currentBullets = bullets as string[];
  let bulletIssues = validateBulletWordCount(currentBullets);
  let retryCount = 0;

  while (bulletIssues.length > 0 && retryCount < MAX_RETRIES) {
    retryCount++;
    console.log(
      `[Scribe] Bullet word count issues detected, retry ${retryCount}/${MAX_RETRIES}:`,
      bulletIssues.map((i) => `Bullet ${i.index + 1}: ${i.wordCount} words (${i.direction})`),
    );

    const retryPrompt = buildRetryPrompt(currentBullets, bulletIssues);

    const retryResult = await createChatCompletion(
      [
        { role: "user", content: prompt },
        { role: "assistant", content: result.content ?? "" },
        { role: "user", content: retryPrompt },
      ],
      { temperature: 0.5, maxTokens: 2000 },
    );

    totalTokensIn += retryResult.tokensIn;
    totalTokensOut += retryResult.tokensOut;

    try {
      const retryParsed = parseJSONResponse<{ bullets: string[] }>(retryResult.content ?? "{}");
      if (Array.isArray(retryParsed.bullets) && retryParsed.bullets.length === 5) {
        currentBullets = retryParsed.bullets;
        bulletIssues = validateBulletWordCount(currentBullets);
      }
    } catch (e) {
      console.warn(`[Scribe] Failed to parse retry response:`, e);
      break;
    }
  }

  // Retry feature phrase length if needed
  if (mergedOptions.titleMode === "feature_phrase") {
    let phrase = featurePhrase ?? "";
    let phraseRetryCount = 0;
    const targets = getFeaturePhraseLengthTargets(mergedOptions.featurePhraseMaxChars);

    while (
      (phrase.length > mergedOptions.featurePhraseMaxChars || phrase.length < targets.minChars) &&
      phraseRetryCount < FEATURE_PHRASE_MAX_RETRIES
    ) {
      phraseRetryCount++;
      const direction = phrase.length > mergedOptions.featurePhraseMaxChars ? "too_long" : "too_short";
      console.log(
        `[Scribe] Feature phrase length issue (${phrase.length}/${mergedOptions.featurePhraseMaxChars}), retry ${phraseRetryCount}/${FEATURE_PHRASE_MAX_RETRIES} (${direction})`,
      );

      const retryPrompt = buildFeaturePhraseRetryPrompt({
        maxChars: mergedOptions.featurePhraseMaxChars,
        minChars: targets.minChars,
        targetMinChars: targets.targetMinChars,
        targetMaxChars: targets.targetMaxChars,
        titleSeparator: mergedOptions.titleSeparator,
        currentPhrase: phrase,
        direction,
      });

      const retryResult = await createChatCompletion(
        [
          { role: "user", content: prompt },
          { role: "assistant", content: result.content ?? "" },
          { role: "user", content: retryPrompt },
        ],
        { temperature: 0.4, maxTokens: 300 },
      );

      totalTokensIn += retryResult.tokensIn;
      totalTokensOut += retryResult.tokensOut;

      try {
        const retryParsed = parseJSONResponse<{ feature_phrase: string }>(retryResult.content ?? "{}");
        if (typeof retryParsed.feature_phrase === "string" && retryParsed.feature_phrase) {
          phrase = retryParsed.feature_phrase;
        }
      } catch (e) {
        console.warn(`[Scribe] Failed to parse feature phrase retry response:`, e);
        break;
      }
    }

    if (phrase.length > mergedOptions.featurePhraseMaxChars) {
      phrase = enforceMaxLenAtWordBoundary(phrase, mergedOptions.featurePhraseMaxChars);
    }

    featurePhrase = phrase.trim();
  }

  const finalWordCounts = currentBullets.map((b, i) => `B${i + 1}: ${countWords(b)}`).join(", ");
  console.log(`[Scribe] Final bullet word counts: ${finalWordCounts}`);

  // Hard limits
  if (mergedOptions.titleMode === "full" && typeof title === "string" && title.length > 200) {
    throw new Error(`Title exceeds 200 characters (${title.length} chars)`);
  }

  for (let i = 0; i < currentBullets.length; i++) {
    if (currentBullets[i].length > 500) {
      throw new Error(`Bullet ${i + 1} exceeds 500 characters (${currentBullets[i].length} chars)`);
    }
  }

  if (description.length > 2000) {
    throw new Error(`Description exceeds 2000 characters (${description.length} chars)`);
  }

  const backendKeywordBytes = new TextEncoder().encode(backendKeywords).length;
  if (backendKeywordBytes > 249) {
    throw new Error(`Backend keywords exceed 249 bytes (${backendKeywordBytes} bytes)`);
  }

  return {
    title: title?.trim(),
    featurePhrase: featurePhrase?.trim(),
    bullets: currentBullets as [string, string, string, string, string],
    description: description.trim(),
    backendKeywords: backendKeywords.trim(),
    tokensIn: totalTokensIn,
    tokensOut: totalTokensOut,
    tokensTotal: totalTokensIn + totalTokensOut,
    model: result.model,
    promptVersion: PROMPT_VERSION,
  };
};
