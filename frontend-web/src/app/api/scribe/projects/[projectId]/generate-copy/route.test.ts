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

/**
 * Stage C Gate Tests
 *
 * Purpose: Verify that Stage C copy generation endpoint (generate-copy) correctly enforces
 * the gate requirement that all SKUs must have exactly 5 approved topics before copy can be generated.
 *
 * Test Coverage:
 * - Reject when project status is not stage_b_approved
 * - Reject when any SKU has 0 approved topics
 * - Reject when any SKU has <5 approved topics (e.g., 4)
 * - Reject when mixed SKU approval counts (some SKUs have 5, others have <5)
 * - Accept when all SKUs have exactly 5 approved topics
 * - Accept when project status is stage_c_approved (regeneration allowed)
 */
describe("generate-copy API (Stage C gate)", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(supabaseMock.supabase);
  });

  it("rejects unauthenticated requests", async () => {
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session: null } });

    const res = await POST(
      mockRequest({}),
      mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" })
    );

    const json = await res.json();
    expect(res.status).toBe(401);
    expect(json.error.code).toBe("unauthorized");
  });

  it("rejects when project status is draft (not stage_b_approved)", async () => {
    const validProjectId = "123e4567-e89b-12d3-a456-426614174000";
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: validProjectId, status: "draft", created_by: "user-1" },
      error: null,
    });

    const res = await POST(mockRequest({}), mockParams({ projectId: validProjectId }));
    const json = await res.json();

    expect(res.status).toBe(400);
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain("Stage B must be approved");
  });

  it("rejects when project status is stage_a_approved (not stage_b_approved)", async () => {
    const validProjectId = "123e4567-e89b-12d3-a456-426614174000";
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: validProjectId, status: "stage_a_approved", created_by: "user-1" },
      error: null,
    });

    const res = await POST(mockRequest({}), mockParams({ projectId: validProjectId }));
    const json = await res.json();

    expect(res.status).toBe(400);
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain("Stage B must be approved");
  });

  it("rejects when SKU has 0 approved topics", async () => {
    const validProjectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "sku-123";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: validProjectId, status: "stage_b_approved", created_by: "user-1" },
      error: null,
    });

    const skus = supabaseMock.getBuilder("scribe_skus");
    skus.__pushResponse({
      data: [{ id: skuId }],
      error: null,
    });

    const topics = supabaseMock.getBuilder("scribe_topics");
    topics.__pushResponse({
      data: null,
      error: null,
      count: 0, // 0 approved topics
    });

    const res = await POST(mockRequest({}), mockParams({ projectId: validProjectId }));
    const json = await res.json();

    expect(res.status).toBe(400);
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain("exactly 5 approved topics");
  });

  it("rejects when SKU has 4 approved topics (less than 5)", async () => {
    const validProjectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "sku-123";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: validProjectId, status: "stage_b_approved", created_by: "user-1" },
      error: null,
    });

    const skus = supabaseMock.getBuilder("scribe_skus");
    skus.__pushResponse({
      data: [{ id: skuId }],
      error: null,
    });

    const topics = supabaseMock.getBuilder("scribe_topics");
    topics.__pushResponse({
      data: null,
      error: null,
      count: 4, // Only 4 approved topics
    });

    const res = await POST(mockRequest({}), mockParams({ projectId: validProjectId }));
    const json = await res.json();

    expect(res.status).toBe(400);
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain("exactly 5 approved topics");
  });

  it("rejects when mixed SKU approval counts (SKU A has 5, SKU B has 3)", async () => {
    const validProjectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuIdA = "sku-a";
    const skuIdB = "sku-b";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: validProjectId, status: "stage_b_approved", created_by: "user-1" },
      error: null,
    });

    const skus = supabaseMock.getBuilder("scribe_skus");
    skus.__pushResponse({
      data: [{ id: skuIdA }, { id: skuIdB }],
      error: null,
    });

    const topics = supabaseMock.getBuilder("scribe_topics");
    // First SKU has 5 approved topics
    topics.__pushResponse({
      data: null,
      error: null,
      count: 5,
    });
    // Second SKU has only 3 approved topics
    topics.__pushResponse({
      data: null,
      error: null,
      count: 3,
    });

    const res = await POST(mockRequest({}), mockParams({ projectId: validProjectId }));
    const json = await res.json();

    expect(res.status).toBe(400);
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain("exactly 5 approved topics");
  });

  it("accepts when all SKUs have exactly 5 approved topics", async () => {
    const validProjectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuIdA = "sku-a";
    const skuIdB = "sku-b";
    const skuIdC = "sku-c";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: validProjectId, status: "stage_b_approved", created_by: "user-1" },
      error: null,
    });

    const skus = supabaseMock.getBuilder("scribe_skus");
    skus.__pushResponse({
      data: [{ id: skuIdA }, { id: skuIdB }, { id: skuIdC }],
      error: null,
    });

    const topics = supabaseMock.getBuilder("scribe_topics");
    // All three SKUs have exactly 5 approved topics
    topics.__pushResponse({ data: null, error: null, count: 5 });
    topics.__pushResponse({ data: null, error: null, count: 5 });
    topics.__pushResponse({ data: null, error: null, count: 5 });

    // Create job
    const jobs = supabaseMock.getBuilder("scribe_generation_jobs");
    jobs.__pushResponse({
      data: { id: "job-123" },
      error: null,
    });

    const res = await POST(mockRequest({}), mockParams({ projectId: validProjectId }));
    const json = await res.json();

    expect(res.status).toBe(200);
    expect(json.jobId).toBe("job-123");
  });

  it("accepts when project status is stage_c_approved (regeneration allowed)", async () => {
    const validProjectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "sku-123";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: validProjectId, status: "stage_c_approved", created_by: "user-1" },
      error: null,
    });

    const skus = supabaseMock.getBuilder("scribe_skus");
    skus.__pushResponse({
      data: [{ id: skuId }],
      error: null,
    });

    const topics = supabaseMock.getBuilder("scribe_topics");
    topics.__pushResponse({
      data: null,
      error: null,
      count: 5,
    });

    // Create job
    const jobs = supabaseMock.getBuilder("scribe_generation_jobs");
    jobs.__pushResponse({
      data: { id: "job-456" },
      error: null,
    });

    const res = await POST(mockRequest({}), mockParams({ projectId: validProjectId }));
    const json = await res.json();

    expect(res.status).toBe(200);
    expect(json.jobId).toBe("job-456");
  });

  it("rejects when project has no SKUs", async () => {
    const validProjectId = "123e4567-e89b-12d3-a456-426614174000";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: validProjectId, status: "stage_b_approved", created_by: "user-1" },
      error: null,
    });

    const skus = supabaseMock.getBuilder("scribe_skus");
    skus.__pushResponse({
      data: [],
      error: null,
    });

    const res = await POST(mockRequest({}), mockParams({ projectId: validProjectId }));
    const json = await res.json();

    expect(res.status).toBe(400);
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain("No SKUs found");
  });
});
