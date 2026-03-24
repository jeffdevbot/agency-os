import { afterEach, describe, expect, it, vi } from "vitest";

process.env.NEXT_PUBLIC_BACKEND_URL = "http://localhost:8000";

import { getTeamHoursReport } from "./teamHours";

const TOKEN = "test-jwt-token";

const mockFetch = (status: number, body: unknown) =>
  vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "Error",
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  });

describe("getTeamHoursReport", () => {
  afterEach(() => vi.restoreAllMocks());

  it("requests the backend report with the selected date range", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch(200, {
        summary: { total_hours: 4 },
        team_members: [],
        clients: [],
        unmapped_users: [],
        unmapped_spaces: [],
        date_range: { start_date_ms: 1, end_date_ms: 2, days: [] },
      }),
    );

    const result = await getTeamHoursReport(TOKEN, {
      startDateMs: 1700000000000,
      endDateMs: 1700086400000,
    });

    expect(result.summary.total_hours).toBe(4);
    const [url, opts] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(
      "http://localhost:8000/admin/team-hours?start_date_ms=1700000000000&end_date_ms=1700086400000",
    );
    expect(opts.method).toBe("GET");
    expect(opts.headers.Authorization).toBe(`Bearer ${TOKEN}`);
  });

  it("throws a readable error on backend failure", async () => {
    vi.stubGlobal("fetch", mockFetch(500, { detail: "ClickUp not configured" }));

    await expect(
      getTeamHoursReport(TOKEN, { startDateMs: 1, endDateMs: 2 }),
    ).rejects.toThrow("Failed to load Team Hours (500): ClickUp not configured");
  });
});
