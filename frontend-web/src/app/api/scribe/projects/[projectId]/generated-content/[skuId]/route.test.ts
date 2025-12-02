import { describe, it, expect, beforeEach, vi } from "vitest";
import type { NextRequest } from "next/server";
import { GET, PATCH } from "./route";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { createSupabaseClientMock, type SupabaseClientMock } from "@/lib/composer/testSupabaseClient";

vi.mock("@/lib/supabase/serverClient", () => ({
  createSupabaseRouteClient: vi.fn(),
}));

const mockParams = (params: Record<string, string | undefined>) => ({
  params: Promise.resolve(params),
});

const mockRequest = (body: unknown) =>
  ({
    json: vi.fn().mockResolvedValue(body),
    url: "http://localhost",
  }) as unknown as NextRequest;

const mockGetRequest = () =>
  ({
    url: "http://localhost",
  }) as unknown as NextRequest;

describe("GET /projects/:id/generated-content/:skuId", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(supabaseMock.supabase);
  });

  it("rejects unauthenticated requests", async () => {
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session: null } });

    const res = await GET(
      mockGetRequest(),
      mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000", skuId: "456e4567-e89b-12d3-a456-426614174000" }),
    );

    const json = await res.json();
    expect(res.status).toBe(401);
    expect(json.error.code).toBe("unauthorized");
  });

  it("returns 404 when project not found", async () => {
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "456e4567-e89b-12d3-a456-426614174000";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: null,
      error: { code: "PGRST116", message: "Not found" },
    });

    const res = await GET(mockGetRequest(), mockParams({ projectId, skuId }));
    const json = await res.json();

    expect(res.status).toBe(404);
    expect(json.error.code).toBe("not_found");
  });

  it("returns 404 when content not found", async () => {
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

    const content = supabaseMock.getBuilder("scribe_generated_content");
    content.__pushResponse({
      data: null,
      error: { code: "PGRST116", message: "Not found" },
    });

    const res = await GET(mockGetRequest(), mockParams({ projectId, skuId }));
    const json = await res.json();

    expect(res.status).toBe(404);
    expect(json.error.code).toBe("not_found");
    expect(json.error.message).toContain("Generated content not found");
  });

  it("returns content payload with bullets array for owner", async () => {
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

    const content = supabaseMock.getBuilder("scribe_generated_content");
    content.__pushResponse({
      data: {
        id: "content-123",
        project_id: projectId,
        sku_id: skuId,
        version: 1,
        title: "Amazing Product Title",
        bullets: ["Bullet 1", "Bullet 2", "Bullet 3", "Bullet 4", "Bullet 5"],
        description: "This is a great product description.",
        backend_keywords: "keyword1 keyword2 keyword3",
        model_used: "gpt-4",
        prompt_version: "scribe_stage_c_v1",
        approved: false,
        approved_at: null,
        created_at: "2025-11-27T00:00:00Z",
        updated_at: "2025-11-27T00:00:00Z",
      },
      error: null,
    });

    const res = await GET(mockGetRequest(), mockParams({ projectId, skuId }));
    const json = await res.json();

    expect(res.status).toBe(200);
    expect(json.id).toBe("content-123");
    expect(json.version).toBe(1);
    expect(json.title).toBe("Amazing Product Title");
    expect(json.bullets).toHaveLength(5);
    expect(json.bullets[0]).toBe("Bullet 1");
    expect(json.description).toBe("This is a great product description.");
    expect(json.backendKeywords).toBe("keyword1 keyword2 keyword3");
    expect(json.modelUsed).toBe("gpt-4");
    expect(json.promptVersion).toBe("scribe_stage_c_v1");
    expect(json.approved).toBe(false);
    expect(json.approvedAt).toBeNull();
    expect(json.createdAt).toBe("2025-11-27T00:00:00Z");
    expect(json.updatedAt).toBe("2025-11-27T00:00:00Z");
  });

  it("allows reading when project is archived (read-only)", async () => {
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "456e4567-e89b-12d3-a456-426614174000";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: projectId, status: "archived", created_by: "user-1" },
      error: null,
    });

    const content = supabaseMock.getBuilder("scribe_generated_content");
    content.__pushResponse({
      data: {
        id: "content-123",
        project_id: projectId,
        sku_id: skuId,
        version: 1,
        title: "Archived Product Title",
        bullets: ["B1", "B2", "B3", "B4", "B5"],
        description: "Archived description",
        backend_keywords: "keywords",
        model_used: null,
        prompt_version: null,
        approved: true,
        approved_at: "2025-11-26T00:00:00Z",
        created_at: "2025-11-27T00:00:00Z",
        updated_at: "2025-11-27T00:00:00Z",
      },
      error: null,
    });

    const res = await GET(mockGetRequest(), mockParams({ projectId, skuId }));
    const json = await res.json();

    expect(res.status).toBe(200);
    expect(json.title).toBe("Archived Product Title");
  });
});

describe("PATCH /projects/:id/generated-content/:skuId (gate tests)", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(supabaseMock.supabase);
  });

  it("rejects when project is not stage_b_approved or stage_c_approved", async () => {
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

    const res = await PATCH(
      mockRequest({ title: "New Title" }),
      mockParams({ projectId, skuId })
    );
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
      count: 4, // Only 4 approved topics
    });

    const res = await PATCH(
      mockRequest({ title: "New Title" }),
      mockParams({ projectId, skuId })
    );
    const json = await res.json();

    expect(res.status).toBe(400);
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain("exactly 5 approved topics");
  });

  it("rejects when bullets are not exactly 5", async () => {
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

    const res = await PATCH(
      mockRequest({ bullets: ["B1", "B2", "B3"] }), // Only 3 bullets
      mockParams({ projectId, skuId })
    );
    const json = await res.json();

    expect(res.status).toBe(400);
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain("Bullets must be exactly 5 items");
  });

  it("rejects when title exceeds 200 characters", async () => {
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

    const longTitle = "A".repeat(201);
    const res = await PATCH(
      mockRequest({ title: longTitle }),
      mockParams({ projectId, skuId })
    );
    const json = await res.json();

    expect(res.status).toBe(400);
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain("Title must not exceed 200 characters");
  });
});
