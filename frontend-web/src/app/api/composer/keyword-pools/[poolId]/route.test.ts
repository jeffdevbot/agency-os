import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";
import { GET, PATCH } from "./route";
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

const buildSession = (overrides?: { orgId?: string | null }) => {
  const hasOverride =
    overrides && Object.prototype.hasOwnProperty.call(overrides, "orgId");
  const orgId = hasOverride ? overrides!.orgId ?? null : "623e4567-e89b-12d3-a456-426614174000";
  return {
    user: {
      id: "723e4567-e89b-12d3-a456-426614174000",
      org_id: orgId,
      app_metadata: {},
      user_metadata: {},
    },
  };
};

const mockPool = {
  id: "223e4567-e89b-12d3-a456-426614174000",
  organization_id: "623e4567-e89b-12d3-a456-426614174000",
  project_id: "123e4567-e89b-12d3-a456-426614174000",
  group_id: null,
  pool_type: "body",
  status: "uploaded",
  raw_keywords: ["blue shirt", "red shoes"],
  raw_keywords_url: null,
  cleaned_keywords: [],
  removed_keywords: [],
  clean_settings: {},
  grouping_config: {},
  cleaned_at: null,
  grouped_at: null,
  approved_at: null,
  created_at: "2025-11-20T10:00:00Z",
};

