import { describe, it, expect, beforeEach, vi } from "vitest";
import type { NextRequest } from "next/server";
import { PATCH } from "./route";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { createSupabaseClientMock, type SupabaseClientMock } from "@/lib/composer/testSupabaseClient";

vi.mock("@/lib/supabase/serverClient", () => ({
  createSupabaseRouteClient: vi.fn(),
}));

const mockParams = (params: Record<string, string | undefined>) => ({
  params: Promise.resolve(params),
});

const mockRequest = (body: unknown) =>
  ({
    json: vi.fn().mockResolvedValue(body),
    url: "http://localhost",
  }) as unknown as NextRequest;

/**
 * SKU PATCH Tests - Attribute Preferences Validation
 *
 * Purpose: Verify that attribute_preferences field is properly validated when updating SKUs
 *
 * Test Coverage:
 * - Accept valid attribute preferences with auto mode
 * - Accept valid attribute preferences with overrides mode and rules
 * - Reject invalid mode values
 * - Reject invalid sections in rules
 * - Reject malformed rules structure
 * - Accept null/undefined attribute preferences (default to auto)
 */
describe("PATCH /projects/:id/skus/:id (attribute_preferences validation)", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(supabaseMock.supabase);
  });

  it("accepts valid attribute preferences with auto mode", async () => {
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "456e4567-e89b-12d3-a456-426614174000";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const skus = supabaseMock.getBuilder("scribe_skus");
    skus.__pushResponse({
      data: {
        id: skuId,
        project_id: projectId,
        sku_code: "SKU001",
        asin: "B001",
        product_name: "Product 1",
        brand_tone: "Professional",
        target_audience: "Adults",
        words_to_avoid: [],
        supplied_content: "Content",
        attribute_preferences: { mode: "auto" },
        sort_order: 1,
        created_at: "2025-11-27T00:00:00Z",
        updated_at: "2025-11-27T00:00:00Z",
      },
      error: null,
    });

    const res = await PATCH(
      mockRequest({ attribute_preferences: { mode: "auto" } }),
      mockParams({ projectId, skuId }),
    );

    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.attributePreferences).toEqual({ mode: "auto" });
  });

  it("accepts valid attribute preferences with overrides mode and rules", async () => {
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "456e4567-e89b-12d3-a456-426614174000";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const validPreferences = {
      mode: "overrides" as const,
      rules: {
        Color: { sections: ["title", "bullets"] },
        Size: { sections: ["title"] },
        Material: { sections: ["bullets", "description", "backend_keywords"] },
      },
    };

    const skus = supabaseMock.getBuilder("scribe_skus");
    skus.__pushResponse({
      data: {
        id: skuId,
        project_id: projectId,
        sku_code: "SKU001",
        asin: "B001",
        product_name: "Product 1",
        brand_tone: "Professional",
        target_audience: "Adults",
        words_to_avoid: [],
        supplied_content: "Content",
        attribute_preferences: validPreferences,
        sort_order: 1,
        created_at: "2025-11-27T00:00:00Z",
        updated_at: "2025-11-27T00:00:00Z",
      },
      error: null,
    });

    const res = await PATCH(
      mockRequest({ attribute_preferences: validPreferences }),
      mockParams({ projectId, skuId }),
    );

    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.attributePreferences).toEqual(validPreferences);
  });

  it("rejects invalid mode value", async () => {
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "456e4567-e89b-12d3-a456-426614174000";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const res = await PATCH(
      mockRequest({ attribute_preferences: { mode: "invalid" } }),
      mockParams({ projectId, skuId }),
    );

    expect(res.status).toBe(400);
    const json = await res.json();
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain('mode must be "auto" or "overrides"');
  });

  it("rejects invalid section names", async () => {
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "456e4567-e89b-12d3-a456-426614174000";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const invalidPreferences = {
      mode: "overrides" as const,
      rules: {
        Color: { sections: ["title", "invalid_section"] },
      },
    };

    const res = await PATCH(
      mockRequest({ attribute_preferences: invalidPreferences }),
      mockParams({ projectId, skuId }),
    );

    expect(res.status).toBe(400);
    const json = await res.json();
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain("invalid section");
    expect(json.error.message).toContain("invalid_section");
  });

  it("rejects malformed rules structure (missing sections array)", async () => {
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "456e4567-e89b-12d3-a456-426614174000";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const invalidPreferences = {
      mode: "overrides" as const,
      rules: {
        Color: { invalid: "field" },
      },
    };

    const res = await PATCH(
      mockRequest({ attribute_preferences: invalidPreferences }),
      mockParams({ projectId, skuId }),
    );

    expect(res.status).toBe(400);
    const json = await res.json();
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain("must have a sections array");
  });

  it("rejects non-array sections field", async () => {
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "456e4567-e89b-12d3-a456-426614174000";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const invalidPreferences = {
      mode: "overrides" as const,
      rules: {
        Color: { sections: "not-an-array" },
      },
    };

    const res = await PATCH(
      mockRequest({ attribute_preferences: invalidPreferences }),
      mockParams({ projectId, skuId }),
    );

    expect(res.status).toBe(400);
    const json = await res.json();
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain("must be an array");
  });

  it("accepts null attribute preferences (defaults to auto)", async () => {
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "456e4567-e89b-12d3-a456-426614174000";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const skus = supabaseMock.getBuilder("scribe_skus");
    skus.__pushResponse({
      data: {
        id: skuId,
        project_id: projectId,
        sku_code: "SKU001",
        asin: "B001",
        product_name: "Product 1",
        brand_tone: "Professional",
        target_audience: "Adults",
        words_to_avoid: [],
        supplied_content: "Content",
        attribute_preferences: null,
        sort_order: 1,
        created_at: "2025-11-27T00:00:00Z",
        updated_at: "2025-11-27T00:00:00Z",
      },
      error: null,
    });

    const res = await PATCH(
      mockRequest({ attribute_preferences: null }),
      mockParams({ projectId, skuId }),
    );

    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.attributePreferences).toBeNull();
  });

  it("accepts all valid section names", async () => {
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "456e4567-e89b-12d3-a456-426614174000";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const validPreferences = {
      mode: "overrides" as const,
      rules: {
        TestAttr: { sections: ["title", "bullets", "description", "backend_keywords"] },
      },
    };

    const skus = supabaseMock.getBuilder("scribe_skus");
    skus.__pushResponse({
      data: {
        id: skuId,
        project_id: projectId,
        sku_code: "SKU001",
        asin: "B001",
        product_name: "Product 1",
        brand_tone: "Professional",
        target_audience: "Adults",
        words_to_avoid: [],
        supplied_content: "Content",
        attribute_preferences: validPreferences,
        sort_order: 1,
        created_at: "2025-11-27T00:00:00Z",
        updated_at: "2025-11-27T00:00:00Z",
      },
      error: null,
    });

    const res = await PATCH(
      mockRequest({ attribute_preferences: validPreferences }),
      mockParams({ projectId, skuId }),
    );

    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.attributePreferences.rules.TestAttr.sections).toEqual([
      "title",
      "bullets",
      "description",
      "backend_keywords",
    ]);
  });

  it("rejects attribute_preferences that is not an object", async () => {
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "456e4567-e89b-12d3-a456-426614174000";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const res = await PATCH(
      mockRequest({ attribute_preferences: "not-an-object" }),
      mockParams({ projectId, skuId }),
    );

    expect(res.status).toBe(400);
    const json = await res.json();
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain("must be an object");
  });
});
