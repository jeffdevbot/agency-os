import { describe, it, expect, beforeEach, vi } from "vitest";
import type { NextRequest } from "next/server";
import { POST } from "./route";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { createSupabaseClientMock, type SupabaseClientMock } from "@/lib/composer/testSupabaseClient";

vi.mock("@/lib/supabase/serverClient", () => ({
  createSupabaseRouteClient: vi.fn(),
}));

const mockParams = (params: Record<string, string | undefined>) => ({
  params: Promise.resolve(params),
});

const mockRequest = (body?: unknown) =>
  ({
    json: vi.fn().mockResolvedValue(body),
    url: "http://localhost",
  }) as unknown as NextRequest;

describe("scribe questions API", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(supabaseMock.supabase);
  });

  it("rejects unauthenticated", async () => {
    const validSkuId = "ea92d6ff-ba2a-4767-aa17-c6f97298e524";
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session: null } });
    const res = await POST(
      mockRequest({ question: "test question", skuId: validSkuId }),
      mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }),
    );
    expect(res.status).toBe(401);
  });

  it("rejects null or missing skuId", async () => {
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const res = await POST(
      mockRequest({ question: "test question" }),
      mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }),
    );
    const json = await res.json();
    expect(res.status).toBe(400);
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toBe("skuId is required");
  });

  it("creates a question with valid skuId", async () => {
    const validSkuId = "ea92d6ff-ba2a-4767-aa17-c6f97298e524";
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });
    const builder = supabaseMock.getBuilder("scribe_customer_questions");
    builder.__pushResponse({
      data: {
        id: "q-1",
        project_id: "proj-1",
        sku_id: validSkuId,
        question: "test question",
        source: null,
        created_at: "2025-11-25T00:00:00Z",
      },
      error: null,
    });

    const res = await POST(
      mockRequest({ question: "test question", skuId: validSkuId }),
      mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }),
    );
    const json = await res.json();
    expect(res.status).toBe(200);
    expect(json.question).toBe("test question");
    expect(json.skuId).toBe(validSkuId);
  });
});
