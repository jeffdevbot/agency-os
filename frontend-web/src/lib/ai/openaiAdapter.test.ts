import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

import { createChatCompletion } from "@/lib/composer/ai/openai";

const originalFetch = global.fetch;

describe("openai adapter", () => {
  beforeEach(() => {
    process.env.OPENAI_API_KEY = "test-key";
  });

  afterEach(() => {
    vi.restoreAllMocks();
    global.fetch = originalFetch;
    delete process.env.OPENAI_MODEL_PRIMARY;
    delete process.env.OPENAI_MODEL_FALLBACK;
    process.env.OPENAI_API_KEY = "test-key";
  });

  it("uses GPT-5 request fields when the primary model is GPT-5", async () => {
    process.env.OPENAI_MODEL_PRIMARY = "gpt-5-mini";

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        choices: [{ message: { content: "{\"ok\":true}" } }],
        usage: { prompt_tokens: 11, completion_tokens: 7, total_tokens: 18 },
        model: "gpt-5-mini-2026-01-01",
      }),
    });
    global.fetch = fetchMock as typeof fetch;

    const result = await createChatCompletion([{ role: "user", content: "hello" }], {
      temperature: 0.1,
      maxTokens: 2200,
    });

    expect(result.model).toBe("gpt-5-mini-2026-01-01");
    expect(fetchMock).toHaveBeenCalledTimes(1);

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(String(init.body));

    expect(body.model).toBe("gpt-5-mini");
    expect(body.reasoning_effort).toBe("low");
    expect(body.max_completion_tokens).toBe(2200);
    expect(body.temperature).toBeUndefined();
    expect(body.max_tokens).toBeUndefined();
  });

  it("uses legacy chat fields for non-GPT-5 models", async () => {
    process.env.OPENAI_MODEL_PRIMARY = "gpt-4o";

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        choices: [{ message: { content: "ok" } }],
        usage: { prompt_tokens: 5, completion_tokens: 3, total_tokens: 8 },
        model: "gpt-4o",
      }),
    });
    global.fetch = fetchMock as typeof fetch;

    await createChatCompletion([{ role: "user", content: "hello" }], {
      temperature: 0.3,
      maxTokens: 120,
    });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(String(init.body));

    expect(body.model).toBe("gpt-4o");
    expect(body.temperature).toBe(0.3);
    expect(body.max_tokens).toBe(120);
    expect(body.max_completion_tokens).toBeUndefined();
    expect(body.reasoning_effort).toBeUndefined();
  });

  it("passes structured response_format through to OpenAI", async () => {
    process.env.OPENAI_MODEL_PRIMARY = "gpt-5.4";

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        choices: [{ message: { content: "{\"ok\":true}" } }],
        usage: { prompt_tokens: 5, completion_tokens: 3, total_tokens: 8 },
        model: "gpt-5.4-2026-03-05",
      }),
    });
    global.fetch = fetchMock as typeof fetch;

    await createChatCompletion([{ role: "user", content: "hello" }], {
      maxTokens: 120,
      responseFormat: {
        type: "json_schema",
        json_schema: {
          name: "test_schema",
          strict: true,
          schema: {
            type: "object",
            additionalProperties: false,
            properties: {
              ok: { type: "boolean" },
            },
            required: ["ok"],
          },
        },
      },
    });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(String(init.body));

    expect(body.response_format).toEqual({
      type: "json_schema",
      json_schema: {
        name: "test_schema",
        strict: true,
        schema: {
          type: "object",
          additionalProperties: false,
          properties: {
            ok: { type: "boolean" },
          },
          required: ["ok"],
        },
      },
    });
  });
});
