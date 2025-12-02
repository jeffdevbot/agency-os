import { describe, it, expect, beforeEach, vi } from "vitest";
import type { NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { createSupabaseClientMock, type SupabaseClientMock } from "@/lib/composer/testSupabaseClient";

vi.mock("@/lib/supabase/serverClient", () => ({
  createSupabaseRouteClient: vi.fn(),
}));

const mockParams = (params: Record<string, string | undefined>) => ({
  params: Promise.resolve(params),
});

const mockRequest = (body?: unknown) =>
  ({
    json: vi.fn().mockResolvedValue(body),
    url: "http://localhost",
  }) as unknown as NextRequest;

/**
 * CSV Import Edge Case Tests
 *
 * Purpose: Verify that CSV import endpoint correctly enforces validation rules
 * for Stage A data import, particularly around limits and data integrity.
 *
 * Test Coverage:
 * - Enforce 50 SKU limit: reject import when existing + incoming SKUs > 50
 * - Duplicate SKUs in CSV: reject or handle per spec
 * - SKUs with >10 keywords: reject or trim per spec
 * - Upsert behavior: new SKUs created, existing SKUs updated
 */
describe("CSV import API (Stage A edge cases)", () => {
  let supabaseMock: SupabaseClientMock;

  // Note: This test assumes the import endpoint will be implemented with similar patterns
  // to existing Scribe endpoints. Adjust imports when the actual route file is created.
  const mockPOST = async (request: NextRequest, context: { params: Promise<{ projectId?: string }> }) => {
    // This is a placeholder for the actual POST handler
    // When the route is implemented, replace this with: import { POST } from "./route";
    const { projectId } = await context.params;

    if (!projectId || !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(projectId)) {
      return {
        status: 400,
        json: async () => ({ error: { code: "validation_error", message: "invalid project id" } }),
      };
    }

    const supabase = await createSupabaseRouteClient();
    const { data: { session } } = await supabase.auth.getSession();

    if (!session) {
      return {
        status: 401,
        json: async () => ({ error: { code: "unauthorized", message: "Unauthorized" } }),
      };
    }

    // Fetch project and verify ownership
    const { data: project, error: fetchError } = await supabase
      .from("scribe_projects")
      .select("id, status, created_by")
      .eq("id", projectId)
      .eq("created_by", session.user.id)
      .single();

    if (fetchError || !project) {
      return {
        status: 404,
        json: async () => ({ error: { code: "not_found", message: "Project not found" } }),
      };
    }

    // Check archived status
    if (project.status === "archived") {
      return {
        status: 403,
        json: async () => ({ error: { code: "forbidden", message: "Archived projects are read-only" } }),
      };
    }

    // Get request body (CSV data)
    const body = await request.json();
    const { skus: importedSkus } = body as { skus: Array<{ skuCode: string; keywords?: string[] }> };

    // Count existing SKUs
    const { count: existingCount, error: countError } = await supabase
      .from("scribe_skus")
      .select("*", { count: "exact", head: true })
      .eq("project_id", projectId);

    if (countError) {
      return {
        status: 500,
        json: async () => ({ error: { code: "server_error", message: countError.message } }),
      };
    }

    // Fetch existing SKUs by sku_code for upsert logic
    const { data: existingSkus, error: fetchSkusError } = await supabase
      .from("scribe_skus")
      .select("sku_code")
      .eq("project_id", projectId);

    if (fetchSkusError) {
      return {
        status: 500,
        json: async () => ({ error: { code: "server_error", message: fetchSkusError.message } }),
      };
    }

    const existingSkuCodes = new Set((existingSkus || []).map((s: { sku_code: string }) => s.sku_code));

    // Check for duplicate SKU codes in the CSV itself
    const importedSkuCodes = importedSkus.map(s => s.skuCode);
    const uniqueImportedSkuCodes = new Set(importedSkuCodes);
    if (importedSkuCodes.length !== uniqueImportedSkuCodes.size) {
      return {
        status: 400,
        json: async () => ({
          error: {
            code: "validation_error",
            message: "Duplicate SKU codes found in CSV"
          }
        }),
      };
    }

    // Calculate new SKUs (those not already in the project)
    const newSkuCodes = importedSkus
      .map(s => s.skuCode)
      .filter(code => !existingSkuCodes.has(code));

    const totalSkusAfterImport = (existingCount ?? 0) + newSkuCodes.length;

    // Enforce 50 SKU limit
    if (totalSkusAfterImport > 50) {
      return {
        status: 400,
        json: async () => ({
          error: {
            code: "validation_error",
            message: `Import would exceed 50 SKU limit (current: ${existingCount}, new: ${newSkuCodes.length}, total: ${totalSkusAfterImport})`
          }
        }),
      };
    }

    // Validate keyword limits per SKU
    for (const sku of importedSkus) {
      if (sku.keywords && sku.keywords.length > 10) {
        return {
          status: 400,
          json: async () => ({
            error: {
              code: "validation_error",
              message: `SKU "${sku.skuCode}" has ${sku.keywords.length} keywords (max 10 allowed)`
            }
          }),
        };
      }
    }

    // If all validations pass, return success summary
    const updated = importedSkus.filter(s => existingSkuCodes.has(s.skuCode)).length;
    const created = newSkuCodes.length;

    return {
      status: 200,
      json: async () => ({
        created,
        updated,
        errors: [],
      }),
    };
  };

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(supabaseMock.supabase);
  });

  it("rejects unauthenticated requests", async () => {
    supabaseMock.supabase.auth.getSession.mockResolvedValue({ data: { session: null } });

    const res = await mockPOST(
      mockRequest({ skus: [] }),
      mockParams({ projectId: "123e4567-e89b-12d3-a456-426614174000" })
    );

    const json = await res.json();
    expect(res.status).toBe(401);
    expect(json.error.code).toBe("unauthorized");
  });

  it("rejects archived projects", async () => {
    const validProjectId = "123e4567-e89b-12d3-a456-426614174000";
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: validProjectId, status: "archived", created_by: "user-1" },
      error: null,
    });

    const res = await mockPOST(
      mockRequest({ skus: [{ skuCode: "SKU1" }] }),
      mockParams({ projectId: validProjectId })
    );

    const json = await res.json();
    expect(res.status).toBe(403);
    expect(json.error.code).toBe("forbidden");
    expect(json.error.message).toContain("read-only");
  });

  it("enforces 50 SKU limit: rejects when existing 46 + importing 10 = 56", async () => {
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
    // Project already has 46 SKUs
    skus.__pushResponse({
      data: null,
      error: null,
      count: 46,
    });
    // Existing SKUs fetch (none match the imported ones)
    skus.__pushResponse({
      data: [],
      error: null,
    });

    // Attempt to import 10 new SKUs
    const importedSkus = Array.from({ length: 10 }, (_, i) => ({ skuCode: `NEW-SKU-${i + 1}` }));

    const res = await mockPOST(
      mockRequest({ skus: importedSkus }),
      mockParams({ projectId: validProjectId })
    );

    const json = await res.json();
    expect(res.status).toBe(400);
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain("50 SKU limit");
    expect(json.error.message).toContain("current: 46");
    expect(json.error.message).toContain("new: 10");
  });

  it("enforces 50 SKU limit: accepts when existing 45 + importing 5 = 50", async () => {
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
    // Project already has 45 SKUs
    skus.__pushResponse({
      data: null,
      error: null,
      count: 45,
    });
    // Existing SKUs fetch (none match the imported ones)
    skus.__pushResponse({
      data: [],
      error: null,
    });

    // Import 5 new SKUs (total = 50, should pass)
    const importedSkus = Array.from({ length: 5 }, (_, i) => ({ skuCode: `NEW-SKU-${i + 1}` }));

    const res = await mockPOST(
      mockRequest({ skus: importedSkus }),
      mockParams({ projectId: validProjectId })
    );

    const json = await res.json();
    expect(res.status).toBe(200);
    expect(json.created).toBe(5);
    expect(json.updated).toBe(0);
  });

  it("allows upsert: existing 46 + importing 10 (all existing) = 46 total", async () => {
    const validProjectId = "123e4567-e89b-12d3-a456-426614174000";
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: validProjectId, status: "draft", created_by: "user-1" },
      error: null,
    });

    const importedSkus = Array.from({ length: 10 }, (_, i) => ({ skuCode: `EXISTING-SKU-${i + 1}` }));
    const existingSkuData = importedSkus.map(s => ({ sku_code: s.skuCode }));

    const skus = supabaseMock.getBuilder("scribe_skus");
    // Project has 46 SKUs
    skus.__pushResponse({
      data: null,
      error: null,
      count: 46,
    });
    // All imported SKUs already exist
    skus.__pushResponse({
      data: existingSkuData,
      error: null,
    });

    const res = await mockPOST(
      mockRequest({ skus: importedSkus }),
      mockParams({ projectId: validProjectId })
    );

    const json = await res.json();
    expect(res.status).toBe(200);
    expect(json.created).toBe(0);
    expect(json.updated).toBe(10);
  });

  it("rejects CSV with duplicate SKU codes", async () => {
    const validProjectId = "123e4567-e89b-12d3-a456-426614174000";
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1" } } },
    });

    const projects = supabaseMock.getBuilder("scribe_projects");
    projects.__pushResponse({
      data: { id: validProjectId, status: "draft", created_by: "user-1" },
      error: null,
    });

    // CSV with duplicate SKU codes
    const importedSkus = [
      { skuCode: "SKU-001" },
      { skuCode: "SKU-002" },
      { skuCode: "SKU-001" }, // Duplicate
      { skuCode: "SKU-003" },
    ];

    const res = await mockPOST(
      mockRequest({ skus: importedSkus }),
      mockParams({ projectId: validProjectId })
    );

    const json = await res.json();
    expect(res.status).toBe(400);
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain("Duplicate SKU codes");
  });

  it("rejects SKU with 11 keywords (exceeds max 10)", async () => {
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
    skus.__pushResponse({
      data: null,
      error: null,
      count: 0,
    });
    skus.__pushResponse({
      data: [],
      error: null,
    });

    // SKU with 11 keywords
    const importedSkus = [
      {
        skuCode: "SKU-001",
        keywords: [
          "keyword1", "keyword2", "keyword3", "keyword4", "keyword5",
          "keyword6", "keyword7", "keyword8", "keyword9", "keyword10",
          "keyword11", // 11th keyword
        ],
      },
    ];

    const res = await mockPOST(
      mockRequest({ skus: importedSkus }),
      mockParams({ projectId: validProjectId })
    );

    const json = await res.json();
    expect(res.status).toBe(400);
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain("SKU-001");
    expect(json.error.message).toContain("11 keywords");
    expect(json.error.message).toContain("max 10");
  });

  it("accepts SKU with exactly 10 keywords", async () => {
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
    skus.__pushResponse({
      data: null,
      error: null,
      count: 0,
    });
    skus.__pushResponse({
      data: [],
      error: null,
    });

    // SKU with exactly 10 keywords
    const importedSkus = [
      {
        skuCode: "SKU-001",
        keywords: [
          "keyword1", "keyword2", "keyword3", "keyword4", "keyword5",
          "keyword6", "keyword7", "keyword8", "keyword9", "keyword10",
        ],
      },
    ];

    const res = await mockPOST(
      mockRequest({ skus: importedSkus }),
      mockParams({ projectId: validProjectId })
    );

    const json = await res.json();
    expect(res.status).toBe(200);
    expect(json.created).toBe(1);
  });

  it("handles mixed scenario: 3 new SKUs + 2 updates, one with 12 keywords (reject)", async () => {
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
    skus.__pushResponse({
      data: null,
      error: null,
      count: 10,
    });
    skus.__pushResponse({
      data: [
        { sku_code: "EXISTING-1" },
        { sku_code: "EXISTING-2" },
      ],
      error: null,
    });

    // Import 5 SKUs: 2 existing, 3 new, but one new SKU has 12 keywords
    const importedSkus = [
      { skuCode: "EXISTING-1", keywords: ["kw1", "kw2"] },
      { skuCode: "EXISTING-2", keywords: ["kw3"] },
      { skuCode: "NEW-1", keywords: ["kw4"] },
      { skuCode: "NEW-2", keywords: ["kw5"] },
      {
        skuCode: "NEW-3",
        keywords: Array.from({ length: 12 }, (_, i) => `kw${i + 10}`), // 12 keywords
      },
    ];

    const res = await mockPOST(
      mockRequest({ skus: importedSkus }),
      mockParams({ projectId: validProjectId })
    );

    const json = await res.json();
    expect(res.status).toBe(400);
    expect(json.error.code).toBe("validation_error");
    expect(json.error.message).toContain("NEW-3");
    expect(json.error.message).toContain("12 keywords");
  });
});
