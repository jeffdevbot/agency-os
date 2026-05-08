import "server-only";

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface ToolCall {
  id: string;
  type: "function";
  function: {
    name: string;
    arguments: string;
  };
}

export interface Tool {
  type: "function";
  function: {
    name: string;
    description: string;
    parameters: Record<string, unknown>;
  };
}

export interface ChatCompletionResult {
  content: string | null;
  toolCalls?: ToolCall[];
  refusal?: string | null;
  finishReason?: string | null;
  tokensIn: number;
  tokensOut: number;
  tokensTotal: number;
  model: string;
  durationMs: number;
}

export interface JsonSchemaResponseFormat {
  type: "json_schema";
  json_schema: {
    name: string;
    description?: string;
    strict?: boolean;
    schema: Record<string, unknown>;
  };
}

export interface JsonObjectResponseFormat {
  type: "json_object";
}

export type ResponseFormat = JsonSchemaResponseFormat | JsonObjectResponseFormat;

// Total attempts (1 initial + up to N-1 retries) for any transient OpenAI
// failure: 429 rate limits, transient 5xx (including the Envoy-style 503
// "upstream connect error" we've seen kill ngram-2 workbook runs), 408/425
// timing errors, and network/abort errors. 3 attempts × ~7s of total backoff
// is enough for a typical OpenAI edge blip without delaying the user
// noticeably on a real outage.
const MAX_TRANSIENT_RETRIES = 3;
const RETRYABLE_HTTP_STATUS = new Set([408, 425, 429, 500, 502, 503, 504]);
// Per-attempt wall-clock cap. OpenAI's structured-output calls for ngram-2
// usually return in 5-30s; 90s gives plenty of headroom while still
// converting a hung connection into a retryable timeout.
const DEFAULT_REQUEST_TIMEOUT_MS = 90_000;
const TRANSIENT_BACKOFF_BASE_MS = 1_000;
const TRANSIENT_BACKOFF_MAX_MS = 8_000;

const getDefaultModel = (): string => {
  const model = process.env.OPENAI_MODEL_PRIMARY || "gpt-5.1-nano";
  return model;
};

const usesMaxCompletionTokens = (model: string): boolean =>
  model.trim().toLowerCase().startsWith("gpt-5");

const supportsTemperature = (model: string): boolean =>
  !model.trim().toLowerCase().startsWith("gpt-5");

const getReasoningEffort = (model: string): string | null =>
  model.trim().toLowerCase().startsWith("gpt-5") ? "low" : null;

const getApiKey = (): string => {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error("OPENAI_API_KEY environment variable is not set");
  }
  return apiKey;
};

const sleep = async (durationMs: number): Promise<void> =>
  new Promise((resolve) => {
    setTimeout(resolve, durationMs);
  });

const exponentialBackoffMs = (attempt: number): number => {
  // attempt is 1-indexed: 1st retry = 1s + jitter, 2nd = 2s + jitter, ...
  const base = Math.min(
    TRANSIENT_BACKOFF_MAX_MS,
    TRANSIENT_BACKOFF_BASE_MS * 2 ** Math.max(0, attempt - 1),
  );
  // ±25% jitter to avoid thundering-herd retries when many parallel calls fail
  // on the same upstream blip.
  const jitter = base * 0.25 * (Math.random() * 2 - 1);
  return Math.max(250, Math.round(base + jitter));
};

const isRetryableNetworkError = (error: unknown): boolean => {
  if (error instanceof Error) {
    // Node's undici-backed fetch surfaces network resets / DNS / connect errors
    // as TypeErrors with names like "TypeError" / "FetchError", and aborts as
    // AbortError. All are safe to retry — the request never reached the model.
    if (error.name === "AbortError") return true;
    if (error.name === "TypeError") return true;
    if (error.name === "FetchError") return true;
    const cause = (error as { cause?: { code?: string } }).cause;
    if (cause?.code) {
      const code = cause.code;
      return (
        code === "ECONNRESET" ||
        code === "ECONNREFUSED" ||
        code === "ETIMEDOUT" ||
        code === "EPIPE" ||
        code === "EAI_AGAIN" ||
        code === "UND_ERR_SOCKET" ||
        code === "UND_ERR_CONNECT_TIMEOUT"
      );
    }
  }
  return false;
};

