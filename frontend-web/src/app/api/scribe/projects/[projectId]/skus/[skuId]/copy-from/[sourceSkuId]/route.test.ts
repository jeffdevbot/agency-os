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

const mockRequest = () =>
  ({
    json: vi.fn().mockResolvedValue({}),
    url: "http://localhost",
  }) as unknown as NextRequest;

describe("scribe copy-from-sku API", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(supabaseMock.supabase);
  });

  it("rejects invalid UUIDs", async () => {
    const res = await POST(
      mockRequest(),
      mockParams({ projectId: "invalid", skuId: "invalid", sourceSkuId: "invalid" }),
    );
    expect(res.status).toBe(400);
    const json = await res.json();
    expect(json.error.code).toBe("validation_error");
  });

  it("rejects copying SKU to itself", async () => {
    const sameId = "ea92d6ff-ba2a-4767-aa17-c6f97298e524";
    const res = await POST(
      mockRequest(),
      mockParams({
        projectId: "123e4567-e89b-12d3-a456-426614174000",
        skuId: sameId,
        sourceSkuId: sameId,
      }),
    );
    expect(res.status).toBe(400);
    const json = await res.json();
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toBe("cannot copy SKU to itself");
  });

  it("rejects unauthenticated", async () => {
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session: null } });
    const res = await POST(
      mockRequest(),
      mockParams({
        projectId: "123e4567-e89b-12d3-a456-426614174000",
        skuId: "ea92d6ff-ba2a-4767-aa17-c6f97298e524",
        sourceSkuId: "fb92d6ff-ba2a-4767-aa17-c6f97298e525",
      }),
    );
    expect(res.status).toBe(401);
  });

  it("returns 404 if source SKU not found", async () => {
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });
    const builder = supabaseMock.getBuilder("scribe_skus");
    // First query for source SKU - returns nothing
    builder.__pushResponse({ data: null, error: { code: "PGRST116" } });

    const res = await POST(
      mockRequest(),
      mockParams({
        projectId: "123e4567-e89b-12d3-a456-426614174000",
        skuId: "ea92d6ff-ba2a-4767-aa17-c6f97298e524",
        sourceSkuId: "fb92d6ff-ba2a-4767-aa17-c6f97298e525",
      }),
    );
    expect(res.status).toBe(404);
    const json = await res.json();
    expect(json.error.code).toBe("not_found");
  });

  it("successfully copies data from source to target SKU", async () => {
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
    const sourceSkuId = "fb92d6ff-ba2a-4767-aa17-c6f97298e525";
    const targetSkuId = "ea92d6ff-ba2a-4767-aa17-c6f97298e524";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const skusBuilder = supabaseMock.getBuilder("scribe_skus");
    // Source SKU query
    skusBuilder.__pushResponse({
      data: {
        id: sourceSkuId,
        project_id: projectId,
        brand_tone: "professional",
        target_audience: "developers",
        words_to_avoid: ["bad", "ugly"],
        supplied_content: "some content",
      },
      error: null,
    });
    // Target SKU query
    skusBuilder.__pushResponse({
      data: {
        id: targetSkuId,
        project_id: projectId,
      },
      error: null,
    });
    // Update target SKU with scalar fields
    skusBuilder.__pushResponse({ data: null, error: null });

    // Delete and insert keywords
    const keywordsBuilder = supabaseMock.getBuilder("scribe_keywords");
    keywordsBuilder.__pushResponse({ data: null, error: null }); // delete
    keywordsBuilder.__pushResponse({
      data: [
        { keyword: "test1", source: "manual", priority: 1 },
        { keyword: "test2", source: "manual", priority: 2 },
      ],
      error: null,
    }); // select
    keywordsBuilder.__pushResponse({ data: null, error: null }); // insert

    // Delete and insert questions
    const questionsBuilder = supabaseMock.getBuilder("scribe_customer_questions");
    questionsBuilder.__pushResponse({ data: null, error: null }); // delete
    questionsBuilder.__pushResponse({
      data: [{ question: "q1", source: "manual" }],
      error: null,
    }); // select
    questionsBuilder.__pushResponse({ data: null, error: null }); // insert

    // Delete and insert variant values
    const variantValuesBuilder = supabaseMock.getBuilder("scribe_sku_variant_values");
    variantValuesBuilder.__pushResponse({ data: null, error: null }); // delete
    variantValuesBuilder.__pushResponse({
      data: [{ attribute_id: "attr-1", value: "value1" }],
      error: null,
    }); // select
    variantValuesBuilder.__pushResponse({ data: null, error: null }); // insert

    const res = await POST(
      mockRequest(),
      mockParams({
        projectId,
        skuId: targetSkuId,
        sourceSkuId,
      }),
    );

    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.ok).toBe(true);
  });
});
