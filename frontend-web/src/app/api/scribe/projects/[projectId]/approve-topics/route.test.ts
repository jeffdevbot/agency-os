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

describe("approve topics (Stage B)", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(supabaseMock.supabase);
  });

  it("rejects when any SKU has fewer than 5 approved topics", async () => {
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    // Fetch project
    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: projectId, status: "stage_a_approved", created_by: "user-1" },
      error: null,
    });

    // SKUs
    const skus = supabaseMock.getBuilder("scribe_skus");
    skus.__pushResponse({
      data: [
        { id: "sku-1" },
        { id: "sku-2" },
      ],
      error: null,
    });

    // Topics counts: first SKU ok (5), second SKU insufficient (4)
    const topics = supabaseMock.getBuilder("scribe_topics");
    topics.__pushResponse({ data: null, error: null, count: 5 });
    topics.__pushResponse({ data: null, error: null, count: 4 });

    const res = await POST(mockRequest(), mockParams({ projectId }));
    const json = await res.json();
    expect(res.status).toBe(400);
    expect(json.error.code).toBe("validation_error");
  });

  it("approves when every SKU has exactly 5 approved topics", async () => {
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    // Fetch project
    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: projectId, status: "stage_a_approved", created_by: "user-1" },
      error: null,
    });

    // SKUs
    const skus = supabaseMock.getBuilder("scribe_skus");
    skus.__pushResponse({
      data: [
        { id: "sku-1" },
        { id: "sku-2" },
      ],
      error: null,
    });

    // Topics counts: both SKUs at 5
    const topics = supabaseMock.getBuilder("scribe_topics");
    topics.__pushResponse({ data: null, error: null, count: 5 });
    topics.__pushResponse({ data: null, error: null, count: 5 });

    // Update project status
    projects.__pushResponse({
      data: { id: projectId, name: "Proj", status: "stage_b_approved", updated_at: "2025-11-27T00:00:00Z" },
      error: null,
    });

    const res = await POST(mockRequest(), mockParams({ projectId }));
    const json = await res.json();
    expect(res.status).toBe(200);
    expect(json.status).toBe("stage_b_approved");
  });
});