describe("keyword-pools API - single pool routes", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(
      supabaseMock.supabase,
    );
  });

  describe("GET /api/composer/keyword-pools/:id", () => {
    it("returns a single keyword pool by ID", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const poolBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      poolBuilder.single.mockResolvedValue({
        data: mockPool,
        error: null,
      });

      const response = await GET(mockRequest(), mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }));
      const json = await response.json();

      expect(response.status).toBe(200);
      expect(json.pool).toBeDefined();
      expect(json.pool.id).toBe("223e4567-e89b-12d3-a456-426614174000");
      expect(json.pool.poolType).toBe("body");
      expect(json.pool.rawKeywords).toEqual(["blue shirt", "red shoes"]);
    });

    it("returns 404 when pool not found", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const poolBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      poolBuilder.single.mockResolvedValue({ data: null, error: null });

      const response = await GET(mockRequest(), mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }));

      expect(response.status).toBe(404);
    });

    it("returns 401 when not authenticated", async () => {
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session: null },
      });

      const response = await GET(mockRequest(), mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }));

      expect(response.status).toBe(401);
    });

    it("returns 400 for invalid pool ID", async () => {
      const response = await GET(
        mockRequest(),
        mockParams({ poolId: "not-a-uuid" }),
      );

      expect(response.status).toBe(400);
      const json = await response.json();
      expect(json.error).toBe("invalid_pool_id");
    });

    it("verifies organization ownership", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const poolBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      poolBuilder.single.mockResolvedValue({
        data: mockPool,
        error: null,
      });

      await GET(mockRequest(), mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }));

      // Verify the query included organization_id check
      const eqCalls = poolBuilder.eq.mock.calls;
      expect(eqCalls).toContainEqual(["organization_id", "623e4567-e89b-12d3-a456-426614174000"]);
    });
  });

  describe("PATCH /api/composer/keyword-pools/:id", () => {
    it("updates raw keywords and resets approvals", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const fetchBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      fetchBuilder.single.mockResolvedValue({
        data: {
          ...mockPool,
          status: "cleaned",
          cleaned_at: "2025-11-20T09:00:00Z",
          cleaned_keywords: ["blue shirt", "red shoes"],
        },
        error: null,
      });

      const updateBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      updateBuilder.single.mockResolvedValue({
        data: {
          ...mockPool,
          raw_keywords: ["new keyword", "another keyword"],
          status: "uploaded",
          cleaned_at: null,
          grouped_at: null,
          approved_at: null,
          cleaned_keywords: [],
          removed_keywords: [],
        },
        error: null,
      });

      const response = await PATCH(
        mockRequest({
          rawKeywords: ["new keyword", "another keyword"],
        }),
        mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
      );

      const json = await response.json();

      expect(response.status).toBe(200);
      expect(json.pool.rawKeywords).toEqual([
        "new keyword",
        "another keyword",
      ]);
      expect(json.pool.status).toBe("uploaded");
      expect(json.pool.cleanedAt).toBeNull();
      expect(json.pool.groupedAt).toBeNull();
      expect(json.pool.approvedAt).toBeNull();
      expect(json.pool.cleanedKeywords).toEqual([]);
    });

    it("updates cleaned keywords without resetting state", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const fetchBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      fetchBuilder.single.mockResolvedValue({
        data: {
          ...mockPool,
          status: "uploaded",
        },
        error: null,
      });

      const updateBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      updateBuilder.single.mockResolvedValue({
        data: {
          ...mockPool,
          cleaned_keywords: ["blue shirt"],
          removed_keywords: [{ term: "red shoes", reason: "manual" }],
        },
        error: null,
      });

      const response = await PATCH(
        mockRequest({
          cleanedKeywords: ["blue shirt"],
          removedKeywords: [{ term: "red shoes", reason: "manual" }],
        }),
        mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
      );

      const json = await response.json();

      expect(response.status).toBe(200);
      expect(json.pool.cleanedKeywords).toEqual(["blue shirt"]);
      expect(json.pool.removedKeywords).toHaveLength(1);
      expect(json.pool.removedKeywords[0].term).toBe("red shoes");
    });

    it("updates clean settings", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const fetchBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      fetchBuilder.single.mockResolvedValue({
        data: mockPool,
        error: null,
      });

      const updateBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      updateBuilder.single.mockResolvedValue({
        data: {
          ...mockPool,
          clean_settings: {
            removeColors: true,
            removeSizes: false,
            removeBrandTerms: true,
            removeCompetitorTerms: true,
          },
        },
        error: null,
      });

      const response = await PATCH(
        mockRequest({
          cleanSettings: {
            removeColors: true,
            removeSizes: false,
            removeBrandTerms: true,
            removeCompetitorTerms: true,
          },
        }),
        mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
      );

      const json = await response.json();

      expect(response.status).toBe(200);
      expect(json.pool.cleanSettings).toEqual({
        removeColors: true,
        removeSizes: false,
        removeBrandTerms: true,
        removeCompetitorTerms: true,
      });
    });

    it("updates grouping config and resets grouped/approved timestamps", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const fetchBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      fetchBuilder.single.mockResolvedValue({
        data: {
          ...mockPool,
          status: "grouped",
          grouped_at: "2025-11-20T11:00:00Z",
          approved_at: "2025-11-20T11:30:00Z",
        },
        error: null,
      });

      const updateBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      updateBuilder.single.mockResolvedValue({
        data: {
          ...mockPool,
          grouping_config: {
            basis: "custom",
            groupCount: 5,
          },
          grouped_at: null,
          approved_at: null,
        },
        error: null,
      });

      const response = await PATCH(
        mockRequest({
          groupingConfig: {
            basis: "custom",
            groupCount: 5,
          },
        }),
        mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
      );

      const json = await response.json();

      expect(response.status).toBe(200);
      expect(json.pool.groupingConfig).toEqual({
        basis: "custom",
        groupCount: 5,
      });
      expect(json.pool.groupedAt).toBeNull();
      expect(json.pool.approvedAt).toBeNull();
    });

    it("approves cleaning when cleaned keywords exist", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const poolBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      poolBuilder.__pushResponse({
        data: {
          ...mockPool,
          status: "uploaded",
          cleaned_keywords: ["blue shirt", "red shoes"],
        },
        error: null,
      });
      poolBuilder.__pushResponse({
        data: {
          ...mockPool,
          status: "cleaned",
          cleaned_keywords: ["blue shirt", "red shoes"],
          cleaned_at: "2025-11-20T12:00:00Z",
        },
        error: null,
      });

      const response = await PATCH(
        mockRequest({
          status: "cleaned",
        }),
        mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
      );

      const json = await response.json();

      expect(response.status).toBe(200);
      expect(json.pool.status).toBe("cleaned");
      expect(json.pool.cleanedKeywords).toEqual(["blue shirt", "red shoes"]);
    });

    it("updates timestamps", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const fetchBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      fetchBuilder.single.mockResolvedValue({
        data: mockPool,
        error: null,
      });

      const updateBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      updateBuilder.single.mockResolvedValue({
        data: {
          ...mockPool,
          cleaned_at: "2025-11-20T12:00:00Z",
          grouped_at: "2025-11-20T12:30:00Z",
          approved_at: "2025-11-20T13:00:00Z",
        },
        error: null,
      });

      const response = await PATCH(
        mockRequest({
          cleanedAt: "2025-11-20T12:00:00Z",
          groupedAt: "2025-11-20T12:30:00Z",
          approvedAt: "2025-11-20T13:00:00Z",
        }),
        mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
      );

      const json = await response.json();

      expect(response.status).toBe(200);
      expect(json.pool.cleanedAt).toBe("2025-11-20T12:00:00Z");
      expect(json.pool.groupedAt).toBe("2025-11-20T12:30:00Z");
      expect(json.pool.approvedAt).toBe("2025-11-20T13:00:00Z");
    });

    it("returns 404 when pool not found", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const fetchBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      fetchBuilder.single.mockResolvedValue({ data: null, error: null });

      const response = await PATCH(
        mockRequest({
          status: "cleaned",
        }),
        mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
      );

      expect(response.status).toBe(404);
    });

    it("returns 401 when not authenticated", async () => {
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session: null },
      });

      const response = await PATCH(
        mockRequest({
          status: "cleaned",
        }),
        mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
      );

      expect(response.status).toBe(401);
    });

    it("returns 400 for invalid pool ID", async () => {
      const response = await PATCH(
        mockRequest({
          status: "cleaned",
        }),
        mockParams({ poolId: "not-a-uuid" }),
      );

      expect(response.status).toBe(400);
      const json = await response.json();
      expect(json.error).toBe("invalid_pool_id");
    });

    it("rejects approval when cleaned keywords are missing", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const fetchBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      fetchBuilder.single.mockResolvedValue({
        data: {
          ...mockPool,
          status: "uploaded",
          cleaned_keywords: [],
        },
        error: null,
      });

      const response = await PATCH(
        mockRequest({
          status: "cleaned",
        }),
        mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
      );

      expect(response.status).toBe(400);
      const json = await response.json();
      expect(json.error).toBe("cannot_approve_without_cleaned_keywords");
    });

    it("rejects approval when pool is not in uploaded state", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const fetchBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      fetchBuilder.single.mockResolvedValue({
        data: {
          ...mockPool,
          status: "cleaned",
          cleaned_keywords: ["blue shirt"],
        },
        error: null,
      });

      const response = await PATCH(
        mockRequest({
          status: "cleaned",
        }),
        mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
      );

      expect(response.status).toBe(400);
      const json = await response.json();
      expect(json.error).toBe("approval_not_allowed_from_state");
    });

    it("handles multiple field updates in one request", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const poolBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      poolBuilder.__pushResponse({
        data: mockPool,
        error: null,
      });
      poolBuilder.__pushResponse({
        data: {
          ...mockPool,
          cleaned_keywords: ["blue shirt"],
          removed_keywords: [{ term: "red shoes", reason: "manual" }],
          clean_settings: { removeColors: true },
          status: "cleaned",
          cleaned_at: "2025-11-20T12:00:00Z",
        },
        error: null,
      });

      const response = await PATCH(
        mockRequest({
          cleanedKeywords: ["blue shirt"],
          removedKeywords: [{ term: "red shoes", reason: "manual" }],
          cleanSettings: { removeColors: true },
          status: "cleaned",
          cleanedAt: "2025-11-20T12:00:00Z",
        }),
        mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
      );

      const json = await response.json();

      expect(response.status).toBe(200);
      expect(json.pool.cleanedKeywords).toEqual(["blue shirt"]);
      expect(json.pool.removedKeywords).toHaveLength(1);
      expect(json.pool.cleanSettings.removeColors).toBe(true);
      expect(json.pool.status).toBe("cleaned");
      expect(json.pool.cleanedAt).toBe("2025-11-20T12:00:00Z");
    });
  });
});
