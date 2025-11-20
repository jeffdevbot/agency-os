import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";
import { POST } from "./route";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import {
  createSupabaseClientMock,
  type SupabaseClientMock,
} from "@/lib/composer/testSupabaseClient";

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

const buildSession = (orgId = "623e4567-e89b-12d3-a456-426614174000") => ({
  user: {
    id: "723e4567-e89b-12d3-a456-426614174000",
    org_id: orgId,
    app_metadata: {},
    user_metadata: {},
  },
});

describe("keyword-pools clean API", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(
      supabaseMock.supabase,
    );
  });

  it("cleans keywords using project + attribute data and stores results", async () => {
    const session = buildSession();
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session },
    });

    const poolBuilder = supabaseMock.getBuilder("composer_keyword_pools");
    poolBuilder.__pushResponse({
      data: {
        id: "223e4567-e89b-12d3-a456-426614174000",
        organization_id: session.user.org_id,
        project_id: "123e4567-e89b-12d3-a456-426614174000",
        group_id: null,
        pool_type: "body",
        status: "uploaded",
        raw_keywords: [
          "Acme Widget",
          "Blue Shirt",
          "blue shirt",
          "Contoso Bag",
          "XL Duffel",
          "Fresh Item",
        ],
        raw_keywords_url: null,
        cleaned_keywords: [],
        removed_keywords: [],
        clean_settings: {},
        grouping_config: {},
        cleaned_at: null,
        grouped_at: null,
        approved_at: null,
        created_at: "2025-11-20T10:00:00Z",
      },
      error: null,
    });

    const projectBuilder = supabaseMock.getBuilder("composer_projects");
    projectBuilder.__pushResponse({
      data: {
        id: "123e4567-e89b-12d3-a456-426614174000",
        organization_id: session.user.org_id,
        client_name: "Acme",
        what_not_to_say: ["Contoso"],
      },
      error: null,
    });

    const variantsBuilder = supabaseMock.getBuilder("composer_sku_variants");
    variantsBuilder.__pushResponse({
      data: [
        { attributes: { color: "Blue", size: "XL" }, group_id: null },
      ],
      error: null,
    });

    poolBuilder.__pushResponse({
      data: {
        id: "223e4567-e89b-12d3-a456-426614174000",
        organization_id: session.user.org_id,
        project_id: "123e4567-e89b-12d3-a456-426614174000",
        group_id: null,
        pool_type: "body",
        status: "uploaded",
        raw_keywords: [
          "Acme Widget",
          "Blue Shirt",
          "blue shirt",
          "Contoso Bag",
          "XL Duffel",
          "Fresh Item",
        ],
        raw_keywords_url: null,
        cleaned_keywords: ["Fresh Item"],
        removed_keywords: [
          { term: "Acme Widget", reason: "brand" },
          { term: "Blue Shirt", reason: "color" },
          { term: "blue shirt", reason: "duplicate" },
          { term: "Contoso Bag", reason: "competitor" },
          { term: "XL Duffel", reason: "size" },
        ],
        clean_settings: {
          removeColors: true,
          removeSizes: true,
          removeBrandTerms: true,
          removeCompetitorTerms: true,
        },
        grouping_config: {},
        cleaned_at: "2025-11-20T12:00:00Z",
        grouped_at: null,
        approved_at: null,
        created_at: "2025-11-20T10:00:00Z",
      },
      error: null,
    });

    const response = await POST(
      mockRequest({
        config: {
          removeColors: true,
          removeSizes: true,
        },
      }),
      mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
    );

    const json = await response.json();

    expect(response.status).toBe(200);
    expect(json.cleaned).toEqual(["Fresh Item"]);
    expect(json.removed).toHaveLength(5);
    expect(json.removed[0]).toEqual({ term: "Acme Widget", reason: "brand" });
    expect(json.pool.cleanedKeywords).toEqual(["Fresh Item"]);
    expect(json.pool.status).toBe("uploaded");
  });

  it("returns 404 when pool is not found", async () => {
    const session = buildSession();
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session },
    });

    const poolBuilder = supabaseMock.getBuilder("composer_keyword_pools");
    poolBuilder.__pushResponse({ data: null, error: null });

    const response = await POST(
      mockRequest({ config: {} }),
      mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
    );

    expect(response.status).toBe(404);
  });

  it("returns 401 when not authenticated", async () => {
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: null },
    });

    const response = await POST(
      mockRequest({ config: {} }),
      mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
    );

    expect(response.status).toBe(401);
  });
});
