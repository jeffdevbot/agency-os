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

describe("POST /projects/:id/unapprove-topics", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(supabaseMock.supabase);
  });

  it("rejects unauthenticated", async () => {
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session: null } });
    const res = await POST(mockRequest(), mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }));
    const json = await res.json();
    expect(res.status).toBe(401);
    expect(json.error.code).toBe("unauthorized");
  });

  it("rejects if project is not stage_b_approved", async () => {
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session: { user: { id: "user-1" } } } });
    supabaseMock.getBuilder("scribe_projects").__pushResponse({
      data: { id: "proj-1", status: "stage_a_approved", created_by: "user-1" },
      error: null,
    });

    const res = await POST(mockRequest(), mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }));
    const json = await res.json();
    expect(res.status).toBe(409);
    expect(json.error.message).toContain("Cannot unapprove topics");
  });

  it("rejects if archived", async () => {
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session: { user: { id: "user-1" } } } });
    supabaseMock.getBuilder("scribe_projects").__pushResponse({
      data: { id: "proj-1", status: "archived", created_by: "user-1" },
      error: null,
    });

    const res = await POST(mockRequest(), mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }));
    const json = await res.json();
    expect(res.status).toBe(403);
    expect(json.error.code).toBe("forbidden");
  });

  it("unapproves stage B (back to stage_a_approved)", async () => {
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session: { user: { id: "user-1" } } } });
    supabaseMock.getBuilder("scribe_projects").__pushResponse({
      data: { id: "proj-1", status: "stage_b_approved", created_by: "user-1" },
      error: null,
    });
    supabaseMock.getBuilder("scribe_projects").__pushResponse({
      data: { id: "proj-1", name: "Proj", status: "stage_a_approved", updated_at: "2025-11-28T00:00:00Z" },
      error: null,
    });

    const res = await POST(mockRequest(), mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }));
    const json = await res.json();
    expect(res.status).toBe(200);
    expect(json.status).toBe("stage_a_approved");
  });
});
