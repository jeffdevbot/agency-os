import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";
import { POST, DELETE } from "./route";
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

describe("group-overrides POST API", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(
      supabaseMock.supabase,
    );
  });

  it("creates a move override successfully", async () => {
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

    const overridesBuilder = supabaseMock.getBuilder(
      "composer_keyword_group_overrides",
    );
    overridesBuilder.__pushResponse({
      data: {
        id: "o23e4567-e89b-12d3-a456-426614174000",
        organization_id: session.user.org_id,
        keyword_pool_id: "223e4567-e89b-12d3-a456-426614174000",
        phrase: "blue shirt",
        action: "move",
        target_group_label: "Red Items",
        target_group_index: 1,
        source_group_id: "g23e4567-e89b-12d3-a456-426614174000",
        created_at: "2025-11-20T12:00:00Z",
      },
      error: null,
    });

    poolBuilder.__pushResponse({ data: {}, error: null });

    const response = await POST(
      mockRequest({
        phrase: "blue shirt",
        action: "move",
        targetGroupIndex: 1,
        targetGroupLabel: "Red Items",
        sourceGroupId: "g23e4567-e89b-12d3-a456-426614174000",
      }),
      mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
    );

    const json = await response.json();

    expect(response.status).toBe(200);
    expect(json.override.phrase).toBe("blue shirt");
    expect(json.override.action).toBe("move");
    expect(json.override.target_group_index).toBe(1);
  });

  it("creates a remove override successfully", async () => {
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

    const overridesBuilder = supabaseMock.getBuilder(
      "composer_keyword_group_overrides",
    );
    overridesBuilder.__pushResponse({
      data: {
        id: "o23e4567-e89b-12d3-a456-426614174000",
        organization_id: session.user.org_id,
        keyword_pool_id: "223e4567-e89b-12d3-a456-426614174000",
        phrase: "bad keyword",
        action: "remove",
        target_group_label: null,
        target_group_index: null,
        source_group_id: null,
        created_at: "2025-11-20T12:00:00Z",
      },
      error: null,
    });

    poolBuilder.__pushResponse({ data: {}, error: null });

    const response = await POST(
      mockRequest({
        phrase: "bad keyword",
        action: "remove",
      }),
      mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
    );

    const json = await response.json();

    expect(response.status).toBe(200);
    expect(json.override.phrase).toBe("bad keyword");
    expect(json.override.action).toBe("remove");
  });

  it("resets approved_at when override is created", async () => {
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

    const overridesBuilder = supabaseMock.getBuilder(
      "composer_keyword_group_overrides",
    );
    overridesBuilder.__pushResponse({
      data: {
        id: "o23e4567-e89b-12d3-a456-426614174000",
        organization_id: session.user.org_id,
        keyword_pool_id: "223e4567-e89b-12d3-a456-426614174000",
        phrase: "keyword",
        action: "remove",
        target_group_label: null,
        target_group_index: null,
        source_group_id: null,
        created_at: "2025-11-20T12:00:00Z",
      },
      error: null,
    });

    poolBuilder.__pushResponse({ data: {}, error: null });

    const response = await POST(
      mockRequest({ phrase: "keyword", action: "remove" }),
      mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
    );

    expect(response.status).toBe(200);
  });

  it("returns 400 when phrase is missing", async () => {
    const session = buildSession();
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session },
    });

    const response = await POST(
      mockRequest({ action: "remove" }),
      mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
    );

    expect(response.status).toBe(400);
    const json = await response.json();
    expect(json.error).toContain("phrase and action are required");
  });

  it("returns 400 when action is invalid", async () => {
    const session = buildSession();
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session },
    });

    const response = await POST(
      mockRequest({ phrase: "keyword", action: "invalid" }),
      mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
    );

    expect(response.status).toBe(400);
    const json = await response.json();
    expect(json.error).toBe("invalid action");
  });

  it("returns 400 when targetGroupIndex is missing for move action", async () => {
    const session = buildSession();
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session },
    });

    const response = await POST(
      mockRequest({ phrase: "keyword", action: "move" }),
      mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
    );

    expect(response.status).toBe(400);
    const json = await response.json();
    expect(json.error).toContain("targetGroupIndex is required");
  });

  it("returns 404 when pool is not found", async () => {
    const session = buildSession();
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session },
    });

    const poolBuilder = supabaseMock.getBuilder("composer_keyword_pools");
    poolBuilder.__pushResponse({ data: null, error: null });

    const response = await POST(
      mockRequest({ phrase: "keyword", action: "remove" }),
      mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
    );

    expect(response.status).toBe(404);
  });

  it("returns 401 when not authenticated", async () => {
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: null },
    });

    const response = await POST(
      mockRequest({ phrase: "keyword", action: "remove" }),
      mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
    );

    expect(response.status).toBe(401);
  });
});

describe("group-overrides DELETE API", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(
      supabaseMock.supabase,
    );
  });

  it("deletes all overrides for a pool", async () => {
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

    const overridesBuilder = supabaseMock.getBuilder(
      "composer_keyword_group_overrides",
    );
    overridesBuilder.__pushResponse({ data: null, error: null });

    poolBuilder.__pushResponse({ data: {}, error: null });

    const response = await DELETE(
      mockRequest(),
      mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
    );

    const json = await response.json();

    expect(response.status).toBe(200);
    expect(json.success).toBe(true);
    expect(json.deleted).toBe(true);
  });

  it("resets approved_at when overrides are deleted", async () => {
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

    const overridesBuilder = supabaseMock.getBuilder(
      "composer_keyword_group_overrides",
    );
    overridesBuilder.__pushResponse({ data: null, error: null });

    poolBuilder.__pushResponse({ data: {}, error: null });

    const response = await DELETE(mockRequest(), mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }));

    expect(response.status).toBe(200);
  });

  it("returns 404 when pool is not found", async () => {
    const session = buildSession();
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session },
    });

    const poolBuilder = supabaseMock.getBuilder("composer_keyword_pools");
    poolBuilder.__pushResponse({ data: null, error: null });

    const response = await DELETE(
      mockRequest(),
      mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
    );

    expect(response.status).toBe(404);
  });

  it("returns 401 when not authenticated", async () => {
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: null },
    });

    const response = await DELETE(
      mockRequest(),
      mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
    );

    expect(response.status).toBe(401);
  });
});
