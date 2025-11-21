import OpenAI from "openai";

export interface OpenAIConfig {
  apiKey: string;
  model: string;
  fallbackModel?: string;
}

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface ChatCompletionResult {
  content: string;
  tokensIn: number;
  tokensOut: number;
  tokensTotal: number;
  model: string;
  durationMs: number;
}

const getOpenAIClient = (): OpenAI => {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error("OPENAI_API_KEY environment variable is not set");
  }
  return new OpenAI({ apiKey });
};

const getDefaultModel = (): string => {
  return process.env.OPENAI_MODEL_PRIMARY || "gpt-5.1-nano";
};

export const createChatCompletion = async (
  messages: ChatMessage[],
  options?: {
    model?: string;
    temperature?: number;
    maxTokens?: number;
  },
): Promise<ChatCompletionResult> => {
  const client = getOpenAIClient();
  const model = options?.model || getDefaultModel();
  const startTime = Date.now();

  try {
    const completion = await client.chat.completions.create({
      model,
      messages,
      temperature: options?.temperature ?? 0.7,
      max_tokens: options?.maxTokens,
    });

    const durationMs = Date.now() - startTime;
    const choice = completion.choices[0];
    const usage = completion.usage;

    if (!choice?.message?.content) {
      throw new Error("No content in OpenAI response");
    }

    return {
      content: choice.message.content,
      tokensIn: usage?.prompt_tokens ?? 0,
      tokensOut: usage?.completion_tokens ?? 0,
      tokensTotal: usage?.total_tokens ?? 0,
      model: completion.model,
      durationMs,
    };
  } catch (error) {
    const durationMs = Date.now() - startTime;

    if (options?.model && options.model !== getDefaultModel()) {
      throw error;
    }

    const fallbackModel = process.env.OPENAI_MODEL_FALLBACK;
    if (fallbackModel && fallbackModel !== model) {
      console.warn(`OpenAI call failed with ${model}, retrying with ${fallbackModel}`);
      return createChatCompletion(messages, { ...options, model: fallbackModel });
    }

    throw error;
  }
};

export const parseJSONResponse = <T>(content: string): T => {
  const jsonMatch = content.match(/```json\n?([\s\S]*?)\n?```/);
  const jsonString = jsonMatch ? jsonMatch[1] : content;

  try {
    return JSON.parse(jsonString) as T;
  } catch (error) {
    throw new Error(`Failed to parse JSON from OpenAI response: ${error instanceof Error ? error.message : String(error)}`);
  }
};
