// Retry-policy tests for the OpenAI HTTP client used by ngram-2.
// Lives here (not next to openai.ts) because src/lib/composer/** is excluded
// from the test run while composer itself is deprecated. ngram-2 is the live
// consumer, so the contract worth testing is the one ngram-2 depends on.

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

// `openai.ts` imports "server-only" which throws under the vitest node
// environment. We're explicitly testing server-side retry behavior here, so
// stub the guard out.
vi.mock("server-only", () => ({}));

import { createChatCompletion } from "@/lib/composer/ai/openai";

const ORIGINAL_FETCH = globalThis.fetch;
const ORIGINAL_API_KEY = process.env.OPENAI_API_KEY;
const ORIGINAL_PRIMARY = process.env.OPENAI_MODEL_PRIMARY;
const ORIGINAL_FALLBACK = process.env.OPENAI_MODEL_FALLBACK;

const buildOkResponse = (overrides?: Partial<{ content: string; model: string }>): Response => {
  const payload = {
    choices: [
      {
        finish_reason: "stop",
        message: { content: overrides?.content ?? "OK", tool_calls: undefined, refusal: null },
      },
    ],
    usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 },
    model: overrides?.model ?? "test-model",
  };
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
};

const buildStatusResponse = (status: number, body = "Service Unavailable"): Response =>
  new Response(body, { status, statusText: body });

describe("openai retry policy (consumed by ngram-2)", () => {
  beforeEach(() => {
    process.env.OPENAI_API_KEY = "test-key";
    process.env.OPENAI_MODEL_PRIMARY = "test-model";
    delete process.env.OPENAI_MODEL_FALLBACK;
    vi.useFakeTimers();
  });

  afterEach(() => {
    globalThis.fetch = ORIGINAL_FETCH;
    process.env.OPENAI_API_KEY = ORIGINAL_API_KEY;
    process.env.OPENAI_MODEL_PRIMARY = ORIGINAL_PRIMARY;
    process.env.OPENAI_MODEL_FALLBACK = ORIGINAL_FALLBACK;
    vi.useRealTimers();
  });

  const drain = async (): Promise<void> => {
    // Advance through any pending backoff sleeps so the retry chain resolves.
    await vi.advanceTimersByTimeAsync(10_000);
  };

  it("retries 503 (Envoy upstream-connect-error pattern) and succeeds", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(buildStatusResponse(503))
      .mockResolvedValueOnce(buildOkResponse({ content: "second-try OK" }));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const promise = createChatCompletion([{ role: "user", content: "hi" }]);
    await drain();
    const result = await promise;

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(result.content).toBe("second-try OK");
  });

  it("retries 429 honoring retry-after-ms header", async () => {
    const rateLimited = new Response("rate limited", {
      status: 429,
      headers: { "retry-after-ms": "500" },
    });
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(rateLimited)
      .mockResolvedValueOnce(buildOkResponse());
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const promise = createChatCompletion([{ role: "user", content: "hi" }]);
    await drain();
    const result = await promise;

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(result.content).toBe("OK");
  });

  it("does NOT retry 400 (permanent client error)", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(buildStatusResponse(400, "bad request"));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    await expect(createChatCompletion([{ role: "user", content: "hi" }])).rejects.toThrow(
      /OpenAI API error \(400\)/,
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("retries network errors (TypeError from undici)", async () => {
    const networkError = new TypeError("fetch failed");
    (networkError as unknown as { cause?: { code: string } }).cause = { code: "ECONNRESET" };
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockRejectedValueOnce(networkError)
      .mockResolvedValueOnce(buildOkResponse({ content: "recovered" }));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const promise = createChatCompletion([{ role: "user", content: "hi" }]);
    await drain();
    const result = await promise;

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(result.content).toBe("recovered");
  });

  it("exhausts retries on persistent 503 and surfaces the error", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(buildStatusResponse(503, "still down"));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    // Attach the rejection assertion before draining timers so the eventual
    // rejection is observed synchronously and doesn't surface as an unhandled
    // rejection under fake timers.
    const promise = createChatCompletion([{ role: "user", content: "hi" }]);
    const assertion = expect(promise).rejects.toThrow(/OpenAI API error \(503\)/);
    await drain();
    await assertion;

    // 3 total attempts: initial + 2 retries (MAX_TRANSIENT_RETRIES = 3).
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});
