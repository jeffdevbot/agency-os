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
    url: "http://localhost",
  }) as unknown as NextRequest;

/**
 * CSV Export Tests
 *
 * Purpose: Verify that CSV export includes Stage C fields (title, bullet_1..5, description, backend_keywords)
 * and correctly handles missing content.
 *
 * Test Coverage:
 * - Validate Stage C columns are present in CSV headers
 * - Export with missing generated content (empty Stage C fields)
 * - Export with full generated content
 * - Allow export for archived projects
 * - Enforce authentication and project ownership
 */
describe("GET /projects/:id/export (Stage C fields)", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(supabaseMock.supabase);
  });

  it("keeps columns aligned when fields contain commas/newlines and variant attrs exist", async () => {
    const validProjectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "sku-123";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: validProjectId, name: "Test Project", created_by: "user-1" },
      error: null,
    });

    const skus = supabaseMock.getBuilder("scribe_skus");
    skus.__pushResponse({
      data: [
        {
          id: skuId,
          sku_code: "TEE-RED-M",
          asin: "B001",
          product_name: "Classic Crewneck Cotton T-Shirt – Red (Medium)",
          brand_tone: "Friendly, casual, approachable",
          target_audience: "Adults who want an everyday comfortable tee",
          supplied_content: "Soft mid-weight cotton.\nBreathable enough for daily wear.",
          words_to_avoid: ["cheap", "knock-off"],
          scribe_sku_variant_values: [
            {
              attribute_id: "attr-color",
              value: "Red",
              scribe_variant_attributes: { name: "color" },
            },
            {
              attribute_id: "attr-size",
              value: "Medium",
              scribe_variant_attributes: { name: "size" },
            },
          ],
        },
      ],
      error: null,
    });

    const keywords = supabaseMock.getBuilder("scribe_keywords");
    keywords.__pushResponse({
      data: [{ sku_id: skuId, keyword: "red t-shirt men" }],
      error: null,
    });

    const questions = supabaseMock.getBuilder("scribe_questions");
    questions.__pushResponse({
      data: [{ sku_id: skuId, question: "Is the fabric thick or more lightweight?" }],
      error: null,
    });

    const content = supabaseMock.getBuilder("scribe_generated_content");
    content.__pushResponse({
      data: [
        {
          sku_id: skuId,
          title: "Sample Title",
          bullets: ["b1", "b2", "b3", "b4", "b5"],
          description: "Desc line 1\nDesc line 2",
          backend_keywords: "backend terms",
        },
      ],
      error: null,
    });

    const res = await GET(mockRequest(), mockParams({ projectId: validProjectId }));
    expect(res.status).toBe(200);
    const csv = await res.text();

    const rows = csv.split("\n");
    const headerCells = rows[0]
      .match(/(".*?"|[^",\s]+)(?=\s*,|\s*$)/g)
      ?.map((c) => c.replace(/^"|"$/g, "").replace(/""/g, '"'));
    const dataRow = rows[1];
    const dataCells = dataRow
      .match(/(".*?"|[^",\s]+)(?=\s*,|\s*$)/g)
      ?.map((c) => c.replace(/^"|"$/g, "").replace(/""/g, '"'));

    expect(dataCells?.length).toBe(headerCells?.length);
    expect(dataCells?.[0]).toBe("TEE-RED-M"); // sku_code
    expect(dataCells?.[3]).toBe("Friendly, casual, approachable"); // brand_tone
    expect(dataCells?.[4]).toBe("Adults who want an everyday comfortable tee"); // target_audience
    expect(dataCells?.[5]).toBe("Soft mid-weight cotton. Breathable enough for daily wear."); // supplied_content (newlines replaced)
    expect(dataCells?.[6]).toBe("Red"); // color
    expect(dataCells?.[7]).toBe("Medium"); // size
  });

  it("rejects unauthenticated requests", async () => {
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session: null } });

    const res = await GET(
      mockRequest(),
      mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" }),
    );

    const json = await res.json();
    expect(res.status).toBe(401);
    expect(json.error.code).toBe("unauthorized");
  });

  it("includes Stage C columns in CSV headers", async () => {
    const validProjectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "sku-123";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: validProjectId, name: "Test Project", created_by: "user-1" },
      error: null,
    });

    const skus = supabaseMock.getBuilder("scribe_skus");
    skus.__pushResponse({
      data: [
        {
          id: skuId,
          sku_code: "SKU001",
          asin: "B001",
          product_name: "Product 1",
          brand_tone: "Professional",
          target_audience: "Adults",
          supplied_content: "Content here",
          words_to_avoid: ["bad", "terrible"],
          scribe_sku_variant_values: [],
        },
      ],
      error: null,
    });

    const keywords = supabaseMock.getBuilder("scribe_keywords");
    keywords.__pushResponse({ data: [], error: null });

    const questions = supabaseMock.getBuilder("scribe_questions");
    questions.__pushResponse({ data: [], error: null });

    const content = supabaseMock.getBuilder("scribe_generated_content");
    content.__pushResponse({ data: [], error: null });

    const res = await GET(mockRequest(), mockParams({ projectId: validProjectId }));
    const csv = await res.text();

    const headers = csv.split("\n")[0];
    expect(headers).toContain("title");
    expect(headers).toContain("bullet_1");
    expect(headers).toContain("bullet_2");
    expect(headers).toContain("bullet_3");
    expect(headers).toContain("bullet_4");
    expect(headers).toContain("bullet_5");
    expect(headers).toContain("description");
    expect(headers).toContain("backend_keywords");
  });

  it("exports with empty Stage C fields when no generated content exists", async () => {
    const validProjectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "sku-123";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: validProjectId, name: "Test Project", created_by: "user-1" },
      error: null,
    });

    const skus = supabaseMock.getBuilder("scribe_skus");
    skus.__pushResponse({
      data: [
        {
          id: skuId,
          sku_code: "SKU001",
          asin: "B001",
          product_name: "Product 1",
          brand_tone: "Professional",
          target_audience: "Adults",
          supplied_content: "Content here",
          words_to_avoid: ["bad"],
          scribe_sku_variant_values: [],
        },
      ],
      error: null,
    });

    const keywords = supabaseMock.getBuilder("scribe_keywords");
    keywords.__pushResponse({
      data: [{ sku_id: skuId, keyword: "keyword1" }],
      error: null,
    });

    const questions = supabaseMock.getBuilder("scribe_questions");
    questions.__pushResponse({
      data: [{ sku_id: skuId, question: "Question 1?" }],
      error: null,
    });

    // No generated content
    const content = supabaseMock.getBuilder("scribe_generated_content");
    content.__pushResponse({ data: [], error: null });

    const res = await GET(mockRequest(), mockParams({ projectId: validProjectId }));
    const csv = await res.text();

    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toBe("text/csv; charset=utf-8");

    const rows = csv.split("\n");
    expect(rows.length).toBe(2); // Header + 1 SKU row

    const dataRow = rows[1];
    // Stage C fields should be empty but present
    // Count commas to verify all columns are present (including empty Stage C fields)
    const commaCount = (dataRow.match(/,/g) || []).length;
    const headerCommaCount = (rows[0].match(/,/g) || []).length;
    expect(commaCount).toBe(headerCommaCount);
  });

  it("exports with full Stage C content when generated content exists", async () => {
    const validProjectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "sku-123";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: validProjectId, name: "Test Project", created_by: "user-1" },
      error: null,
    });

    const skus = supabaseMock.getBuilder("scribe_skus");
    skus.__pushResponse({
      data: [
        {
          id: skuId,
          sku_code: "SKU001",
          asin: "B001",
          product_name: "Product 1",
          brand_tone: "Professional",
          target_audience: "Adults",
          supplied_content: "Content here",
          words_to_avoid: [],
          scribe_sku_variant_values: [],
        },
      ],
      error: null,
    });

    const keywords = supabaseMock.getBuilder("scribe_keywords");
    keywords.__pushResponse({ data: [], error: null });

    const questions = supabaseMock.getBuilder("scribe_questions");
    questions.__pushResponse({ data: [], error: null });

    const content = supabaseMock.getBuilder("scribe_generated_content");
    content.__pushResponse({
      data: [
        {
          sku_id: skuId,
          title: "Amazing Product Title",
          bullets: [
            "Bullet point 1",
            "Bullet point 2",
            "Bullet point 3",
            "Bullet point 4",
            "Bullet point 5",
          ],
          description: "This is a detailed product description.",
          backend_keywords: "keyword1 keyword2 keyword3",
        },
      ],
      error: null,
    });

    const res = await GET(mockRequest(), mockParams({ projectId: validProjectId }));
    const csv = await res.text();

    expect(res.status).toBe(200);
    expect(csv).toContain("Amazing Product Title");
    expect(csv).toContain("Bullet point 1");
    expect(csv).toContain("Bullet point 2");
    expect(csv).toContain("Bullet point 3");
    expect(csv).toContain("Bullet point 4");
    expect(csv).toContain("Bullet point 5");
    expect(csv).toContain("This is a detailed product description");
    expect(csv).toContain("keyword1 keyword2 keyword3");
  });

  it("allows export for archived projects", async () => {
    const validProjectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "sku-123";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: validProjectId, name: "Archived Project", created_by: "user-1" },
      error: null,
    });

    const skus = supabaseMock.getBuilder("scribe_skus");
    skus.__pushResponse({
      data: [
        {
          id: skuId,
          sku_code: "SKU001",
          asin: "B001",
          product_name: "Product 1",
          brand_tone: "Professional",
          target_audience: "Adults",
          supplied_content: "Content here",
          words_to_avoid: [],
          scribe_sku_variant_values: [],
        },
      ],
      error: null,
    });

    const keywords = supabaseMock.getBuilder("scribe_keywords");
    keywords.__pushResponse({ data: [], error: null });

    const questions = supabaseMock.getBuilder("scribe_questions");
    questions.__pushResponse({ data: [], error: null });

    const content = supabaseMock.getBuilder("scribe_generated_content");
    content.__pushResponse({ data: [], error: null });

    const res = await GET(mockRequest(), mockParams({ projectId: validProjectId }));

    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toBe("text/csv; charset=utf-8");
  });

  it("rejects when project has no SKUs", async () => {
    const validProjectId = "123e4567-e89b-12d3-a456-426614174000";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: validProjectId, name: "Test Project", created_by: "user-1" },
      error: null,
    });

    const skus = supabaseMock.getBuilder("scribe_skus");
    skus.__pushResponse({
      data: [],
      error: null,
    });

    const res = await GET(mockRequest(), mockParams({ projectId: validProjectId }));
    const json = await res.json();

    expect(res.status).toBe(400);
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain("No SKUs found");
  });

  it("properly escapes CSV values with commas and quotes", async () => {
    const validProjectId = "123e4567-e89b-12d3-a456-426614174000";
    const skuId = "sku-123";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: validProjectId, name: "Test Project", created_by: "user-1" },
      error: null,
    });

    const skus = supabaseMock.getBuilder("scribe_skus");
    skus.__pushResponse({
      data: [
        {
          id: skuId,
          sku_code: "SKU001",
          asin: "B001",
          product_name: 'Product with "quotes" and, commas',
          brand_tone: "Professional",
          target_audience: "Adults",
          supplied_content: "Content here",
          words_to_avoid: [],
          scribe_sku_variant_values: [],
        },
      ],
      error: null,
    });

    const keywords = supabaseMock.getBuilder("scribe_keywords");
    keywords.__pushResponse({ data: [], error: null });

    const questions = supabaseMock.getBuilder("scribe_questions");
    questions.__pushResponse({ data: [], error: null });

    const content = supabaseMock.getBuilder("scribe_generated_content");
    content.__pushResponse({
      data: [
        {
          sku_id: skuId,
          title: 'Title with "quotes"',
          bullets: ['Bullet with, comma', 'Bullet with "quotes"', "Normal", "Bullet", "Five"],
          description: "Description with, comma and \"quotes\"",
          backend_keywords: "keyword1, keyword2",
        },
      ],
      error: null,
    });

    const res = await GET(mockRequest(), mockParams({ projectId: validProjectId }));
    const csv = await res.text();

    expect(res.status).toBe(200);
    // CSV escaping: values with commas or quotes should be wrapped in quotes
    // and internal quotes should be doubled
    expect(csv).toContain('"Product with ""quotes"" and, commas"');
    expect(csv).toContain('"Title with ""quotes"""');
    expect(csv).toContain('"Bullet with, comma"');
    expect(csv).toContain('"Bullet with ""quotes"""');
  });
});
