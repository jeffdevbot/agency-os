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

const getDefaultModel = (): string => {
  return process.env.OPENAI_MODEL_PRIMARY || "gpt-5.1-nano";
};

const getApiKey = (): string => {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error("OPENAI_API_KEY environment variable is not set");
  }
  return apiKey;
};

const callOpenAIHttp = async (
  messages: ChatMessage[],
  model: string,
  temperature: number,
  maxTokens?: number,
): Promise<ChatCompletionResult> => {
  const startTime = Date.now();
  const response = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getApiKey()}`,
    },
    body: JSON.stringify({
      model,
      messages,
      temperature,
      max_tokens: maxTokens,
    }),
  });

  const durationMs = Date.now() - startTime;

  if (!response.ok) {
    const errorBody = await response.text().catch(() => "");
    throw new Error(
      `OpenAI API error (${response.status}): ${errorBody || response.statusText}`,
    );
  }

  const data = (await response.json()) as {
    choices: Array<{ message?: { content?: string } }>;
    usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
    model: string;
  };

  const choice = data.choices?.[0];
  if (!choice?.message?.content) {
    throw new Error("No content in OpenAI response");
  }

  const tokensIn = data.usage?.prompt_tokens ?? 0;
  const tokensOut = data.usage?.completion_tokens ?? 0;
  const tokensTotal = data.usage?.total_tokens ?? tokensIn + tokensOut;

  return {
    content: choice.message.content,
    tokensIn,
    tokensOut,
    tokensTotal,
    model: data.model || model,
    durationMs,
  };
};

export const createChatCompletion = async (
  messages: ChatMessage[],
  options?: {
    model?: string;
    temperature?: number;
    maxTokens?: number;
  },
): Promise<ChatCompletionResult> => {
  const model = options?.model || getDefaultModel();
  try {
    return await callOpenAIHttp(messages, model, options?.temperature ?? 0.7, options?.maxTokens);
  } catch (error) {
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
