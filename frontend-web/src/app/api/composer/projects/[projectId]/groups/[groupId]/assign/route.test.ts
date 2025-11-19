import { beforeEach, describe, expect, it, vi } from "vitest";
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

describe("assign group API", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(supabaseMock.supabase);
  });

  const validParams = {
    projectId: "123e4567-e89b-12d3-a456-426614174000",
    groupId: "123e4567-e89b-12d3-a456-426614174111",
  };

  const validPayload = { variantIds: ["123e4567-e89b-12d3-a456-426614174999"] };

  const seedSessionAndProject = () => {
    const session = buildSession();
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session } });
    const projectBuilder = supabaseMock.getBuilder("composer_projects");
    projectBuilder.single.mockResolvedValue({ data: { id: validParams.projectId }, error: null });

    const groupBuilder = supabaseMock.getBuilder("composer_sku_groups");
    groupBuilder.single.mockResolvedValue({ data: { id: validParams.groupId }, error: null });
  };

  it("assigns SKUs to a group", async () => {
    seedSessionAndProject();
    const variantsBuilder = supabaseMock.getBuilder("composer_sku_variants");
    variantsBuilder.update.mockReturnThis();
    variantsBuilder.in.mockReturnThis();
    variantsBuilder.eq
      .mockImplementationOnce(() => variantsBuilder)
      .mockImplementationOnce(() => Promise.resolve({ error: null }));

    const response = await POST(mockRequest(validPayload), mockParams(validParams));
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ success: true, assignedCount: 1 });
    expect(variantsBuilder.update).toHaveBeenCalledWith(
      expect.objectContaining({ group_id: validParams.groupId }),
    );
  });

  it("returns 400 when variantIds is not an array", async () => {
    const response = await POST(mockRequest({ variantIds: "oops" }), mockParams(validParams));
    expect(response.status).toBe(400);
  });

  it("returns 400 when variantIds contain invalid UUIDs", async () => {
    const response = await POST(mockRequest({ variantIds: ["bad-id"] }), mockParams(validParams));
    expect(response.status).toBe(400);
  });

  it("returns 400 for invalid path params", async () => {
    const response = await POST(mockRequest(validPayload), mockParams({ projectId: "bad", groupId: "bad" }));
    expect(response.status).toBe(400);
  });

  it("returns 401 when session missing", async () => {
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session: null } });
    const response = await POST(mockRequest(validPayload), mockParams(validParams));
    expect(response.status).toBe(401);
  });

  it("returns 403 when no org metadata", async () => {
    const session = buildSession({ orgId: null });
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session } });
    const response = await POST(mockRequest(validPayload), mockParams(validParams));
    expect(response.status).toBe(403);
  });

  it("returns 404 when project missing", async () => {
    const session = buildSession();
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session } });
    const projectBuilder = supabaseMock.getBuilder("composer_projects");
    projectBuilder.single.mockResolvedValue({ data: null, error: { message: "Not found" } });
    const response = await POST(mockRequest(validPayload), mockParams(validParams));
    expect(response.status).toBe(404);
  });

  it("returns 404 when group missing", async () => {
    const session = buildSession();
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session } });
    const projectBuilder = supabaseMock.getBuilder("composer_projects");
    projectBuilder.single.mockResolvedValue({ data: { id: validParams.projectId }, error: null });
    const groupBuilder = supabaseMock.getBuilder("composer_sku_groups");
    groupBuilder.single.mockResolvedValue({ data: null, error: { message: "Missing" } });

    const response = await POST(mockRequest(validPayload), mockParams(validParams));
    expect(response.status).toBe(404);
  });

  it("returns 500 when update fails", async () => {
    seedSessionAndProject();
    const variantsBuilder = supabaseMock.getBuilder("composer_sku_variants");
    variantsBuilder.update.mockReturnThis();
    variantsBuilder.in.mockReturnThis();
    variantsBuilder.eq
      .mockImplementationOnce(() => variantsBuilder)
      .mockImplementationOnce(() =>
        Promise.resolve({
          error: { message: "DB error" },
        }),
      );

    const response = await POST(mockRequest(validPayload), mockParams(validParams));
    expect(response.status).toBe(500);
  });
});
