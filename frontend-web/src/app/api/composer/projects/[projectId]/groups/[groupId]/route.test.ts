import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";
import { DELETE, PATCH } from "./route";
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
  }) as unknown as NextRequest;

const buildSession = (overrides?: { orgId?: string | null }) => {
  const hasOverride = overrides && Object.prototype.hasOwnProperty.call(overrides, "orgId");
  const orgId = hasOverride ? overrides!.orgId ?? null : "org-1";
  return {
    user: {
      id: "user-1",
      org_id: orgId,
      app_metadata: {},
      user_metadata: {},
    },
  };
};

describe("composer group detail API", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(supabaseMock.supabase);
  });

  describe("PATCH", () => {
    const validParams = {
      projectId: "123e4567-e89b-12d3-a456-426614174000",
      groupId: "123e4567-e89b-12d3-a456-426614174111",
    };

    beforeEach(() => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session } });
      const projectBuilder = supabaseMock.getBuilder("composer_projects");
      projectBuilder.single.mockResolvedValue({ data: { id: validParams.projectId }, error: null });
    });

    it("updates a group and returns the mapped payload", async () => {
      const groupBuilder = supabaseMock.getBuilder("composer_sku_groups");
      groupBuilder.single.mockResolvedValue({
        data: {
          id: validParams.groupId,
          organization_id: "org-1",
          project_id: validParams.projectId,
          name: "Updated",
          description: "Trimmed",
          sort_order: 5,
          created_at: "2025-01-01T00:00:00.000Z",
        },
        error: null,
      });

      const response = await PATCH(
        mockRequest({ name: " Updated ", description: " Trimmed " }),
        mockParams(validParams),
      );
      expect(response.status).toBe(200);
      const json = await response.json();
      expect(json.group).toMatchObject({
        name: "Updated",
        description: "Trimmed",
      });
      expect(groupBuilder.update).toHaveBeenCalled();
    });

    it("returns 400 for invalid IDs", async () => {
      const response = await PATCH(mockRequest({ name: "Test" }), mockParams({ projectId: "bad", groupId: "bad" }));
      expect(response.status).toBe(400);
    });

    it("returns 400 when no valid fields provided", async () => {
      const response = await PATCH(mockRequest({}), mockParams(validParams));
      expect(response.status).toBe(400);
    });

    it("returns 401 when session missing", async () => {
      supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session: null } });
      const response = await PATCH(mockRequest({ name: "Ok" }), mockParams(validParams));
      expect(response.status).toBe(401);
    });

    it("returns 403 when org metadata missing", async () => {
      const session = buildSession({ orgId: null });
      supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session } });
      const response = await PATCH(mockRequest({ name: "Ok" }), mockParams(validParams));
      expect(response.status).toBe(403);
    });

    it("returns 404 when project not found", async () => {
      const projectBuilder = supabaseMock.getBuilder("composer_projects");
      projectBuilder.single.mockResolvedValue({ data: null, error: { message: "Not found" } });
      const response = await PATCH(mockRequest({ name: "Ok" }), mockParams(validParams));
      expect(response.status).toBe(404);
    });

    it("returns 404 when group update misses", async () => {
      const groupBuilder = supabaseMock.getBuilder("composer_sku_groups");
      groupBuilder.single.mockResolvedValue({
        data: null,
        error: { message: "Group missing", code: "PGRST116" },
      });
      const response = await PATCH(mockRequest({ name: "Ok" }), mockParams(validParams));
      expect(response.status).toBe(404);
    });

    it("returns 500 when update fails unexpectedly", async () => {
      const groupBuilder = supabaseMock.getBuilder("composer_sku_groups");
      groupBuilder.single.mockResolvedValue({
        data: null,
        error: { message: "DB failure" },
      });
      const response = await PATCH(mockRequest({ name: "Ok" }), mockParams(validParams));
      expect(response.status).toBe(500);
    });
  });

  describe("DELETE", () => {
    const validParams = {
      projectId: "123e4567-e89b-12d3-a456-426614174000",
      groupId: "123e4567-e89b-12d3-a456-426614174111",
    };

    beforeEach(() => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session } });
      const projectBuilder = supabaseMock.getBuilder("composer_projects");
      projectBuilder.single.mockResolvedValue({ data: { id: validParams.projectId }, error: null });
    });

    it("deletes a group when no SKUs are assigned", async () => {
      const variantsBuilder = supabaseMock.getBuilder("composer_sku_variants");
      variantsBuilder.__pushResponse({ data: null, error: null, count: 0 });

      const groupsBuilder = supabaseMock.getBuilder("composer_sku_groups");
      groupsBuilder.eq
        .mockImplementationOnce(() => groupsBuilder)
        .mockImplementationOnce(() => groupsBuilder)
        .mockImplementationOnce(() => Promise.resolve({ error: null }));

      const response = await DELETE({} as NextRequest, mockParams(validParams));
      expect(response.status).toBe(200);
    });

    it("returns 400 when SKUs are still assigned", async () => {
      const variantsBuilder = supabaseMock.getBuilder("composer_sku_variants");
      variantsBuilder.__pushResponse({ data: null, error: null, count: 3 });

      const response = await DELETE({} as NextRequest, mockParams(validParams));
      expect(response.status).toBe(400);
    });

    it("returns 400 for invalid IDs", async () => {
      const response = await DELETE({} as NextRequest, mockParams({ projectId: "bad", groupId: "bad" }));
      expect(response.status).toBe(400);
    });

    it("returns 401 when session missing", async () => {
      supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session: null } });
      const response = await DELETE({} as NextRequest, mockParams(validParams));
      expect(response.status).toBe(401);
    });

    it("returns 403 when org metadata missing", async () => {
      const session = buildSession({ orgId: null });
      supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session } });
      const response = await DELETE({} as NextRequest, mockParams(validParams));
      expect(response.status).toBe(403);
    });

    it("returns 404 when project not found", async () => {
      const projectBuilder = supabaseMock.getBuilder("composer_projects");
      projectBuilder.single.mockResolvedValue({ data: null, error: { message: "Not found" } });
      const response = await DELETE({} as NextRequest, mockParams(validParams));
      expect(response.status).toBe(404);
    });

    it("returns 500 when delete fails", async () => {
      const variantsBuilder = supabaseMock.getBuilder("composer_sku_variants");
      variantsBuilder.__pushResponse({ data: null, error: null, count: 0 });

      const groupsBuilder = supabaseMock.getBuilder("composer_sku_groups");
      groupsBuilder.eq
        .mockImplementationOnce(() => groupsBuilder)
        .mockImplementationOnce(() => groupsBuilder)
        .mockImplementationOnce(() => Promise.resolve({ error: { message: "DB error" } }));

      const response = await DELETE({} as NextRequest, mockParams(validParams));
      expect(response.status).toBe(500);
    });
  });
});
