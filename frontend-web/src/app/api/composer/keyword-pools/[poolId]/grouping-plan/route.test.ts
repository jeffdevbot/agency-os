import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";
import { POST } from "./route";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import {
  createSupabaseClientMock,
  type SupabaseClientMock,
} from "@/lib/composer/testSupabaseClient";
import * as groupKeywordsModule from "@agency/lib/composer/ai/groupKeywords";
import * as usageLoggerModule from "@agency/lib/composer/ai/usageLogger";

vi.mock("@/lib/supabase/serverClient", () => ({
  createSupabaseRouteClient: vi.fn(),
}));

vi.mock("@agency/lib/composer/ai/groupKeywords");
vi.mock("@agency/lib/composer/ai/usageLogger");

const mockParams = (params: Record<string, string | undefined>) => ({
  params: Promise.resolve(params),
});

const mockRequest = (body?: unknown) =>
  ({
    json: vi.fn().mockResolvedValue(body),
  }) as unknown as NextRequest;

const buildSession = (orgId = "623e4567-e89b-12d3-a456-426614174000") => ({
  user: {
    id: "723e4567-e89b-12d3-a456-426614174000",
    org_id: orgId,
    app_metadata: {},
    user_metadata: {},
  },
});

describe("grouping-plan API", () => {
  let supabaseMock: SupabaseClientMock;

  beforeEach(() => {
    vi.resetAllMocks();
    supabaseMock = createSupabaseClientMock();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue(
      supabaseMock.supabase,
    );

    vi.spyOn(usageLoggerModule, "logUsageEvent").mockResolvedValue();
  });

  it("groups keywords and stores AI groups", async () => {
    const session = buildSession();
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session },
    });

    const poolBuilder = supabaseMock.getBuilder("composer_keyword_pools");
    poolBuilder.__pushResponse({
      data: {
        id: "223e4567-e89b-12d3-a456-426614174000",
        organization_id: session.user.org_id,
        project_id: "123e4567-e89b-12d3-a456-426614174000",
        group_id: null,
        pool_type: "body",
        status: "cleaned",
        raw_keywords: ["blue shirt", "red dress", "green pants"],
        cleaned_keywords: ["blue shirt", "red dress", "green pants"],
        removed_keywords: [],
        clean_settings: {},
        grouping_config: {},
        cleaned_at: "2025-11-20T10:00:00Z",
        grouped_at: null,
        approved_at: null,
        created_at: "2025-11-20T09:00:00Z",
      },
      error: null,
    });

    const projectBuilder = supabaseMock.getBuilder("composer_projects");
    projectBuilder.__pushResponse({
      data: {
        id: "123e4567-e89b-12d3-a456-426614174000",
        organization_id: session.user.org_id,
        client_name: "Acme Corp",
        category: "Apparel",
      },
      error: null,
    });

    const groupsBuilder = supabaseMock.getBuilder("composer_keyword_groups");
    groupsBuilder.__pushResponse({ data: [], error: null });

    const mockGroups = [
      {
        id: "g23e4567-e89b-12d3-a456-426614174000",
        organizationId: session.user.org_id,
        keywordPoolId: "223e4567-e89b-12d3-a456-426614174000",
        groupIndex: 0,
        label: "Blue Items",
        phrases: ["blue shirt"],
        metadata: { basis: "custom", aiGenerated: true },
        createdAt: "2025-11-20T12:00:00Z",
      },
      {
        id: "g23e4567-e89b-12d3-a456-426614174001",
        organizationId: session.user.org_id,
        keywordPoolId: "223e4567-e89b-12d3-a456-426614174000",
        groupIndex: 1,
        label: "Red/Green Items",
        phrases: ["red dress", "green pants"],
        metadata: { basis: "custom", aiGenerated: true },
        createdAt: "2025-11-20T12:00:00Z",
      },
    ];

    vi.spyOn(groupKeywordsModule, "groupKeywords").mockResolvedValue({
      groups: mockGroups,
      usage: { tokensIn: 10, tokensOut: 20, tokensTotal: 30, model: "gpt-5.1-nano", durationMs: 500 },
    });

    groupsBuilder.__pushResponse({
      data: [
        {
          id: "g23e4567-e89b-12d3-a456-426614174000",
          organization_id: session.user.org_id,
          keyword_pool_id: "223e4567-e89b-12d3-a456-426614174000",
          group_index: 0,
          label: "Blue Items",
          phrases: ["blue shirt"],
          metadata: { basis: "custom", aiGenerated: true },
          created_at: "2025-11-20T12:00:00Z",
        },
        {
          id: "g23e4567-e89b-12d3-a456-426614174001",
          organization_id: session.user.org_id,
          keyword_pool_id: "223e4567-e89b-12d3-a456-426614174000",
          group_index: 1,
          label: "Red/Green Items",
          phrases: ["red dress", "green pants"],
          metadata: { basis: "custom", aiGenerated: true },
          created_at: "2025-11-20T12:00:00Z",
        },
      ],
      error: null,
    });

    poolBuilder.__pushResponse({
      data: {
        id: "223e4567-e89b-12d3-a456-426614174000",
        organization_id: session.user.org_id,
        project_id: "123e4567-e89b-12d3-a456-426614174000",
        group_id: null,
        pool_type: "body",
        status: "cleaned",
        raw_keywords: ["blue shirt", "red dress", "green pants"],
        cleaned_keywords: ["blue shirt", "red dress", "green pants"],
        removed_keywords: [],
        clean_settings: {},
        grouping_config: { basis: "custom", groupCount: 2 },
        cleaned_at: "2025-11-20T10:00:00Z",
        grouped_at: "2025-11-20T12:00:00Z",
        approved_at: null,
        created_at: "2025-11-20T09:00:00Z",
      },
      error: null,
    });

    const response = await POST(
      mockRequest({ config: { basis: "custom", groupCount: 2 } }),
      mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
    );

    const json = await response.json();

    expect(response.status).toBe(200);
    expect(json.groups).toHaveLength(2);
    expect(json.groups[0].label).toBe("Blue Items");
    expect(json.groups[1].label).toBe("Red/Green Items");
    expect(json.pool.groupingConfig).toEqual({ basis: "custom", groupCount: 2 });
    expect(json.pool.groupedAt).toBeTruthy();
    expect(json.pool.approvedAt).toBeNull();

    expect(groupKeywordsModule.groupKeywords).toHaveBeenCalledWith(
      ["blue shirt", "red dress", "green pants"],
      { basis: "custom", groupCount: 2 },
      expect.objectContaining({
        project: { clientName: "Acme Corp", category: "Apparel" },
        poolType: "body",
        poolId: "223e4567-e89b-12d3-a456-426614174000",
      }),
    );

    expect(usageLoggerModule.logUsageEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        action: "keyword_grouping",
        model: "gpt-5.1-nano",
        tokensIn: 10,
        tokensOut: 20,
        tokensTotal: 30,
        meta: expect.objectContaining({
          pool_type: "body",
          pool_id: "223e4567-e89b-12d3-a456-426614174000",
          keyword_count: 3,
          basis: "custom",
          group_count: 2,
        }),
      }),
    );
  });

  it("returns 400 when pool is not cleaned", async () => {
    const session = buildSession();
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session },
    });

    const poolBuilder = supabaseMock.getBuilder("composer_keyword_pools");
    poolBuilder.__pushResponse({
      data: {
        id: "223e4567-e89b-12d3-a456-426614174000",
        organization_id: session.user.org_id,
        project_id: "123e4567-e89b-12d3-a456-426614174000",
        pool_type: "body",
        status: "uploaded",
        cleaned_keywords: [],
      },
      error: null,
    });

    const response = await POST(
      mockRequest({ config: { basis: "single" } }),
      mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
    );

    expect(response.status).toBe(400);
    const json = await response.json();
    expect(json.error).toBe("pool_must_be_cleaned_before_grouping");
  });

  it("returns 400 when pool has no cleaned keywords", async () => {
    const session = buildSession();
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session },
    });

    const poolBuilder = supabaseMock.getBuilder("composer_keyword_pools");
    poolBuilder.__pushResponse({
      data: {
        id: "223e4567-e89b-12d3-a456-426614174000",
        organization_id: session.user.org_id,
        project_id: "123e4567-e89b-12d3-a456-426614174000",
        pool_type: "body",
        status: "cleaned",
        cleaned_keywords: [],
      },
      error: null,
    });

    const response = await POST(
      mockRequest({ config: { basis: "single" } }),
      mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
    );

    expect(response.status).toBe(400);
    const json = await response.json();
    expect(json.error).toBe("no_cleaned_keywords_to_group");
  });

  it("returns 404 when pool is not found", async () => {
    const session = buildSession();
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session },
    });

    const poolBuilder = supabaseMock.getBuilder("composer_keyword_pools");
    poolBuilder.__pushResponse({ data: null, error: null });

    const response = await POST(
      mockRequest({ config: { basis: "single" } }),
      mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
    );

    expect(response.status).toBe(404);
  });

  it("returns 401 when not authenticated", async () => {
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session: null },
    });

    const response = await POST(
      mockRequest({ config: { basis: "single" } }),
      mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
    );

    expect(response.status).toBe(401);
  });

  it("deletes existing groups before inserting new ones", async () => {
    const session = buildSession();
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session },
    });

    const poolBuilder = supabaseMock.getBuilder("composer_keyword_pools");
    poolBuilder.__pushResponse({
      data: {
        id: "223e4567-e89b-12d3-a456-426614174000",
        organization_id: session.user.org_id,
        project_id: "123e4567-e89b-12d3-a456-426614174000",
        pool_type: "body",
        status: "cleaned",
        cleaned_keywords: ["blue shirt"],
      },
      error: null,
    });

    const projectBuilder = supabaseMock.getBuilder("composer_projects");
    projectBuilder.__pushResponse({
      data: {
        id: "123e4567-e89b-12d3-a456-426614174000",
        organization_id: session.user.org_id,
        client_name: "Acme",
        category: null,
      },
      error: null,
    });

    const groupsBuilder = supabaseMock.getBuilder("composer_keyword_groups");
    groupsBuilder.__pushResponse({
      data: [{ id: "old-group-1" }, { id: "old-group-2" }],
      error: null,
    });

    groupsBuilder.__pushResponse({ data: [], error: null });

    vi.spyOn(groupKeywordsModule, "groupKeywords").mockResolvedValue({
      groups: [
        {
          id: "n23e4567-e89b-12d3-a456-426614174000",
          organizationId: session.user.org_id,
          keywordPoolId: "223e4567-e89b-12d3-a456-426614174000",
          groupIndex: 0,
          label: "General",
          phrases: ["blue shirt"],
          metadata: {},
          createdAt: new Date().toISOString(),
        },
      ],
      usage: { tokensIn: 5, tokensOut: 5, tokensTotal: 10, model: "gpt-5.1-nano", durationMs: 50 },
    });

    groupsBuilder.__pushResponse({
      data: [
        {
          id: "n23e4567-e89b-12d3-a456-426614174000",
          organization_id: session.user.org_id,
          keyword_pool_id: "223e4567-e89b-12d3-a456-426614174000",
          group_index: 0,
          label: "General",
          phrases: ["blue shirt"],
          metadata: {},
          created_at: new Date().toISOString(),
        },
      ],
      error: null,
    });

    poolBuilder.__pushResponse({
      data: {
        id: "223e4567-e89b-12d3-a456-426614174000",
        organization_id: session.user.org_id,
        project_id: "123e4567-e89b-12d3-a456-426614174000",
        pool_type: "body",
        status: "cleaned",
        cleaned_keywords: ["blue shirt"],
        grouping_config: {},
        grouped_at: new Date().toISOString(),
      },
      error: null,
    });

    const response = await POST(
      mockRequest({ config: {} }),
      mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
    );

    expect(response.status).toBe(200);
  });

  it("logs usage event even when grouping fails", async () => {
    const session = buildSession();
    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session },
    });

    const poolBuilder = supabaseMock.getBuilder("composer_keyword_pools");
    poolBuilder.__pushResponse({
      data: {
        id: "223e4567-e89b-12d3-a456-426614174000",
        organization_id: session.user.org_id,
        project_id: "123e4567-e89b-12d3-a456-426614174000",
        pool_type: "body",
        status: "cleaned",
        cleaned_keywords: ["blue shirt"],
      },
      error: null,
    });

    const projectBuilder = supabaseMock.getBuilder("composer_projects");
    projectBuilder.__pushResponse({
      data: {
        id: "123e4567-e89b-12d3-a456-426614174000",
        organization_id: session.user.org_id,
        client_name: "Acme",
        category: null,
      },
      error: null,
    });

    const groupsBuilder = supabaseMock.getBuilder("composer_keyword_groups");
    groupsBuilder.__pushResponse({ data: [], error: null });

    vi.spyOn(groupKeywordsModule, "groupKeywords").mockRejectedValue(
      new Error("AI error"),
    );

    const response = await POST(
      mockRequest({ config: { basis: "single" } }),
      mockParams({ poolId: "223e4567-e89b-12d3-a456-426614174000" }),
    );

    expect(response.status).toBe(500);

    expect(usageLoggerModule.logUsageEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        action: "keyword_grouping",
        meta: expect.objectContaining({
          error: "AI error",
        }),
      }),
    );
  });

  it("logs comprehensive usage event with all required parameters on success", async () => {
    const session = buildSession();
    const orgId = session.user.org_id;
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
    const poolId = "223e4567-e89b-12d3-a456-426614174000";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session },
    });

    const poolBuilder = supabaseMock.getBuilder("composer_keyword_pools");
    poolBuilder.__pushResponse({
      data: {
        id: poolId,
        organization_id: orgId,
        project_id: projectId,
        pool_type: "titles",
        status: "cleaned",
        cleaned_keywords: ["keyword1", "keyword2", "keyword3"],
      },
      error: null,
    });

    const projectBuilder = supabaseMock.getBuilder("composer_projects");
    projectBuilder.__pushResponse({
      data: {
        id: projectId,
        organization_id: orgId,
        client_name: "Test Client",
        category: "Test Category",
      },
      error: null,
    });

    const groupsBuilder = supabaseMock.getBuilder("composer_keyword_groups");
    groupsBuilder.__pushResponse({ data: [], error: null });

    const mockGroups = [
      {
        id: "g23e4567-e89b-12d3-a456-426614174000",
        organizationId: orgId,
        keywordPoolId: poolId,
        groupIndex: 0,
        label: "Test Group",
        phrases: ["keyword1", "keyword2", "keyword3"],
        metadata: { basis: "per_sku", aiGenerated: true },
        createdAt: new Date().toISOString(),
      },
    ];

    vi.spyOn(groupKeywordsModule, "groupKeywords").mockResolvedValue(mockGroups);

    groupsBuilder.__pushResponse({
      data: [
        {
          id: "g23e4567-e89b-12d3-a456-426614174000",
          organization_id: orgId,
          keyword_pool_id: poolId,
          group_index: 0,
          label: "Test Group",
          phrases: ["keyword1", "keyword2", "keyword3"],
          metadata: { basis: "per_sku", aiGenerated: true },
          created_at: new Date().toISOString(),
        },
      ],
      error: null,
    });

    poolBuilder.__pushResponse({
      data: {
        id: poolId,
        organization_id: orgId,
        project_id: projectId,
        pool_type: "titles",
        status: "cleaned",
        cleaned_keywords: ["keyword1", "keyword2", "keyword3"],
        grouping_config: { basis: "per_sku" },
        grouped_at: new Date().toISOString(),
      },
      error: null,
    });

    vi.spyOn(groupKeywordsModule, "groupKeywords").mockResolvedValue({
      groups: [
        {
          id: "group-1",
          organizationId: orgId,
          keywordPoolId: poolId,
          groupIndex: 0,
          label: "Test Group",
          phrases: ["keyword1", "keyword2", "keyword3"],
          metadata: { basis: "per_sku", aiGenerated: true },
          createdAt: new Date().toISOString(),
        },
      ],
      usage: { tokensIn: 12, tokensOut: 8, tokensTotal: 20, model: "gpt-5.1-nano", durationMs: 42 },
    });

    await POST(
      mockRequest({ config: { basis: "per_sku" } }),
      mockParams({ poolId }),
    );

    expect(usageLoggerModule.logUsageEvent).toHaveBeenCalledTimes(1);
    expect(usageLoggerModule.logUsageEvent).toHaveBeenCalledWith({
      supabase: supabaseMock.supabase,
      organizationId: orgId,
      projectId: projectId,
      jobId: null,
      action: "keyword_grouping",
      model: "gpt-5.1-nano",
      tokensIn: 12,
      tokensOut: 8,
      tokensTotal: 20,
      durationMs: 42,
      meta: {
        pool_type: "titles",
        pool_id: poolId,
        keyword_count: 3,
        basis: "per_sku",
        group_count: 1,
      },
    });

    const call = vi.mocked(usageLoggerModule.logUsageEvent).mock.calls[0][0];
    expect(call.tokensIn).toBeGreaterThan(0);
    expect(call.tokensOut).toBeGreaterThan(0);
    expect(call.tokensTotal).toBe(call.tokensIn + call.tokensOut);
    expect(call.durationMs).toBeGreaterThanOrEqual(0);
  });

  it("logs usage event with zero tokens on error", async () => {
    const session = buildSession();
    const orgId = session.user.org_id;
    const projectId = "123e4567-e89b-12d3-a456-426614174000";
    const poolId = "223e4567-e89b-12d3-a456-426614174000";

    supabaseMock.supabase.auth.getSession.mockResolvedValue({
      data: { session },
    });

    const poolBuilder = supabaseMock.getBuilder("composer_keyword_pools");
    poolBuilder.__pushResponse({
      data: {
        id: poolId,
        organization_id: orgId,
        project_id: projectId,
        pool_type: "body",
        status: "cleaned",
        cleaned_keywords: ["test keyword"],
      },
      error: null,
    });

    const projectBuilder = supabaseMock.getBuilder("composer_projects");
    projectBuilder.__pushResponse({
      data: {
        id: projectId,
        organization_id: orgId,
        client_name: "Test",
        category: "Test",
      },
      error: null,
    });

    const groupsBuilder = supabaseMock.getBuilder("composer_keyword_groups");
    groupsBuilder.__pushResponse({ data: [], error: null });

    vi.spyOn(groupKeywordsModule, "groupKeywords").mockRejectedValue(
      new Error("OpenAI API timeout"),
    );

    await POST(
      mockRequest({ config: { basis: "custom", groupCount: 5 } }),
      mockParams({ poolId }),
    );

    expect(usageLoggerModule.logUsageEvent).toHaveBeenCalledTimes(1);
    expect(usageLoggerModule.logUsageEvent).toHaveBeenCalledWith({
      supabase: supabaseMock.supabase,
      organizationId: orgId,
      projectId: projectId,
      jobId: null,
      action: "keyword_grouping",
      model: expect.any(String),
      tokensIn: 0,
      tokensOut: 0,
      tokensTotal: 0,
      durationMs: expect.any(Number),
      meta: {
        pool_type: "body",
        pool_id: poolId,
        keyword_count: 1,
        basis: "custom",
        error: "OpenAI API timeout",
      },
    });
  });
});
