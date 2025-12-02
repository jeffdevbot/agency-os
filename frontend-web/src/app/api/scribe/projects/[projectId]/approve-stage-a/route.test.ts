import { describe, it, expect, beforeEach, vi } from "vitest";
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

const mockRequest = () =>
  ({
    json: vi.fn(),
    url: "http://localhost",
  }) as unknown as NextRequest;

describe("approve stage A", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(supabaseMock.supabase);
  });

  it("rejects when no SKUs", async () => {
    const validProjectId = "123e4567-e89b-12d3-a456-426614174000";
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });
    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: validProjectId, status: "draft", created_by: "user-1" },
      error: null,
    });
    const skus = supabaseMock.getBuilder("scribe_skus");
    skus.__pushResponse({ data: null, error: null, count: 0 });

    const res = await POST(mockRequest(), mockParams({ projectId: validProjectId }));
    const json = await res.json();
    expect(res.status).toBe(400);
    expect(json.error.code).toBe("validation_error");
  });

  it("approves when SKUs exist", async () => {
    const validProjectId = "123e4567-e89b-12d3-a456-426614174000";
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });
    const projects = supabaseMock.getBuilder("scribe_projects");
    // First call: fetch project
    projects.__pushResponse({
      data: { id: validProjectId, status: "draft", created_by: "user-1" },
      error: null,
    });
    const skus = supabaseMock.getBuilder("scribe_skus");
    // Second call: count SKUs
    skus.__pushResponse({ data: null, error: null, count: 1 });
    // Third call: update project status
    projects.__pushResponse({
      data: { id: validProjectId, name: "Proj", status: "stage_a_approved", updated_at: "2025-11-25T00:00:00Z" },
      error: null,
    });

    const res = await POST(mockRequest(), mockParams({ projectId: validProjectId }));
    const json = await res.json();
    expect(res.status).toBe(200);
    expect(json.status).toBe("stage_a_approved");
  });
});
