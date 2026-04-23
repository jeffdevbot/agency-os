import { beforeEach, describe, expect, it, vi } from "vitest";

import { GET } from "./route";
import { assertNgram2ProfileAccess } from "@/lib/ngram2/access";
import { createSupabaseRouteClient, createSupabaseServiceClient } from "@/lib/supabase/serverClient";

vi.mock("@/lib/supabase/serverClient", () => ({
  createSupabaseRouteClient: vi.fn(),
  createSupabaseServiceClient: vi.fn(),
}));

vi.mock("@/lib/ngram2/access", () => ({
  assertNgram2ProfileAccess: vi.fn(),
  NgramAccessError: class NgramAccessError extends Error {
    status: number;

    constructor(message: string, status = 403) {
      super(message);
      this.status = status;
    }
  },
}));

type PreviewRunRow = {
  id: string;
  created_at: string;
  ad_product: string;
  date_from: string;
  date_to: string;
  spend_threshold: number;
  respect_legacy_exclusions: boolean;
  model: string;
  prompt_version: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  preview_payload: Record<string, unknown>;
};

const buildServiceClientMock = (rows: PreviewRunRow[]) => {
  const builder = {
    select: vi.fn(),
    eq: vi.fn(),
    order: vi.fn(),
    range: vi.fn(),
  };

  builder.select.mockReturnValue(builder);
  builder.eq.mockReturnValue(builder);
  builder.order.mockReturnValue(builder);
  builder.range.mockImplementation(async (from: number, to: number) => ({
    data: rows.slice(from, to + 1),
    error: null,
  }));

  return {
    from: vi.fn(() => builder),
    builder,
  };
};

