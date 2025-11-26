import { describe, it, expect, beforeEach, vi } from "vitest";
import type { NextRequest } from "next/server";
import { GET, POST } from "./route";
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

describe("scribe skus API", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(supabaseMock.supabase);
  });

  it("rejects unauthenticated", async () => {
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session: null } });
    const res = await GET({ url: "http://localhost" } as NextRequest, mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }));
    expect(res.status).toBe(401);
  });

  it("creates a SKU and returns it", async () => {
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });
    const builder = supabaseMock.getBuilder("scribe_skus");
    builder.__pushResponse({ data: null, error: null, count: 0 }); // count
    builder.__pushResponse({
      data: {
        id: "sku-1",
        project_id: "proj-1",
        sku_code: "SKU123",
        asin: "B00TEST",
        product_name: "Test",
        brand_tone_override: null,
        target_audience_override: null,
        words_to_avoid_override: [],
        supplied_content_override: null,
        sort_order: 1,
        created_at: "2025-11-25T00:00:00Z",
        updated_at: "2025-11-25T00:00:00Z",
      },
      error: null,
    });

    const res = await POST(
      mockRequest({ skuCode: "SKU123", asin: "B00TEST", productName: "Test" }),
      mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }),
    );
    const json = await res.json();
    expect(res.status).toBe(200);
    expect(json.skuCode).toBe("SKU123");
  });

  it("enforces 50 SKU limit", async () => {
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });
    const builder = supabaseMock.getBuilder("scribe_skus");
    builder.__pushResponse({ data: null, error: null, count: 50 }); // count response

    const res = await POST(
      mockRequest({ skuCode: "SKU123" }),
      mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }),
    );
    const json = await res.json();
    expect(res.status).toBe(400);
    expect(json.error.code).toBe("validation_error");
  });
});
