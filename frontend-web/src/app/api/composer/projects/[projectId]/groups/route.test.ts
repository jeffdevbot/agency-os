import { beforeEach, describe, expect, it, vi } from "vitest";
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

describe("composer groups API", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(supabaseMock.supabase);
  });

  describe("GET", () => {
    it("returns groups for the project", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session } });

      const projectBuilder = supabaseMock.getBuilder("composer_projects");
      projectBuilder.single.mockResolvedValue({ data: { id: "proj-1" }, error: null });

      const groupsBuilder = supabaseMock.getBuilder("composer_sku_groups");
      groupsBuilder.__pushResponse({
        data: [
          {
            id: "group-1",
            organization_id: "org-1",
            project_id: "proj-1",
            name: "Group 1",
            description: "Desc",
            sort_order: 0,
            created_at: "2025-01-01T00:00:00.000Z",
          },
        ],
        error: null,
      });

      const response = await GET(
        {} as NextRequest,
        mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }),
      );
      expect(response.status).toBe(200);
      const json = await response.json();
      expect(json.groups).toEqual([
        {
          id: "group-1",
          organizationId: "org-1",
          projectId: "proj-1",
          name: "Group 1",
          description: "Desc",
          sortOrder: 0,
          createdAt: "2025-01-01T00:00:00.000Z",
        },
      ]);
    });

    it("returns 400 for invalid project id", async () => {
      const response = await GET({} as NextRequest, mockParams({ projectId: "not-a-uuid" }));
      expect(response.status).toBe(400);
    });

    it("returns 401 when session is missing", async () => {
      supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session: null } });
      const response = await GET({} as NextRequest, mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }));
      expect(response.status).toBe(401);
    });

    it("returns 403 when org metadata is missing", async () => {
      const session = buildSession({ orgId: null });
      supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session } });
      const response = await GET({} as NextRequest, mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }));
      expect(response.status).toBe(403);
    });

    it("returns 404 when project does not belong to org", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session } });
      const projectBuilder = supabaseMock.getBuilder("composer_projects");
      projectBuilder.single.mockResolvedValue({ data: null, error: { message: "Not found", code: "PGRST116" } });

      const response = await GET({} as NextRequest, mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }));
      expect(response.status).toBe(404);
    });

    it("returns 500 when group query fails", async () => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session } });
      const projectBuilder = supabaseMock.getBuilder("composer_projects");
      projectBuilder.single.mockResolvedValue({ data: { id: "proj-1" }, error: null });

      const groupsBuilder = supabaseMock.getBuilder("composer_sku_groups");
      groupsBuilder.__pushResponse({
        data: null,
        error: { message: "DB error" },
      });

      const response = await GET({} as NextRequest, mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }));
      expect(response.status).toBe(500);
    });
  });

  describe("POST", () => {
    const validPayload = { name: "New Group", description: "  Notes " };

    beforeEach(() => {
      const session = buildSession();
      supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session } });
      const projectBuilder = supabaseMock.getBuilder("composer_projects");
      projectBuilder.single.mockResolvedValue({ data: { id: "proj-1" }, error: null });
    });

    it("creates a group with incremented sort order and trimmed description", async () => {
      const groupsBuilder = supabaseMock.getBuilder("composer_sku_groups");
      groupsBuilder.__pushResponse({
        data: [{ sort_order: 2 }],
        error: null,
      });
      groupsBuilder.single.mockResolvedValue({
        data: {
          id: "group-3",
          organization_id: "org-1",
          project_id: "proj-1",
          name: "New Group",
          description: "Notes",
          sort_order: 3,
          created_at: "2025-01-01T00:00:00.000Z",
        },
        error: null,
      });

      const response = await POST(mockRequest(validPayload), mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }));
      expect(response.status).toBe(201);
      const json = await response.json();
      expect(json.group.sortOrder).toBe(3);

      expect(groupsBuilder.insert).toHaveBeenCalledWith(
        expect.objectContaining({
          description: "Notes",
          sort_order: 3,
        }),
      );
    });

    it("coerces blank descriptions to null", async () => {
      const groupsBuilder = supabaseMock.getBuilder("composer_sku_groups");
      groupsBuilder.__pushResponse({ data: [], error: null });
      groupsBuilder.single.mockResolvedValue({
        data: {
          id: "group-1",
          organization_id: "org-1",
          project_id: "proj-1",
          name: "Group",
          description: null,
          sort_order: 0,
          created_at: "2025-01-01T00:00:00.000Z",
        },
        error: null,
      });

      await POST(mockRequest({ name: "Group", description: "" }), mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }));
      expect(groupsBuilder.insert).toHaveBeenCalledWith(
        expect.objectContaining({
          description: null,
        }),
      );
    });

    it("returns 400 when name is missing", async () => {
      const response = await POST(mockRequest({ name: "" }), mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }));
      expect(response.status).toBe(400);
    });

    it("returns 401 when session missing", async () => {
      supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session: null } });
      const response = await POST(mockRequest(validPayload), mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }));
      expect(response.status).toBe(401);
    });

    it("returns 403 when org metadata missing", async () => {
      const session = buildSession({ orgId: null });
      supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session } });
      const response = await POST(mockRequest(validPayload), mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }));
      expect(response.status).toBe(403);
    });

    it("returns 404 when project not found", async () => {
      const projectBuilder = supabaseMock.getBuilder("composer_projects");
      projectBuilder.single.mockResolvedValue({ data: null, error: { message: "Not found" } });

      const response = await POST(mockRequest(validPayload), mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }));
      expect(response.status).toBe(404);
    });

    it("returns 500 when insert fails", async () => {
      const groupsBuilder = supabaseMock.getBuilder("composer_sku_groups");
      groupsBuilder.__pushResponse({ data: [], error: null });
      groupsBuilder.single.mockResolvedValue({ data: null, error: { message: "Insert failed" } });

      const response = await POST(mockRequest(validPayload), mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }));
      expect(response.status).toBe(500);
    });

    it("returns 400 for invalid project id", async () => {
      const response = await POST(mockRequest(validPayload), mockParams({ projectId: "not-a-uuid" }));
      expect(response.status).toBe(400);
    });
  });
});
