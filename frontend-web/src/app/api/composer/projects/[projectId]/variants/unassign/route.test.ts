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

describe("unassign variants API", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(supabaseMock.supabase);
  });

  const validParams = { projectId: "123e4567-e89b-12d3-a456-426614174000" };
  const session = buildSession();

  const seedProject = () => {
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session } });
    const projectBuilder = supabaseMock.getBuilder("composer_projects");
    projectBuilder.single.mockResolvedValue({ data: { id: validParams.projectId }, error: null });
  };

  it("unassigns the provided variant IDs", async () => {
    seedProject();
    const variantsBuilder = supabaseMock.getBuilder("composer_sku_variants");
    variantsBuilder.update.mockReturnThis();
    variantsBuilder.in.mockReturnThis();
    variantsBuilder.eq
      .mockImplementationOnce(() => variantsBuilder)
      .mockImplementationOnce(() => Promise.resolve({ error: null }));

    const response = await POST(
      mockRequest({ variantIds: ["123e4567-e89b-12d3-a456-426614174999"] }),
      mockParams(validParams),
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ success: true, unassignedCount: 1 });
    expect(variantsBuilder.update).toHaveBeenCalledWith({ group_id: null });
  });

  it("handles empty variant ID arrays", async () => {
    seedProject();
    const response = await POST(mockRequest({ variantIds: [] }), mockParams(validParams));
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ success: true, unassignedCount: 0 });
  });

  it("returns 400 for invalid project id", async () => {
    const response = await POST(mockRequest({ variantIds: [] }), mockParams({ projectId: "bad" }));
    expect(response.status).toBe(400);
  });

  it("returns 400 when payload is invalid", async () => {
    const response = await POST(mockRequest({}), mockParams(validParams));
    expect(response.status).toBe(400);
  });

  it("returns 400 when variant IDs invalid", async () => {
    const response = await POST(mockRequest({ variantIds: ["not-uuid"] }), mockParams(validParams));
    expect(response.status).toBe(400);
  });

  it("returns 401 when session missing", async () => {
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session: null } });
    const response = await POST(mockRequest({ variantIds: [] }), mockParams(validParams));
    expect(response.status).toBe(401);
  });

  it("returns 403 when org metadata missing", async () => {
    const missingOrgSession = buildSession({ orgId: null });
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session: missingOrgSession } });
    const response = await POST(mockRequest({ variantIds: [] }), mockParams(validParams));
    expect(response.status).toBe(403);
  });

  it("returns 404 when project missing", async () => {
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session } });
    const projectBuilder = supabaseMock.getBuilder("composer_projects");
    projectBuilder.single.mockResolvedValue({ data: null, error: { message: "Not found" } });
    const response = await POST(mockRequest({ variantIds: [] }), mockParams(validParams));
    expect(response.status).toBe(404);
  });

  it("returns 500 when update fails", async () => {
    seedProject();
    const variantsBuilder = supabaseMock.getBuilder("composer_sku_variants");
    variantsBuilder.update.mockReturnThis();
    variantsBuilder.in.mockReturnThis();
    variantsBuilder.eq
      .mockImplementationOnce(() => variantsBuilder)
      .mockImplementationOnce(() => Promise.resolve({ error: { message: "DB error" } }));

    const response = await POST(
      mockRequest({ variantIds: ["123e4567-e89b-12d3-a456-426614174999"] }),
      mockParams(validParams),
    );
    expect(response.status).toBe(500);
  });
});
