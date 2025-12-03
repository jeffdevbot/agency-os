import { describe, it, expect, beforeEach, vi } from "vitest";
import type { NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { createSupabaseClientMock, type SupabaseClientMock } from "@/lib/composer/testSupabaseClient";
import { GET, PATCH } from "./route";

vi.mock("@/lib/supabase/serverClient", () => ({
  createSupabaseRouteClient: vi.fn(),
}));

const mockParams = (params: Record<string, string | undefined>) => ({
  params: Promise.resolve(params),
});

const mockRequest = (body?: unknown) =>
  ({
    json: vi.fn().mockResolvedValue(body),
  }) as unknown as NextRequest;

describe("generated-content GET/PATCH", () => {
  let supabaseMock: SupabaseClientMock;
  const projectId = "11111111-1111-4111-8111-111111111111";
  const skuId = "33333333-3333-4333-8333-333333333333";

  beforeEach(() => {
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as unknown as vi.Mock).mockResolvedValue(supabaseMock.supabase);
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session: { user: { id: "user-1" } } } });
  });

  it("GET returns generated content for owned project/SKU", async () => {
    supabaseMock.getBuilder("scribe_projects").__pushResponse({
      data: { id: projectId, created_by: "user-1" },
      error: null,
    });
    supabaseMock.getBuilder("scribe_generated_content").__pushResponse({
      data: { sku_id: skuId, title: "T", bullets: ["b1", "b2"], description: "D", backend_keywords: "kw" },
      error: null,
    });

    const res = await GET(mockRequest(), mockParams({ projectId, skuId }));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.title).toBe("T");
    expect(body.bullets).toEqual(["b1", "b2"]);
  });

  it("PATCH updates title/bullets/description", async () => {
    supabaseMock.getBuilder("scribe_projects").__pushResponse({
      data: { id: projectId, created_by: "user-1" },
      error: null,
    });
    supabaseMock.getBuilder("scribe_skus").__pushResponse({
      data: { id: skuId },
      error: null,
    });
    supabaseMock.getBuilder("scribe_topics").__pushResponse({ data: null, error: null, count: 5 });
    supabaseMock.getBuilder("scribe_generated_content").__pushResponse({
      data: { sku_id: skuId, title: "Old", bullets: ["", "", "", "", ""], description: "", backend_keywords: "kw" },
      error: null,
    });
    const gcBuilder = supabaseMock.getBuilder("scribe_generated_content");
    // ensure upsert exists in mock chain
    gcBuilder.upsert = vi.fn().mockReturnThis();
    gcBuilder.__pushResponse({
      data: { sku_id: skuId, title: "New", bullets: ["x", "x2", "x3", "x4", "x5"], description: "Desc", backend_keywords: "kw" },
      error: null,
    });

    const res = await PATCH(
      mockRequest({ title: "New", bullets: ["x", "x2", "x3", "x4", "x5"], description: "Desc" }),
      mockParams({ projectId, skuId }),
    );

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.title).toBe("New");
    expect(body.bullets).toEqual(["x", "x2", "x3", "x4", "x5"]);
    expect(body.description).toBe("Desc");
  });
});
