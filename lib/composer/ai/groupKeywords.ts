import type {
  GroupingConfig,
  ComposerProject,
  ComposerKeywordGroup,
} from "@agency/lib/composer/types";
import { createChatCompletion, parseJSONResponse, type ChatCompletionResult } from "./openai";

export interface GroupKeywordsContext {
  project: {
    clientName?: string | null;
    category?: string | null;
  };
  poolType: "body" | "titles";
  poolId: string;
}

interface AIGroupResponse {
  groups: Array<{
    label: string;
    keywords: string[];
  }>;
}

const buildGroupingPrompt = (
  keywords: string[],
  config: GroupingConfig,
  context: GroupKeywordsContext,
): string => {
  const { basis, attributeName, groupCount, phrasesPerGroup } = config;
  const { project, poolType } = context;

  let instruction = "";

  switch (basis) {
    case "single":
      instruction = "Group all keywords into a single group labeled 'General'.";
      break;

    case "per_sku":
      instruction = "Create one group per SKU variation. Use SKU attributes or identifiers to label each group.";
      break;

    case "attribute":
      if (!attributeName) {
        throw new Error("attributeName is required when basis is 'attribute'");
      }
      instruction = `Group keywords by the attribute: ${attributeName}. Create a separate group for each distinct value of ${attributeName}.`;
      break;

    case "custom":
      if (!groupCount) {
        throw new Error("groupCount is required when basis is 'custom'");
      }
      instruction = `Create exactly ${groupCount} logical groups based on semantic similarity and search intent.`;
      break;

    default:
      instruction = "Create logical groups based on semantic similarity and search intent.";
  }

  const targetPhrasesHint = phrasesPerGroup
    ? `\nTry to distribute keywords so each group has approximately ${phrasesPerGroup} phrases.`
    : "";

  const productContext = project.clientName
    ? `\nProduct context: ${project.clientName}${project.category ? ` in category ${project.category}` : ""}`
    : "";

  return `You are a keyword grouping assistant for Amazon listing optimization.

Task: Group the following keywords into logical, semantic groups for ${poolType === "body" ? "product description and bullet points" : "product titles"}.

${instruction}${targetPhrasesHint}${productContext}

Keywords to group:
${keywords.map((kw, i) => `${i + 1}. ${kw}`).join("\n")}

Requirements:
- Every keyword must be assigned to exactly one group
- Group labels should be concise and descriptive
- Return valid JSON only, no markdown formatting
- Use this exact structure:
{
  "groups": [
    {
      "label": "Group Name",
      "keywords": ["keyword1", "keyword2"]
    }
  ]
}`;
};

export interface GroupKeywordsResult {
  groups: ComposerKeywordGroup[];
  usage: Pick<ChatCompletionResult, "tokensIn" | "tokensOut" | "tokensTotal" | "model" | "durationMs">;
}

export const groupKeywords = async (
  keywords: string[],
  config: GroupingConfig,
  context: GroupKeywordsContext,
): Promise<GroupKeywordsResult> => {
  if (keywords.length === 0) {
    return {
      groups: [],
      usage: {
        tokensIn: 0,
        tokensOut: 0,
        tokensTotal: 0,
        model: "gpt-5.1-nano",
        durationMs: 0,
      },
    };
  }

  if (config.basis === "single" || keywords.length === 1) {
    return {
      groups: [
        {
          id: crypto.randomUUID(),
          organizationId: "",
          keywordPoolId: context.poolId,
          groupIndex: 0,
          label: "General",
          phrases: keywords,
          metadata: { basis: config.basis || "single" },
          createdAt: new Date().toISOString(),
        },
      ],
      usage: {
        tokensIn: 0,
        tokensOut: 0,
        tokensTotal: 0,
        model: "gpt-5.1-nano",
        durationMs: 0,
      },
    };
  }

  let usage: GroupKeywordsResult["usage"] = {
    tokensIn: 0,
    tokensOut: 0,
    tokensTotal: 0,
    model: process.env.OPENAI_MODEL_PRIMARY || "gpt-5.1-nano",
    durationMs: 0,
  };

  try {
    const prompt = buildGroupingPrompt(keywords, config, context);
    const result = await createChatCompletion(
      [
        {
          role: "system",
          content: "You are a keyword grouping assistant. Return valid JSON only.",
        },
        {
          role: "user",
          content: prompt,
        },
      ],
      {
        temperature: 0.3,
        maxTokens: 4000,
      },
    );
    usage = {
      tokensIn: result.tokensIn,
      tokensOut: result.tokensOut,
      tokensTotal: result.tokensTotal,
      model: result.model,
      durationMs: result.durationMs,
    };

    const aiResponse = parseJSONResponse<AIGroupResponse>(result.content);

    if (!aiResponse.groups || !Array.isArray(aiResponse.groups)) {
      throw new Error("Invalid AI response: missing 'groups' array");
    }

    const assignedKeywords = new Set<string>();
    aiResponse.groups.forEach((group) => {
      group.keywords.forEach((kw) => assignedKeywords.add(kw.toLowerCase()));
    });

    const missingKeywords = keywords.filter(
      (kw) => !assignedKeywords.has(kw.toLowerCase()),
    );

    if (missingKeywords.length > 0) {
      if (aiResponse.groups.length === 0) {
        aiResponse.groups.push({
          label: "General",
          keywords: missingKeywords,
        });
      } else {
        aiResponse.groups[aiResponse.groups.length - 1].keywords.push(
          ...missingKeywords,
        );
      }
    }

    return {
      groups: aiResponse.groups.map((group, index) => ({
        id: crypto.randomUUID(),
        organizationId: "",
        keywordPoolId: context.poolId,
        groupIndex: index,
        label: group.label,
        phrases: group.keywords,
        metadata: {
          basis: config.basis,
          attributeName: config.attributeName,
          aiGenerated: true,
        },
        createdAt: new Date().toISOString(),
      })),
      usage,
    };
  } catch (error) {
    console.error("AI grouping failed, falling back to single group:", error);
    return {
      groups: [
        {
          id: crypto.randomUUID(),
          organizationId: "",
          keywordPoolId: context.poolId,
          groupIndex: 0,
          label: "General",
          phrases: keywords,
          metadata: { basis: "single", fallback: true },
          createdAt: new Date().toISOString(),
        },
      ],
      usage: {
        ...usage,
        tokensIn: 0,
        tokensOut: 0,
        tokensTotal: 0,
      },
    };
  }
};
