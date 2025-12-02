import { describe, it, expect, beforeEach, vi } from "vitest";
import type { NextRequest } from "next/server";
import { GET } from "./route";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { createSupabaseClientMock, type SupabaseClientMock } from "@/lib/composer/testSupabaseClient";

vi.mock("@/lib/supabase/serverClient", () => ({
  createSupabaseRouteClient: vi.fn(),
}));

const mockParams = (params: Record<string, string | undefined>) => ({
  params: Promise.resolve(params),
});

const mockRequest = () =>
  ({
    json: vi.fn(),
    url: "http://localhost",
  }) as unknown as NextRequest;

describe("scribe jobs GET", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(supabaseMock.supabase);
  });

  it("rejects unauthenticated", async () => {
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session: null } });
    const res = await GET(mockRequest(), mockParams({ jobId: "123e4567-e89b-12d3-a456-426614174000" }));
    expect(res.status).toBe(401);
  });

  it("forbids access to jobs from another user", async () => {
    const jobId = "123e4567-e89b-12d3-a456-426614174000";
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    // Job fetch
    const jobs = supabaseMock.getBuilder("scribe_generation_jobs");
    jobs.__pushResponse({
      data: {
        id: jobId,
        project_id: "proj-1",
        job_type: "topics",
        status: "queued",
        payload: { projectId: "proj-1" },
        error_message: null,
        created_at: "2025-11-27T00:00:00Z",
        completed_at: null,
      },
      error: null,
    });

    // Project ownership check (different user)
    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: null,
      error: { message: "not found", code: "PGRST116" },
    });

    const res = await GET(mockRequest(), mockParams({ jobId }));
    expect(res.status).toBe(403);
  });

  it("returns job when owned by user", async () => {
    const jobId = "123e4567-e89b-12d3-a456-426614174000";
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const jobs = supabaseMock.getBuilder("scribe_generation_jobs");
    jobs.__pushResponse({
      data: {
        id: jobId,
        project_id: "proj-1",
        job_type: "topics",
        status: "succeeded",
        payload: { projectId: "proj-1" },
        error_message: null,
        created_at: "2025-11-27T00:00:00Z",
        completed_at: "2025-11-27T01:00:00Z",
      },
      error: null,
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: "proj-1", created_by: "user-1" },
      error: null,
    });

    const res = await GET(mockRequest(), mockParams({ jobId }));
    const json = await res.json();
    expect(res.status).toBe(200);
    expect(json.id).toBe(jobId);
    expect(json.status).toBe("succeeded");
    expect(json.projectId).toBe("proj-1");
  });
});