const parseRateLimitDelayMs = (response: Response, errorBody: string): number | null => {
  const retryAfterMs = Number.parseFloat(response.headers.get("retry-after-ms") || "");
  if (Number.isFinite(retryAfterMs) && retryAfterMs > 0) {
    return retryAfterMs;
  }

  const retryAfterSeconds = Number.parseFloat(response.headers.get("retry-after") || "");
  if (Number.isFinite(retryAfterSeconds) && retryAfterSeconds > 0) {
    return retryAfterSeconds * 1000;
  }

  const bodyMatch = errorBody.match(/Please try again in\s+([\d.]+)s/i);
  if (bodyMatch?.[1]) {
    const seconds = Number.parseFloat(bodyMatch[1]);
    if (Number.isFinite(seconds) && seconds > 0) {
      return seconds * 1000;
    }
  }

  return null;
};

const callOpenAIHttp = async (
  messages: ChatMessage[],
  model: string,
  temperature: number,
  maxTokens?: number,
  tools?: Tool[],
  responseFormat?: ResponseFormat,
  retryCount = 0,
): Promise<ChatCompletionResult> => {
  const startTime = Date.now();

  const requestBody: Record<string, unknown> = {
    model,
    messages,
  };

  if (supportsTemperature(model)) {
    requestBody.temperature = temperature;
  }

  const reasoningEffort = getReasoningEffort(model);
  if (reasoningEffort) {
    requestBody.reasoning_effort = reasoningEffort;
  }

  if (typeof maxTokens === "number") {
    requestBody[usesMaxCompletionTokens(model) ? "max_completion_tokens" : "max_tokens"] = maxTokens;
  }

  if (tools && tools.length > 0) {
    requestBody.tools = tools;
  }

  if (responseFormat) {
    requestBody.response_format = responseFormat;
  }

  const controller = new AbortController();
  const timeoutHandle = setTimeout(
    () => controller.abort(),
    DEFAULT_REQUEST_TIMEOUT_MS,
  );

  let response: Response;
  try {
    response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${getApiKey()}`,
      },
      body: JSON.stringify(requestBody),
      signal: controller.signal,
    });
  } catch (error) {
    if (isRetryableNetworkError(error) && retryCount < MAX_TRANSIENT_RETRIES - 1) {
      await sleep(exponentialBackoffMs(retryCount + 1));
      return callOpenAIHttp(
        messages,
        model,
        temperature,
        maxTokens,
        tools,
        responseFormat,
        retryCount + 1,
      );
    }
    throw error;
  } finally {
    clearTimeout(timeoutHandle);
  }

  const durationMs = Date.now() - startTime;

  if (!response.ok) {
    const errorBody = await response.text().catch(() => "");
    if (
      RETRYABLE_HTTP_STATUS.has(response.status) &&
      retryCount < MAX_TRANSIENT_RETRIES - 1
    ) {
      const rateLimitDelayMs =
        response.status === 429 ? parseRateLimitDelayMs(response, errorBody) : null;
      const retryDelayMs =
        rateLimitDelayMs != null
          ? Math.min(15000, Math.max(1000, Math.ceil(rateLimitDelayMs + 250)))
          : exponentialBackoffMs(retryCount + 1);
      await sleep(retryDelayMs);
      return callOpenAIHttp(
        messages,
        model,
        temperature,
        maxTokens,
        tools,
        responseFormat,
        retryCount + 1,
      );
    }
    throw new Error(
      `OpenAI API error (${response.status}): ${errorBody || response.statusText}`,
    );
  }

  const data = (await response.json()) as {
    choices: Array<{
      finish_reason?: string | null;
      message?: {
        content?: string | null;
        tool_calls?: ToolCall[];
        refusal?: string | null;
      }
    }>;
    usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
    model: string;
  };

  const choice = data.choices?.[0];
  if (!choice?.message) {
    throw new Error("No message in OpenAI response");
  }

  const tokensIn = data.usage?.prompt_tokens ?? 0;
  const tokensOut = data.usage?.completion_tokens ?? 0;
  const tokensTotal = data.usage?.total_tokens ?? tokensIn + tokensOut;

  return {
    content: choice.message.content ?? null,
    toolCalls: choice.message.tool_calls,
    refusal: choice.message.refusal ?? null,
    finishReason: choice.finish_reason ?? null,
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
    tools?: Tool[];
    responseFormat?: ResponseFormat;
  },
): Promise<ChatCompletionResult> => {
  const model = options?.model || getDefaultModel();
  try {
    return await callOpenAIHttp(
      messages,
      model,
      options?.temperature ?? 0.7,
      options?.maxTokens,
      options?.tools,
      options?.responseFormat,
    );
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
