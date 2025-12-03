import { describe, it, expect, beforeEach, vi } from "vitest";
import type { NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { createSupabaseClientMock, type SupabaseClientMock } from "@/lib/composer/testSupabaseClient";
import { GET } from "./route";

vi.mock("@/lib/supabase/serverClient", () => ({
  createSupabaseRouteClient: vi.fn(),
}));

const mockParams = (params: Record<string, string | undefined>) => ({
  params: Promise.resolve(params),
});

const mockRequest = () => ({ url: "http://localhost" }) as unknown as NextRequest;

describe("export-copy route", () => {
  let supabaseMock: SupabaseClientMock;
  const projectId = "11111111-1111-4111-8111-111111111111";

  beforeEach(() => {
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as unknown as vi.Mock).mockResolvedValue(supabaseMock.supabase);
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session: { user: { id: "user-1" } } } });
  });

  it("returns CSV with dynamic attributes, padded bullets, and cleaned backend keywords", async () => {
    // project
    supabaseMock.getBuilder("scribe_projects").__pushResponse({
      data: { id: projectId, name: "My Project Name", created_by: "user-1" },
      error: null,
    });
    // skus
    supabaseMock.getBuilder("scribe_skus").__pushResponse({
      data: [
        { id: "sku-1", sku_code: "SKU-001", product_name: "Prod One", asin: "B00TEST", sort_order: 1 },
        { id: "sku-2", sku_code: "SKU-002", product_name: "Prod Two", asin: null, sort_order: 2 },
      ],
      error: null,
    });
    // variant attributes
    supabaseMock.getBuilder("scribe_variant_attributes").__pushResponse({
      data: [{ id: "attr-1", name: "Size", sort_order: 1 }],
      error: null,
    });
    // variant values
    supabaseMock.getBuilder("scribe_sku_variant_values").__pushResponse({
      data: [
        { sku_id: "sku-1", attribute_id: "attr-1", value: "Large" },
        { sku_id: "sku-2", attribute_id: "attr-1", value: "Small" },
      ],
      error: null,
    });
    // generated content
    supabaseMock.getBuilder("scribe_generated_content").__pushResponse({
      data: [
        {
          sku_id: "sku-1",
          title: "Title 1",
          bullets: ["b1", "b2"],
          description: "Desc 1",
          backend_keywords: "red, shoes  comfy",
        },
        // sku-2 intentionally omitted to ensure empty content rows are handled
      ],
      error: null,
    });

    const response = await GET(mockRequest(), mockParams({ projectId }));
    expect(response.status).toBe(200);
    const contentDisposition = response.headers.get("Content-Disposition") || "";
    expect(contentDisposition).toContain(`scribe_my-project-name_amazon_content_`);
    const csvText = await response.text();
    const cleaned = csvText.replace(/^\uFEFF/, "");
    const lines = cleaned.trim().split("\n");

    expect(lines[0]).toBe(
      `"SKU","Product Name","ASIN","Size","Product Title","Bullet Point 1","Bullet Point 2","Bullet Point 3","Bullet Point 4","Bullet Point 5","Description","Backend Keywords"`,
    );

    // sku-1 row has values and cleaned backend keywords (commas removed, spaces collapsed)
    expect(lines[1]).toContain(`"SKU-001"`);
    expect(lines[1]).toContain(`"Prod One"`);
    expect(lines[1]).toContain(`"B00TEST"`);
    expect(lines[1]).toContain(`"Large"`);
    expect(lines[1]).toContain(`"Title 1"`);
    expect(lines[1]).toContain(`"b1"`);
    expect(lines[1]).toContain(`"b2"`);
    expect(lines[1]).toContain(`""`); // padded bullets / empty slots
    expect(lines[1]).toContain(`"Desc 1"`);
    expect(lines[1]).toContain(`"red shoes comfy"`);

    // sku-2 row exists with empty copy fields and its variant value
    expect(lines[2]).toContain(`"SKU-002"`);
    expect(lines[2]).toContain(`"Prod Two"`);
    expect(lines[2]).toContain(`""`); // ASIN empty
    expect(lines[2]).toContain(`"Small"`);
    expect(lines[2]).toContain(`""`); // empty title/copy fields
  });
});
