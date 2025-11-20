import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";
import { GET, POST } from "./route";
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

const mockRequest = (body?: unknown, url?: string) =>
  ({
    json: vi.fn().mockResolvedValue(body),
    url: url || "http://localhost:3000/api/composer/projects/proj-1/keyword-pools",
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

describe("keyword-pools API - project-level routes", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(
      supabaseMock.supabase,
    );
  });

  describe("GET /api/composer/projects/:id/keyword-pools", () => {
    it("returns all pools for the project", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const projectBuilder = supabaseMock.getBuilder("composer_projects");
      projectBuilder.single.mockResolvedValue({
        data: { id: "123e4567-e89b-12d3-a456-426614174000" },
        error: null,
      });

      const poolsBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      poolsBuilder.__pushResponse({
        data: [
          {
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
          },
          {
            id: "323e4567-e89b-12d3-a456-426614174000",
            organization_id: "623e4567-e89b-12d3-a456-426614174000",
            project_id: "123e4567-e89b-12d3-a456-426614174000",
            group_id: null,
            pool_type: "titles",
            status: "empty",
            raw_keywords: [],
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
        ],
        error: null,
      });

      const response = await GET(
        mockRequest(),
        mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }),
      );
      const json = await response.json();

      expect(response.status).toBe(200);
      expect(json.pools).toHaveLength(2);
      expect(json.pools[0].poolType).toBe("body");
      expect(json.pools[1].poolType).toBe("titles");
    });

    it("filters by groupId if provided", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const projectBuilder = supabaseMock.getBuilder("composer_projects");
      projectBuilder.single.mockResolvedValue({
        data: { id: "123e4567-e89b-12d3-a456-426614174000" },
        error: null,
      });

      const poolsBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      poolsBuilder.__pushResponse({
        data: [
          {
            id: "223e4567-e89b-12d3-a456-426614174000",
            organization_id: "623e4567-e89b-12d3-a456-426614174000",
            project_id: "123e4567-e89b-12d3-a456-426614174000",
            group_id: "523e4567-e89b-12d3-a456-426614174000",
            pool_type: "body",
            status: "uploaded",
            raw_keywords: ["blue shirt"],
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
        ],
        error: null,
      });

      const url =
        "http://localhost:3000/api/composer/projects/123e4567-e89b-12d3-a456-426614174000/keyword-pools?groupId=523e4567-e89b-12d3-a456-426614174000";
      const response = await GET(
        mockRequest(undefined, url),
        mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }),
      );
      const json = await response.json();

      expect(response.status).toBe(200);
      expect(json.pools).toHaveLength(1);
      expect(json.pools[0].groupId).toBe("523e4567-e89b-12d3-a456-426614174000");

      // Verify the query had the eq('group_id', 'group-1') call
      const eqCalls = poolsBuilder.eq.mock.calls;
      expect(eqCalls).toContainEqual(["group_id", "523e4567-e89b-12d3-a456-426614174000"]);
    });

    it("returns 401 when not authenticated", async () => {
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session: null },
      });

      const response = await GET(
        mockRequest(),
        mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }),
      );

      expect(response.status).toBe(401);
    });

    it("returns 404 when project not found", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const projectBuilder = supabaseMock.getBuilder("composer_projects");
      projectBuilder.single.mockResolvedValue({ data: null, error: null });

      const response = await GET(
        mockRequest(),
        mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }),
      );

      expect(response.status).toBe(404);
    });

    it("returns 400 for invalid project ID", async () => {
      const response = await GET(
        mockRequest(),
        mockParams({ projectId: "not-a-uuid" }),
      );

      expect(response.status).toBe(400);
      const json = await response.json();
      expect(json.error).toBe("invalid_project_id");
    });
  });

  describe("POST /api/composer/projects/:id/keyword-pools", () => {
    it("creates a new keyword pool", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const projectBuilder = supabaseMock.getBuilder("composer_projects");
      projectBuilder.single.mockResolvedValue({
        data: { id: "123e4567-e89b-12d3-a456-426614174000" },
        error: null,
      });

      const poolsBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      // First query: check for existing pool - returns null
      poolsBuilder.__pushResponse({ data: null, error: null });
      // Second operation: insert new pool
      poolsBuilder.__pushResponse({
        data: {
          id: "423e4567-e89b-12d3-a456-426614174000",
          organization_id: "623e4567-e89b-12d3-a456-426614174000",
          project_id: "123e4567-e89b-12d3-a456-426614174000",
          group_id: null,
          pool_type: "body",
          status: "uploaded",
          raw_keywords: ["blue shirt", "red shoes", "green hat", "yellow pants", "orange jacket"],
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

      const response = await POST(
        mockRequest({
          poolType: "body",
          keywords: ["blue shirt", "red shoes", "green hat", "Blue Shirt", "yellow pants", "orange jacket"],
        }),
        mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }),
      );

      const json = await response.json();

      expect(response.status).toBe(201);
      expect(json.pool).toBeDefined();
      expect(json.pool.poolType).toBe("body");
      expect(json.pool.status).toBe("uploaded");
      expect(json.merged).toBe(false);
      // Should have deduped "Blue Shirt" case-insensitively (6 keywords -> 5 after dedupe)
      expect(json.pool.rawKeywords).toHaveLength(5);
    });

    it("merges with existing pool and resets approvals", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const projectBuilder = supabaseMock.getBuilder("composer_projects");
      projectBuilder.single.mockResolvedValue({
        data: { id: "123e4567-e89b-12d3-a456-426614174000" },
        error: null,
      });

      const poolsBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      // First query: check for existing pool - returns existing pool
      poolsBuilder.__pushResponse({
        data: {
          id: "223e4567-e89b-12d3-a456-426614174000",
          organization_id: "623e4567-e89b-12d3-a456-426614174000",
          project_id: "123e4567-e89b-12d3-a456-426614174000",
          group_id: null,
          pool_type: "body",
          status: "cleaned",
          raw_keywords: ["existing keyword", "another term", "third phrase"],
          cleaned_keywords: ["existing keyword", "another term", "third phrase"],
          removed_keywords: [],
          clean_settings: {},
          grouping_config: {},
          cleaned_at: "2025-11-20T09:00:00Z",
          grouped_at: null,
          approved_at: null,
          created_at: "2025-11-20T08:00:00Z",
        },
        error: null,
      });
      // Second operation: update pool
      poolsBuilder.__pushResponse({
        data: {
          id: "223e4567-e89b-12d3-a456-426614174000",
          organization_id: "623e4567-e89b-12d3-a456-426614174000",
          project_id: "123e4567-e89b-12d3-a456-426614174000",
          group_id: null,
          pool_type: "body",
          status: "uploaded",
          raw_keywords: ["existing keyword", "another term", "third phrase", "new keyword", "fifth term"],
          raw_keywords_url: null,
          cleaned_keywords: [],
          removed_keywords: [],
          clean_settings: {},
          grouping_config: {},
          cleaned_at: null,
          grouped_at: null,
          approved_at: null,
          created_at: "2025-11-20T08:00:00Z",
        },
        error: null,
      });

      const response = await POST(
        mockRequest({
          poolType: "body",
          keywords: ["new keyword", "Existing Keyword", "fifth term"],
        }),
        mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }),
      );

      const json = await response.json();

      expect(response.status).toBe(200);
      expect(json.merged).toBe(true);
      expect(json.pool.rawKeywords).toHaveLength(5);
      expect(json.pool.rawKeywords).toContain("existing keyword");
      expect(json.pool.rawKeywords).toContain("new keyword");
      // Status should reset to uploaded
      expect(json.pool.status).toBe("uploaded");
      // Approvals should be reset
      expect(json.pool.cleanedAt).toBeNull();
      expect(json.pool.groupedAt).toBeNull();
      expect(json.pool.approvedAt).toBeNull();
      // Cleaned keywords should be cleared
      expect(json.pool.cleanedKeywords).toEqual([]);
    });

    it("returns error for less than 5 keywords", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const projectBuilder = supabaseMock.getBuilder("composer_projects");
      projectBuilder.single.mockResolvedValue({
        data: { id: "123e4567-e89b-12d3-a456-426614174000" },
        error: null,
      });

      const poolsQueryBuilder = supabaseMock.getBuilder(
        "composer_keyword_pools",
      );
      poolsQueryBuilder.single.mockResolvedValue({ data: null, error: null });

      const response = await POST(
        mockRequest({
          poolType: "body",
          keywords: ["one", "two", "three"],
        }),
        mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }),
      );

      const json = await response.json();

      expect(response.status).toBe(400);
      expect(json.error).toContain("At least 5 keywords are required");
    });

    it("returns error for more than 5000 keywords", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const projectBuilder = supabaseMock.getBuilder("composer_projects");
      projectBuilder.single.mockResolvedValue({
        data: { id: "123e4567-e89b-12d3-a456-426614174000" },
        error: null,
      });

      const poolsQueryBuilder = supabaseMock.getBuilder(
        "composer_keyword_pools",
      );
      poolsQueryBuilder.single.mockResolvedValue({ data: null, error: null });

      const tooManyKeywords = Array.from(
        { length: 5001 },
        (_, i) => `keyword${i}`,
      );

      const response = await POST(
        mockRequest({
          poolType: "body",
          keywords: tooManyKeywords,
        }),
        mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }),
      );

      const json = await response.json();

      expect(response.status).toBe(400);
      expect(json.error).toContain("Maximum 5000 keywords allowed");
    });

    it("returns warning for less than 20 keywords", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const projectBuilder = supabaseMock.getBuilder("composer_projects");
      projectBuilder.single.mockResolvedValue({
        data: { id: "123e4567-e89b-12d3-a456-426614174000" },
        error: null,
      });

      const poolsBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      // First query: check for existing pool - returns null
      poolsBuilder.__pushResponse({ data: null, error: null });
      // Second operation: insert new pool
      poolsBuilder.__pushResponse({
        data: {
          id: "423e4567-e89b-12d3-a456-426614174000",
          organization_id: "623e4567-e89b-12d3-a456-426614174000",
          project_id: "123e4567-e89b-12d3-a456-426614174000",
          group_id: null,
          pool_type: "body",
          status: "uploaded",
          raw_keywords: Array.from({ length: 10 }, (_, i) => `keyword${i}`),
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

      const tenKeywords = Array.from({ length: 10 }, (_, i) => `keyword${i}`);

      const response = await POST(
        mockRequest({
          poolType: "body",
          keywords: tenKeywords,
        }),
        mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }),
      );

      const json = await response.json();

      expect(response.status).toBe(201);
      expect(json.warning).toBeDefined();
      expect(json.warning).toContain("only 10 keywords");
      expect(json.warning).toContain("recommend 50-100+");
    });

    it("supports group-level pools (distinct mode)", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const projectBuilder = supabaseMock.getBuilder("composer_projects");
      projectBuilder.single.mockResolvedValue({
        data: { id: "123e4567-e89b-12d3-a456-426614174000" },
        error: null,
      });

      const groupBuilder = supabaseMock.getBuilder("composer_sku_groups");
      groupBuilder.single.mockResolvedValue({
        data: { id: "523e4567-e89b-12d3-a456-426614174000" },
        error: null,
      });

      const poolsBuilder = supabaseMock.getBuilder("composer_keyword_pools");
      // First query: check for existing pool - returns null
      poolsBuilder.__pushResponse({ data: null, error: null });
      // Second operation: insert new pool
      poolsBuilder.__pushResponse({
        data: {
          id: "423e4567-e89b-12d3-a456-426614174000",
          organization_id: "623e4567-e89b-12d3-a456-426614174000",
          project_id: "123e4567-e89b-12d3-a456-426614174000",
          group_id: "523e4567-e89b-12d3-a456-426614174000",
          pool_type: "body",
          status: "uploaded",
          raw_keywords: ["blue shirt", "navy top", "cobalt tee", "azure blouse", "sapphire sweater"],
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

      const response = await POST(
        mockRequest({
          poolType: "body",
          groupId: "523e4567-e89b-12d3-a456-426614174000",
          keywords: ["blue shirt", "navy top", "cobalt tee", "azure blouse", "sapphire sweater"],
        }),
        mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }),
      );

      const json = await response.json();

      expect(response.status).toBe(201);
      expect(json.pool.groupId).toBe("523e4567-e89b-12d3-a456-426614174000");
    });

    it("returns 404 when group not found", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const projectBuilder = supabaseMock.getBuilder("composer_projects");
      projectBuilder.single.mockResolvedValue({
        data: { id: "123e4567-e89b-12d3-a456-426614174000" },
        error: null,
      });

      const groupBuilder = supabaseMock.getBuilder("composer_sku_groups");
      groupBuilder.single.mockResolvedValue({ data: null, error: null });

      const response = await POST(
        mockRequest({
          poolType: "body",
          groupId: "523e4567-e89b-12d3-a456-426614174000",
          keywords: ["one", "two", "three", "four", "five"],
        }),
        mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }),
      );

      expect(response.status).toBe(404);
    });

    it("returns 400 for invalid poolType", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const response = await POST(
        mockRequest({
          poolType: "invalid",
          keywords: ["one", "two", "three", "four", "five"],
        }),
        mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }),
      );

      const json = await response.json();

      expect(response.status).toBe(400);
      expect(json.error).toContain("poolType must be 'body' or 'titles'");
    });

    it("returns 400 when keywords is not an array", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({
        data: { session },
      });

      const response = await POST(
        mockRequest({
          poolType: "body",
          keywords: "not an array",
        }),
        mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }),
      );

      const json = await response.json();

      expect(response.status).toBe(400);
      expect(json.error).toContain("keywords must be an array");
    });
  });
});
