import { describe, it, expect, beforeEach, vi } from "vitest";
import type { NextRequest } from "next/server";
import { POST } from "./route";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { createSupabaseClientMock, type SupabaseClientMock } from "@/lib/composer/testSupabaseClient";

vi.mock("@/lib/supabase/serverClient", () => ({
  createSupabaseRouteClient: vi.fn(),
}));

vi.mock("@/lib/scribe/jobProcessor", () => ({
  processCopyJob: vi.fn(() => Promise.resolve()),
}));

const mockParams = (params: Record<string, string | undefined>) => ({
  params: Promise.resolve(params),
});

const mockRequest = (body?: unknown) =>
  ({
    json: vi.fn().mockResolvedValue(body || {}),
    url: "http://localhost",
  }) as unknown as NextRequest;

describe("POST /projects/:id/skus/:skuId/regenerate-copy", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(supabaseMock.supabase);
  });

  it("rejects section-scoped regenerate (not implemented in v1)", async () => {
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "456e4567-e89b-12d3-a456-426614174000";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const res = await POST(
      mockRequest({ sections: ["title", "bullets"] }),
      mockParams({ projectId, skuId })
    );
    const json = await res.json();

    expect(res.status).toBe(400);
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain("Section-scoped regenerate not supported yet");
  });

  it.skip("rejects when project is not stage_b_approved or stage_c_approved", async () => {
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "456e4567-e89b-12d3-a456-426614174000";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: projectId, status: "stage_a_approved", created_by: "user-1" },
      error: null,
    });

    const res = await POST(mockRequest({}), mockParams({ projectId, skuId }));
    const json = await res.json();

    expect(res.status).toBe(400);
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain("Stage B must be approved");
  });

  it("rejects when SKU has != 5 approved topics", async () => {
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "456e4567-e89b-12d3-a456-426614174000";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: projectId, status: "stage_b_approved", created_by: "user-1" },
      error: null,
    });

    const skus = supabaseMock.getBuilder("scribe_skus");
    skus.__pushResponse({
      data: { id: skuId },
      error: null,
    });

    const topics = supabaseMock.getBuilder("scribe_topics");
    topics.__pushResponse({
      data: null,
      error: null,
      count: 3, // Only 3 approved topics
    });

    const res = await POST(mockRequest({}), mockParams({ projectId, skuId }));
    const json = await res.json();

    expect(res.status).toBe(400);
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain("exactly 5 approved topics");
  });

  it("creates job when project is stage_b_approved and SKU has 5 topics", async () => {
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "456e4567-e89b-12d3-a456-426614174000";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: projectId, status: "stage_b_approved", created_by: "user-1" },
      error: null,
    });

    const skus = supabaseMock.getBuilder("scribe_skus");
    skus.__pushResponse({
      data: { id: skuId },
      error: null,
    });

    const topics = supabaseMock.getBuilder("scribe_topics");
    topics.__pushResponse({
      data: null,
      error: null,
      count: 5,
    });

    const jobs = supabaseMock.getBuilder("scribe_generation_jobs");
    jobs.__pushResponse({
      data: { id: "job-123" },
      error: null,
    });

    const res = await POST(mockRequest({}), mockParams({ projectId, skuId }));
    const json = await res.json();

    expect(res.status).toBe(200);
    expect(json.jobId).toBe("job-123");
  });

  it("allows regenerate when project is stage_c_approved", async () => {
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "456e4567-e89b-12d3-a456-426614174000";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: projectId, status: "stage_c_approved", created_by: "user-1" },
      error: null,
    });

    const skus = supabaseMock.getBuilder("scribe_skus");
    skus.__pushResponse({
      data: { id: skuId },
      error: null,
    });

    const topics = supabaseMock.getBuilder("scribe_topics");
    topics.__pushResponse({
      data: null,
      error: null,
      count: 5,
    });

    const jobs = supabaseMock.getBuilder("scribe_generation_jobs");
    jobs.__pushResponse({
      data: { id: "job-456" },
      error: null,
    });

    const res = await POST(mockRequest({}), mockParams({ projectId, skuId }));
    const json = await res.json();

    expect(res.status).toBe(200);
    expect(json.jobId).toBe("job-456");
  });
});