describe("GET /api/ngram-2/saved-runs", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    (createSupabaseRouteClient as vi.Mock).mockResolvedValue({
      auth: {
        getUser: vi.fn().mockResolvedValue({
          data: {
            user: {
              id: "user-1",
            },
          },
        }),
      },
    });
    vi.mocked(assertNgram2ProfileAccess).mockResolvedValue(undefined);
  });

  it("returns only saved runs that match the selected allowed languages", async () => {
    const serviceClientMock = buildServiceClientMock([
      {
        id: "run-match",
        created_at: "2026-04-23T12:00:00Z",
        ad_product: "SPONSORED_PRODUCTS",
        date_from: "2026-04-01",
        date_to: "2026-04-15",
        spend_threshold: 0,
        respect_legacy_exclusions: true,
        model: "gpt-5.4",
        prompt_version: "prompt-v1",
        prompt_tokens: 100,
        completion_tokens: 40,
        total_tokens: 140,
        preview_payload: {
          run_mode: "preview",
          prefill_strategy: "pure_model_single_campaign",
          allowed_languages: ["fr", "en"],
          disable_language_negation: false,
          preview_campaigns: 2,
          runnable_campaigns: 2,
          recommendation_counts: { keep: 1, negate: 2, review: 0 },
        },
      },
      {
        id: "run-mismatch",
        created_at: "2026-04-23T11:00:00Z",
        ad_product: "SPONSORED_PRODUCTS",
        date_from: "2026-04-01",
        date_to: "2026-04-15",
        spend_threshold: 0,
        respect_legacy_exclusions: true,
        model: "gpt-5.4",
        prompt_version: "prompt-v1",
        prompt_tokens: 90,
        completion_tokens: 30,
        total_tokens: 120,
        preview_payload: {
          run_mode: "preview",
          prefill_strategy: "pure_model_single_campaign",
          allowed_languages: ["en", "es"],
          disable_language_negation: false,
          preview_campaigns: 1,
          runnable_campaigns: 1,
          recommendation_counts: { keep: 1, negate: 0, review: 0 },
        },
      },
    ]);
    (createSupabaseServiceClient as vi.Mock).mockReturnValue(serviceClientMock);

    const response = await GET(
      new Request(
        "http://localhost/api/ngram-2/saved-runs?profile_id=profile-1&ad_product=SPONSORED_PRODUCTS&date_from=2026-04-01&date_to=2026-04-15&respect_legacy_exclusions=true&allowed_languages=en,fr&disable_language_negation=false&limit=5",
      ),
    );
    const json = (await response.json()) as { runs: Array<{ id: string }> };

    expect(response.status).toBe(200);
    expect(json.runs.map((run) => run.id)).toEqual(["run-match"]);
    expect(serviceClientMock.builder.range).toHaveBeenCalledWith(0, 24);
  });

  it("ignores allowed languages when language-based negation is disabled", async () => {
    const serviceClientMock = buildServiceClientMock([
      {
        id: "run-disabled-a",
        created_at: "2026-04-23T12:00:00Z",
        ad_product: "SPONSORED_PRODUCTS",
        date_from: "2026-04-01",
        date_to: "2026-04-15",
        spend_threshold: 0,
        respect_legacy_exclusions: true,
        model: "gpt-5.4",
        prompt_version: "prompt-v1",
        prompt_tokens: 100,
        completion_tokens: 40,
        total_tokens: 140,
        preview_payload: {
          run_mode: "preview",
          prefill_strategy: "pure_model_single_campaign",
          allowed_languages: ["en"],
          disable_language_negation: true,
          preview_campaigns: 2,
          runnable_campaigns: 2,
          recommendation_counts: { keep: 1, negate: 2, review: 0 },
        },
      },
      {
        id: "run-disabled-b",
        created_at: "2026-04-23T11:00:00Z",
        ad_product: "SPONSORED_PRODUCTS",
        date_from: "2026-04-01",
        date_to: "2026-04-15",
        spend_threshold: 0,
        respect_legacy_exclusions: true,
        model: "gpt-5.4",
        prompt_version: "prompt-v1",
        prompt_tokens: 90,
        completion_tokens: 30,
        total_tokens: 120,
        preview_payload: {
          run_mode: "preview",
          prefill_strategy: "pure_model_single_campaign",
          allowed_languages: ["fr", "de"],
          disable_language_negation: true,
          preview_campaigns: 1,
          runnable_campaigns: 1,
          recommendation_counts: { keep: 1, negate: 0, review: 0 },
        },
      },
      {
        id: "run-enabled",
        created_at: "2026-04-23T10:00:00Z",
        ad_product: "SPONSORED_PRODUCTS",
        date_from: "2026-04-01",
        date_to: "2026-04-15",
        spend_threshold: 0,
        respect_legacy_exclusions: true,
        model: "gpt-5.4",
        prompt_version: "prompt-v1",
        prompt_tokens: 80,
        completion_tokens: 20,
        total_tokens: 100,
        preview_payload: {
          run_mode: "preview",
          prefill_strategy: "pure_model_single_campaign",
          allowed_languages: ["en", "fr"],
          disable_language_negation: false,
          preview_campaigns: 1,
          runnable_campaigns: 1,
          recommendation_counts: { keep: 1, negate: 0, review: 0 },
        },
      },
    ]);
    (createSupabaseServiceClient as vi.Mock).mockReturnValue(serviceClientMock);

    const response = await GET(
      new Request(
        "http://localhost/api/ngram-2/saved-runs?profile_id=profile-1&ad_product=SPONSORED_PRODUCTS&date_from=2026-04-01&date_to=2026-04-15&respect_legacy_exclusions=true&allowed_languages=ja,ko&disable_language_negation=true&limit=5",
      ),
    );
    const json = (await response.json()) as { runs: Array<{ id: string }> };

    expect(response.status).toBe(200);
    expect(json.runs.map((run) => run.id)).toEqual(["run-disabled-a", "run-disabled-b"]);
  });

  it("keeps paging until it finds later matching runs", async () => {
    const rows: PreviewRunRow[] = Array.from({ length: 25 }, (_, index) => ({
      id: `run-mismatch-${index + 1}`,
      created_at: `2026-04-23T12:${String(index).padStart(2, "0")}:00Z`,
      ad_product: "SPONSORED_PRODUCTS",
      date_from: "2026-04-01",
      date_to: "2026-04-15",
      spend_threshold: 0,
      respect_legacy_exclusions: true,
      model: "gpt-5.4",
      prompt_version: "prompt-v1",
      prompt_tokens: 50,
      completion_tokens: 10,
      total_tokens: 60,
      preview_payload: {
        run_mode: "preview",
        prefill_strategy: "pure_model_single_campaign",
        allowed_languages: ["en", "es"],
        disable_language_negation: false,
        preview_campaigns: 1,
        runnable_campaigns: 1,
        recommendation_counts: { keep: 1, negate: 0, review: 0 },
      },
    }));
    rows.push({
      id: "run-match-page-2",
      created_at: "2026-04-23T11:00:00Z",
      ad_product: "SPONSORED_PRODUCTS",
      date_from: "2026-04-01",
      date_to: "2026-04-15",
      spend_threshold: 0,
      respect_legacy_exclusions: true,
      model: "gpt-5.4",
      prompt_version: "prompt-v1",
      prompt_tokens: 100,
      completion_tokens: 40,
      total_tokens: 140,
      preview_payload: {
        run_mode: "preview",
        prefill_strategy: "pure_model_single_campaign",
        allowed_languages: ["en", "fr"],
        disable_language_negation: false,
        preview_campaigns: 2,
        runnable_campaigns: 2,
        recommendation_counts: { keep: 1, negate: 2, review: 0 },
      },
    });
    const serviceClientMock = buildServiceClientMock(rows);
    (createSupabaseServiceClient as vi.Mock).mockReturnValue(serviceClientMock);

    const response = await GET(
      new Request(
        "http://localhost/api/ngram-2/saved-runs?profile_id=profile-1&ad_product=SPONSORED_PRODUCTS&date_from=2026-04-01&date_to=2026-04-15&respect_legacy_exclusions=true&allowed_languages=en,fr&disable_language_negation=false&limit=5",
      ),
    );
    const json = (await response.json()) as { runs: Array<{ id: string }> };

    expect(response.status).toBe(200);
    expect(json.runs.map((run) => run.id)).toEqual(["run-match-page-2"]);
    expect(serviceClientMock.builder.range).toHaveBeenNthCalledWith(1, 0, 24);
    expect(serviceClientMock.builder.range).toHaveBeenNthCalledWith(2, 25, 49);
  });
});
