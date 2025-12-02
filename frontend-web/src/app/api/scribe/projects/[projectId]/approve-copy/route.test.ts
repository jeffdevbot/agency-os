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

describe("POST /projects/:id/approve-copy (Stage C approval)", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(supabaseMock.supabase);
  });

  it("rejects when project is not stage_b_approved or stage_c_approved", async () => {
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: projectId, status: "stage_a_approved", created_by: "user-1" },
      error: null,
    });

    const res = await POST(mockRequest(), mockParams({ projectId }));
    const json = await res.json();

    expect(res.status).toBe(400);
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain("Stage B must be approved");
  });

  it("rejects when any SKU lacks generated content", async () => {
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
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
      data: [{ id: "sku-1" }, { id: "sku-2" }],
      error: null,
    });

    const content = supabaseMock.getBuilder("scribe_generated_content");
    // First SKU has content
    content.__pushResponse({
      data: { id: "content-1" },
      error: null,
    });
    // Second SKU missing content
    content.__pushResponse({
      data: null,
      error: { code: "PGRST116" },
    });

    const res = await POST(mockRequest(), mockParams({ projectId }));
    const json = await res.json();

    expect(res.status).toBe(400);
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain("All SKUs must have generated content");
  });

  it("approves when project is stage_b_approved and all SKUs have content", async () => {
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
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
      data: [{ id: "sku-1" }, { id: "sku-2" }],
      error: null,
    });

    const content = supabaseMock.getBuilder("scribe_generated_content");
    content.__pushResponse({
      data: { id: "content-1" },
      error: null,
    });
    content.__pushResponse({
      data: { id: "content-2" },
      error: null,
    });

    // Update project status
    projects.__pushResponse({
      data: { id: projectId, name: "Test", status: "stage_c_approved", updated_at: "2025-11-27T00:00:00Z" },
      error: null,
    });

    const res = await POST(mockRequest(), mockParams({ projectId }));
    const json = await res.json();

    expect(res.status).toBe(200);
    expect(json.status).toBe("stage_c_approved");
  });

  it("allows approval when project is already stage_c_approved", async () => {
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
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
      data: [{ id: "sku-1" }],
      error: null,
    });

    const content = supabaseMock.getBuilder("scribe_generated_content");
    content.__pushResponse({
      data: { id: "content-1" },
      error: null,
    });

    // Update project status (re-approval)
    projects.__pushResponse({
      data: { id: projectId, name: "Test", status: "stage_c_approved", updated_at: "2025-11-27T00:00:00Z" },
      error: null,
    });

    const res = await POST(mockRequest(), mockParams({ projectId }));
    const json = await res.json();

    expect(res.status).toBe(200);
    expect(json.status).toBe("stage_c_approved");
  });
});
