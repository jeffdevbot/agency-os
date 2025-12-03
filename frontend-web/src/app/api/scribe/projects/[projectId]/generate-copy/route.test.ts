import { describe, it, expect, beforeEach, vi } from "vitest";
import type { NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { createSupabaseClientMock, type SupabaseClientMock } from "@/lib/composer/testSupabaseClient";
import { POST } from "./route";

vi.mock("@/lib/supabase/serverClient", () => ({
  createSupabaseRouteClient: vi.fn(),
}));

vi.mock("@/lib/scribe/jobProcessor", () => ({
  processCopyJob: vi.fn(() => Promise.resolve()),
}));

const mockParams = (params: Record<string, string | undefined>) => ({
  params: Promise.resolve(params),
});

const mockRequest = (body: unknown) =>
  ({
    json: vi.fn().mockResolvedValue(body),
  }) as unknown as NextRequest;

describe("generate-copy route", () => {
  let supabaseMock: SupabaseClientMock;
  const projectId = "11111111-1111-4111-8111-111111111111";

  beforeEach(() => {
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as unknown as vi.Mock).mockResolvedValue(supabaseMock.supabase);
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session: { user: { id: "user-1" } } } });
  });

  it("validates project ownership and inserts job for provided SKUs", async () => {
    // project ownership
    supabaseMock.getBuilder("scribe_projects").__pushResponse({
      data: { id: projectId, created_by: "user-1" },
      error: null,
    });
    // provided skus exist
    supabaseMock.getBuilder("scribe_skus").__pushResponse({
      data: [{ id: "sku-1" }, { id: "sku-2" }],
      error: null,
    });
    // topic counts per target SKU
    supabaseMock.getBuilder("scribe_topics").__pushResponse({ data: null, error: null, count: 5 });
    supabaseMock.getBuilder("scribe_topics").__pushResponse({ data: null, error: null, count: 5 });
    // insert job response
    supabaseMock.getBuilder("scribe_generation_jobs").__pushResponse({
      data: { id: "job-123" },
      error: null,
    });

    const res = await POST(
      mockRequest({ mode: "all", skuIds: ["sku-1", "sku-2"] }),
      mockParams({ projectId }),
    );

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.jobId).toBe("job-123");
    expect(supabaseMock.getBuilder("scribe_generation_jobs").insert).toHaveBeenCalledWith(
      expect.objectContaining({
        project_id: projectId,
        job_type: "copy",
        status: "queued",
        payload: expect.objectContaining({ skuIds: ["sku-1", "sku-2"] }),
      }),
    );
  });

  it("ignores unexpected mode and still generates when data is valid", async () => {
    supabaseMock.getBuilder("scribe_projects").__pushResponse({
      data: { id: projectId, created_by: "user-1" },
      error: null,
    });
    supabaseMock.getBuilder("scribe_skus").__pushResponse({
      data: [{ id: "sku-1" }],
      error: null,
    });
    supabaseMock.getBuilder("scribe_topics").__pushResponse({ data: null, error: null, count: 5 });
    supabaseMock.getBuilder("scribe_generation_jobs").__pushResponse({
      data: { id: "job-999" },
      error: null,
    });

    const res = await POST(
      mockRequest({ mode: "weird", skuIds: ["sku-1"] }),
      mockParams({ projectId }),
    );

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.jobId).toBe("job-999");
  });
});
