import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";
import { GET } from "./route";
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

const mockRequest = () =>
  ({
    json: vi.fn(),
  }) as unknown as NextRequest;

const buildSession = (orgId = "623e4567-e89b-12d3-a456-426614174000") => ({
  user: {
    id: "723e4567-e89b-12d3-a456-426614174000",
    org_id: orgId,
    app_metadata: {},
    user_metadata: {},
  },
});

describe("groups GET API", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(
      supabaseMock.supabase,
    );
  });

  it("returns AI groups, overrides, and merged view", async () => {
    const session = buildSession();
    const poolId = "223e4567-e89b-12d3-a456-426614174000";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session },
    });

    const poolBuilder = supabaseMock.getBuilder("composer_keyword_pools");
    poolBuilder.__pushResponse({
      data: {
        id: poolId,
        organization_id: session.user.org_id,
      },
      error: null,
    });

    const groupsBuilder = supabaseMock.getBuilder("composer_keyword_groups");
    groupsBuilder.__pushResponse({
      data: [
        {
          id: "g23e4567-e89b-12d3-a456-426614174000",
          organization_id: session.user.org_id,
          keyword_pool_id: poolId,
          group_index: 0,
          label: "Blue Items",
          phrases: ["blue shirt", "navy pants"],
          metadata: { aiGenerated: true },
          created_at: "2025-11-20T10:00:00Z",
        },
        {
          id: "g23e4567-e89b-12d3-a456-426614174001",
          organization_id: session.user.org_id,
          keyword_pool_id: "223e4567-e89b-12d3-a456-426614174000",
          group_index: 1,
          label: "Red Items",
          phrases: ["red dress"],
          metadata: { aiGenerated: true },
          created_at: "2025-11-20T10:00:00Z",
        },
      ],
      error: null,
    });

    const overridesBuilder = supabaseMock.getBuilder(
      "composer_keyword_group_overrides",
    );
    overridesBuilder.__pushResponse({
      data: [
        {
          id: "o23e4567-e89b-12d3-a456-426614174000",
          organization_id: session.user.org_id,
          keyword_pool_id: "223e4567-e89b-12d3-a456-426614174000",
          source_group_id: "g23e4567-e89b-12d3-a456-426614174000",
          phrase: "navy pants",
          action: "move",
          target_group_label: "Red Items",
          target_group_index: 1,
          created_at: "2025-11-20T11:00:00Z",
        },
      ],
      error: null,
    });

    const response = await GET(mockRequest(), mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }));

    const json = await response.json();

    expect(response.status).toBe(200);
    expect(json.aiGroups).toHaveLength(2);
    expect(json.overrides).toHaveLength(1);
    expect(json.merged).toHaveLength(2);

    expect(json.merged[0].phrases).toEqual(["blue shirt"]);
    expect(json.merged[1].phrases).toEqual(["red dress", "navy pants"]);
  });

  it("returns empty groups and overrides when none exist", async () => {
    const session = buildSession();
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session },
    });

    const poolBuilder = supabaseMock.getBuilder("composer_keyword_pools");
    poolBuilder.__pushResponse({
      data: {
        id: "223e4567-e89b-12d3-a456-426614174000",
        organization_id: session.user.org_id,
      },
      error: null,
    });

    const groupsBuilder = supabaseMock.getBuilder("composer_keyword_groups");
    groupsBuilder.__pushResponse({
      data: [],
      error: null,
    });

    const overridesBuilder = supabaseMock.getBuilder(
      "composer_keyword_group_overrides",
    );
    overridesBuilder.__pushResponse({
      data: [],
      error: null,
    });

    const response = await GET(mockRequest(), mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }));

    const json = await response.json();

    expect(response.status).toBe(200);
    expect(json.aiGroups).toEqual([]);
    expect(json.overrides).toEqual([]);
    expect(json.merged).toEqual([]);
  });

  it("returns 404 when pool is not found", async () => {
    const session = buildSession();
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session },
    });

    const poolBuilder = supabaseMock.getBuilder("composer_keyword_pools");
    poolBuilder.__pushResponse({ data: null, error: null });

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
    const session = buildSession();
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session },
    });

    const response = await GET(mockRequest(), mockParams({ poolId: "invalid" }));

    expect(response.status).toBe(400);
  });

  it("handles groups query error gracefully", async () => {
    const session = buildSession();
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session },
    });

    const poolBuilder = supabaseMock.getBuilder("composer_keyword_pools");
    poolBuilder.__pushResponse({
      data: {
        id: "223e4567-e89b-12d3-a456-426614174000",
        organization_id: session.user.org_id,
      },
      error: null,
    });

    const groupsBuilder = supabaseMock.getBuilder("composer_keyword_groups");
    groupsBuilder.__pushResponse({
      data: null,
      error: { message: "Database error" },
    });

    const response = await GET(mockRequest(), mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }));

    expect(response.status).toBe(500);
  });
});
