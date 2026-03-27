import { afterEach, describe, expect, it, vi } from "vitest";

process.env.NEXT_PUBLIC_BACKEND_URL = "http://localhost:8000";

import {
  listAmazonAdsSyncRuns,
  runAmazonAdsBackfill,
  runSearchTermBackfill,
  runSearchTermDailyRefresh,
} from "./wbrAmazonAdsApi";

const TOKEN = "test-jwt-token";

const mockFetch = (status: number, body: unknown) =>
  vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "Error",
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  });

describe("wbrAmazonAdsApi", () => {
  afterEach(() => vi.restoreAllMocks());

  it("parses sync runs with async Amazon Ads report progress metadata", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch(200, {
        ok: true,
        runs: [
          {
            id: "run-1",
            profile_id: "profile-1",
            source_type: "amazon_ads",
            ad_product: "SPONSORED_PRODUCTS",
            report_type_id: "spCampaigns",
            job_type: "backfill",
            date_from: "2026-03-01",
            date_to: "2026-03-14",
            status: "running",
            rows_fetched: 0,
            rows_loaded: 0,
            error_message: null,
            started_at: "2026-03-14T14:00:00+00:00",
            finished_at: null,
            created_at: "2026-03-14T14:00:00+00:00",
            updated_at: "2026-03-14T14:01:00+00:00",
            request_meta: {
              async_reports_v1: true,
              amazon_ads_profile_id: "1234567890",
              marketplace_code: "US",
              queued_at: "2026-03-14T14:00:00+00:00",
              report_jobs: [
                {
                  report_id: "rep-1",
                  status: "processing",
                  poll_attempts: 2,
                  next_poll_at: "2026-03-14T14:02:00+00:00",
                  location: null,
                  status_detail: "IN_PROGRESS",
                  campaign_type: "sponsored_products",
                  ad_product: "SPONSORED_PRODUCTS",
                  report_type_id: "spCampaigns",
                  columns: ["date", "campaignId"],
                },
              ],
              report_progress: {
                phase: "polling",
                summary: "0/1 reports ready, 1 still waiting on Amazon.",
                total_jobs: 1,
                pending_jobs: 0,
                processing_jobs: 1,
                completed_jobs: 0,
                failed_jobs: 0,
                next_poll_at: "2026-03-14T14:02:00+00:00",
              },
            },
          },
        ],
      }),
    );

    const runs = await listAmazonAdsSyncRuns(TOKEN, "profile-1");

    expect(runs).toHaveLength(1);
    expect(runs[0].ad_product).toBe("SPONSORED_PRODUCTS");
    expect(runs[0].report_type_id).toBe("spCampaigns");
    expect(runs[0].request_meta?.async_reports_v1).toBe(true);
    expect(runs[0].request_meta?.report_progress?.phase).toBe("polling");
    expect(runs[0].request_meta?.report_jobs[0].campaign_type).toBe("sponsored_products");
    expect(runs[0].request_meta?.report_jobs[0].poll_attempts).toBe(2);
  });

  it("parses queued backfill chunk responses with nested run metadata", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch(200, {
        ok: true,
        profile_id: "profile-1",
        job_type: "backfill",
        chunk_days: 14,
        date_from: "2026-03-01",
        date_to: "2026-03-14",
        chunks: [
          {
            rows_fetched: 0,
            rows_loaded: 0,
            run: {
              id: "run-1",
              profile_id: "profile-1",
              source_type: "amazon_ads",
              ad_product: "SPONSORED_PRODUCTS",
              report_type_id: "spCampaigns",
              job_type: "backfill",
              date_from: "2026-03-01",
              date_to: "2026-03-14",
              status: "running",
              rows_fetched: 0,
              rows_loaded: 0,
              error_message: null,
              started_at: "2026-03-14T14:00:00+00:00",
              finished_at: null,
              created_at: "2026-03-14T14:00:00+00:00",
              updated_at: "2026-03-14T14:00:00+00:00",
              request_meta: {
                async_reports_v1: true,
                report_progress: {
                  phase: "queued",
                  summary: "Queued 3 Amazon Ads report requests.",
                  total_jobs: 3,
                  pending_jobs: 3,
                  processing_jobs: 0,
                  completed_jobs: 0,
                  failed_jobs: 0,
                  next_poll_at: "2026-03-14T14:00:00+00:00",
                },
              },
            },
          },
        ],
      }),
    );

    const result = await runAmazonAdsBackfill(TOKEN, "profile-1", {
      date_from: "2026-03-01",
      date_to: "2026-03-14",
      chunk_days: 14,
    });

    expect(result.chunks).toHaveLength(1);
    expect(result.chunks[0].run.ad_product).toBe("SPONSORED_PRODUCTS");
    expect(result.chunks[0].run.report_type_id).toBe("spCampaigns");
    expect(result.chunks[0].run.request_meta?.report_progress?.phase).toBe("queued");
    expect(result.chunks[0].run.request_meta?.report_progress?.total_jobs).toBe(3);
  });

  it("sends the SB ad_product through search-term backfill and daily refresh requests", async () => {
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      json: () =>
        Promise.resolve({
          ok: true,
          profile_id: "profile-1",
          job_type: "backfill",
          chunk_days: 14,
          date_from: "2026-03-25",
          date_to: "2026-03-26",
          chunks: [
            {
              rows_fetched: 0,
              rows_loaded: 0,
              run: {
                id: "run-sb-1",
                profile_id: "profile-1",
                source_type: "amazon_ads_search_terms",
                ad_product: "SPONSORED_BRANDS",
                report_type_id: "sbSearchTerm",
                job_type: "backfill",
                date_from: "2026-03-25",
                date_to: "2026-03-26",
                status: "running",
                rows_fetched: 0,
                rows_loaded: 0,
                error_message: null,
                started_at: "2026-03-27T14:00:00+00:00",
                finished_at: null,
                created_at: "2026-03-27T14:00:00+00:00",
                updated_at: "2026-03-27T14:00:00+00:00",
                request_meta: { report_progress: { phase: "queued" } },
              },
            },
          ],
        }),
      text: () => Promise.resolve(""),
    });
    vi.stubGlobal("fetch", fetchSpy);

    await runSearchTermBackfill(
      TOKEN,
      "profile-1",
      {
        date_from: "2026-03-25",
        date_to: "2026-03-26",
        chunk_days: 14,
      },
      "SPONSORED_BRANDS",
    );

    await runSearchTermDailyRefresh(TOKEN, "profile-1", "SPONSORED_BRANDS").catch(() => undefined);

    const [backfillUrl, backfillInit] = fetchSpy.mock.calls[0];
    expect(String(backfillUrl)).toContain("/sync-runs/search-terms/backfill");
    expect(JSON.parse(String(backfillInit?.body)).ad_product).toBe("SPONSORED_BRANDS");

    const [refreshUrl] = fetchSpy.mock.calls[1];
    expect(String(refreshUrl)).toContain(
      "/sync-runs/search-terms/daily-refresh?ad_product=SPONSORED_BRANDS",
    );
  });
});
