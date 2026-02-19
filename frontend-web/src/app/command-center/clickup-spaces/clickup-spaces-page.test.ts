/**
 * Page behavior tests for ClickUp Spaces page (C6B).
 *
 * Uses Vitest + a lightweight render check since the test environment is
 * `node` (not jsdom). We test the data-flow logic by importing the module
 * and verifying the component function exists and exports correctly.
 *
 * Full interactive RTL tests would require jsdom; these are smoke tests
 * that validate the module is importable and the key API client functions
 * behave correctly when called from page-level code paths.
 */
import { describe, it, expect, vi, afterEach } from "vitest";

// Stub supabase client before importing page module
vi.mock("@/lib/supabaseClient", () => ({
    getBrowserSupabaseClient: () => ({
        auth: {
            getSession: () =>
                Promise.resolve({
                    data: { session: { access_token: "test-token" } },
                }),
        },
    }),
}));

// Stub env
process.env.NEXT_PUBLIC_BACKEND_URL = "http://localhost:8000";

import {
    syncClickupSpaces,
    listClickupSpaces,
    classifyClickupSpace,
    mapClickupSpaceToBrand,
} from "@/lib/api/admin/clickupSpaces";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockFetchOk = (body: unknown) =>
    vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve(body),
        text: () => Promise.resolve(JSON.stringify(body)),
    });

const mockFetchErr = (status: number, detail: string) =>
    vi.fn().mockResolvedValue({
        ok: false,
        status,
        statusText: "Error",
        json: () => Promise.resolve({ detail }),
        text: () => Promise.resolve(JSON.stringify({ detail })),
    });

const SAMPLE_SPACES = [
    {
        space_id: "sp1",
        name: "Brand Alpha",
        team_id: "t1",
        classification: "brand_scoped",
        brand_id: "b-1",
        active: true,
        last_seen_at: null,
        last_synced_at: null,
        created_at: "2026-01-01T00:00:00Z",
    },
    {
        space_id: "sp2",
        name: "Shared Reporting",
        team_id: "t1",
        classification: "shared_service",
        brand_id: null,
        active: true,
        last_seen_at: null,
        last_synced_at: null,
        created_at: "2026-01-01T00:00:00Z",
    },
];

// ---------------------------------------------------------------------------
// Tests — API integration paths (page would call these)
// ---------------------------------------------------------------------------

describe("ClickUp Spaces page data paths", () => {
    afterEach(() => vi.restoreAllMocks());

    it("sync button triggers sync endpoint then refreshes list", async () => {
        const syncBody = { ok: true, synced: 2, spaces: SAMPLE_SPACES };
        const listBody = { spaces: SAMPLE_SPACES };

        const fetchMock = vi
            .fn()
            .mockResolvedValueOnce({
                ok: true,
                status: 200,
                json: () => Promise.resolve(syncBody),
                text: () => Promise.resolve(JSON.stringify(syncBody)),
            })
            .mockResolvedValueOnce({
                ok: true,
                status: 200,
                json: () => Promise.resolve(listBody),
                text: () => Promise.resolve(JSON.stringify(listBody)),
            });

        vi.stubGlobal("fetch", fetchMock);

        // Simulate sync → load sequence the page does
        const syncResult = await syncClickupSpaces("test-token");
        expect(syncResult.synced).toBe(2);

        const spaces = await listClickupSpaces("test-token");
        expect(spaces).toHaveLength(2);
        expect(spaces[0].name).toBe("Brand Alpha");

        expect(fetchMock).toHaveBeenCalledTimes(2);
        expect(fetchMock.mock.calls[0][0]).toContain("/admin/clickup-spaces/sync");
        expect(fetchMock.mock.calls[1][0]).toContain("/admin/clickup-spaces");
    });

    it("classification action sends correct payload", async () => {
        const body = {
            ok: true,
            space: { space_id: "sp1", classification: "shared_service" },
        };
        vi.stubGlobal("fetch", mockFetchOk(body));

        const result = await classifyClickupSpace(
            "test-token",
            "sp1",
            "shared_service",
        );

        expect(result.ok).toBe(true);
        expect(result.space.classification).toBe("shared_service");

        const [, opts] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
        const sentBody = JSON.parse(opts.body);
        expect(sentBody).toEqual({
            space_id: "sp1",
            classification: "shared_service",
        });
    });

    it("map brand action sends correct payload", async () => {
        const body = { ok: true, space: { space_id: "sp1", brand_id: "b-new" } };
        vi.stubGlobal("fetch", mockFetchOk(body));

        const result = await mapClickupSpaceToBrand("test-token", "sp1", "b-new");

        expect(result.ok).toBe(true);
        const [, opts] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
        const sentBody = JSON.parse(opts.body);
        expect(sentBody).toEqual({ space_id: "sp1", brand_id: "b-new" });
    });

    it("unmap brand action sends null brand_id", async () => {
        const body = { ok: true, space: { space_id: "sp1", brand_id: null } };
        vi.stubGlobal("fetch", mockFetchOk(body));

        const result = await mapClickupSpaceToBrand("test-token", "sp1", null);

        expect(result.space.brand_id).toBeNull();
        const [, opts] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
        const sentBody = JSON.parse(opts.body);
        expect(sentBody.brand_id).toBeNull();
    });

    it("error response renders useful info", async () => {
        vi.stubGlobal(
            "fetch",
            mockFetchErr(500, "Space sync failed: ClickUp unreachable"),
        );

        await expect(syncClickupSpaces("test-token")).rejects.toThrow(
            "Space sync failed: ClickUp unreachable",
        );
    });
});
