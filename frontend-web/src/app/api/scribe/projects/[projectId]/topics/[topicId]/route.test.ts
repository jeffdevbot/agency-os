import { describe, it, expect, beforeEach, vi } from "vitest";
import type { NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { createSupabaseClientMock, type SupabaseClientMock } from "@/lib/composer/testSupabaseClient";
import { PATCH } from "./route";

vi.mock("@/lib/supabase/serverClient", () => ({
  createSupabaseRouteClient: vi.fn(),
}));

const mockParams = (params: Record<string, string | undefined>) => ({
  params: Promise.resolve(params),
});

const mockRequest = (body: unknown) =>
  ({
    json: vi.fn().mockResolvedValue(body),
  }) as unknown as NextRequest;

describe("topics PATCH selection rules", () => {
  let supabaseMock: SupabaseClientMock;
  const projectId = "11111111-1111-4111-8111-111111111111";
  const topicId = "22222222-2222-4222-8222-222222222222";
  const skuId = "33333333-3333-4333-8333-333333333333";

  beforeEach(() => {
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as unknown as vi.Mock).mockResolvedValue(supabaseMock.supabase);
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session: { user: { id: "user-1" } } } });
  });

  it("rejects selecting more than 5 topics per SKU", async () => {
    // project ownership
    supabaseMock.getBuilder("scribe_projects").__pushResponse({
      data: { id: projectId, created_by: "user-1" },
      error: null,
    });
    // fetch topic
    supabaseMock.getBuilder("scribe_topics").__pushResponse({
      data: { id: topicId, sku_id: skuId, project_id: projectId },
      error: null,
    });
    // selected topics count (already 5, none is this topic)
    supabaseMock.getBuilder("scribe_topics").__pushResponse({
      data: [
        { id: "t1" },
        { id: "t2" },
        { id: "t3" },
        { id: "t4" },
        { id: "t5" },
      ],
      error: null,
    });

    const res = await PATCH(
      mockRequest({ selected: true }),
      mockParams({ projectId, topicId }),
    );

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body?.error?.message).toMatch(/Maximum 5 topics/);
  });

  it("allows selecting when already counted among the 5", async () => {
    supabaseMock.getBuilder("scribe_projects").__pushResponse({
      data: { id: projectId, created_by: "user-1" },
      error: null,
    });
    supabaseMock.getBuilder("scribe_topics").__pushResponse({
      data: { id: topicId, sku_id: skuId, project_id: projectId },
      error: null,
    });
    supabaseMock.getBuilder("scribe_topics").__pushResponse({
      data: [
        { id: "t1" },
        { id: "t2" },
        { id: "t3" },
        { id: "t4" },
        { id: topicId }, // already selected
      ],
      error: null,
    });
    supabaseMock.getBuilder("scribe_topics").__pushResponse({
      data: { id: topicId, sku_id: skuId, selected: true },
      error: null,
    });

    const res = await PATCH(
      mockRequest({ selected: true }),
      mockParams({ projectId, topicId }),
    );

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.selected).toBe(true);
    expect(body.skuId).toBe(skuId);
  });
});
