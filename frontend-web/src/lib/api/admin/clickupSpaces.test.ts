/**
 * Tests for ClickUp Spaces API client (C6B).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Set env before importing module
process.env.NEXT_PUBLIC_BACKEND_URL = "http://localhost:8000";

import {
    syncClickupSpaces,
    listClickupSpaces,
    classifyClickupSpace,
    mapClickupSpaceToBrand,
} from "./clickupSpaces";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const TOKEN = "test-jwt-token";

const mockFetch = (status: number, body: unknown) => {
    return vi.fn().mockResolvedValue({
        ok: status >= 200 && status < 300,
        status,
        statusText: status === 200 ? "OK" : "Error",
        json: () => Promise.resolve(body),
        text: () => Promise.resolve(JSON.stringify(body)),
    });
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("syncClickupSpaces", () => {
    afterEach(() => vi.restoreAllMocks());

    it("returns sync result on success", async () => {
        const body = { ok: true, synced: 2, spaces: [{ space_id: "sp1" }, { space_id: "sp2" }] };
        vi.stubGlobal("fetch", mockFetch(200, body));

        const result = await syncClickupSpaces(TOKEN);

        expect(result.ok).toBe(true);
        expect(result.synced).toBe(2);
        expect(result.spaces).toHaveLength(2);

        const [url, opts] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
        expect(url).toBe("http://localhost:8000/admin/clickup-spaces/sync");
        expect(opts.method).toBe("POST");
        expect(opts.headers.Authorization).toBe(`Bearer ${TOKEN}`);
    });

    it("throws on error response", async () => {
        vi.stubGlobal("fetch", mockFetch(500, { detail: "ClickUp not configured" }));
        await expect(syncClickupSpaces(TOKEN)).rejects.toThrow("Sync failed (500)");
    });
});

describe("listClickupSpaces", () => {
    afterEach(() => vi.restoreAllMocks());

    it("returns spaces on success", async () => {
        const body = { spaces: [{ space_id: "sp1", name: "Test" }] };
        vi.stubGlobal("fetch", mockFetch(200, body));

        const result = await listClickupSpaces(TOKEN);

        expect(result).toHaveLength(1);
        expect(result[0].space_id).toBe("sp1");
    });

    it("passes query params when provided", async () => {
        vi.stubGlobal("fetch", mockFetch(200, { spaces: [] }));

        await listClickupSpaces(TOKEN, {
            classification: "brand_scoped",
            include_inactive: true,
        });

        const [url] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
        expect(url).toContain("classification=brand_scoped");
        expect(url).toContain("include_inactive=true");
    });

    it("throws on error response", async () => {
        vi.stubGlobal("fetch", mockFetch(403, { detail: "Admin access required" }));
        await expect(listClickupSpaces(TOKEN)).rejects.toThrow("Failed to list spaces (403)");
    });
});

describe("classifyClickupSpace", () => {
    afterEach(() => vi.restoreAllMocks());

    it("returns action result on success", async () => {
        const body = { ok: true, space: { space_id: "sp1", classification: "brand_scoped" } };
        vi.stubGlobal("fetch", mockFetch(200, body));

        const result = await classifyClickupSpace(TOKEN, "sp1", "brand_scoped");

        expect(result.ok).toBe(true);
        expect(result.space.classification).toBe("brand_scoped");

        const [, opts] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
        const sentBody = JSON.parse(opts.body);
        expect(sentBody.space_id).toBe("sp1");
        expect(sentBody.classification).toBe("brand_scoped");
    });

    it("throws on error response", async () => {
        vi.stubGlobal("fetch", mockFetch(400, { detail: "Invalid classification 'bad'" }));
        await expect(classifyClickupSpace(TOKEN, "sp1", "unknown")).rejects.toThrow(
            "Classification failed (400)",
        );
    });
});

describe("mapClickupSpaceToBrand", () => {
    afterEach(() => vi.restoreAllMocks());

    it("maps a brand on success", async () => {
        const body = { ok: true, space: { space_id: "sp1", brand_id: "b-1" } };
        vi.stubGlobal("fetch", mockFetch(200, body));

        const result = await mapClickupSpaceToBrand(TOKEN, "sp1", "b-1");

        expect(result.ok).toBe(true);
        expect(result.space.brand_id).toBe("b-1");

        const [, opts] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
        const sentBody = JSON.parse(opts.body);
        expect(sentBody.space_id).toBe("sp1");
        expect(sentBody.brand_id).toBe("b-1");
    });

    it("unmaps brand with null", async () => {
        const body = { ok: true, space: { space_id: "sp1", brand_id: null } };
        vi.stubGlobal("fetch", mockFetch(200, body));

        const result = await mapClickupSpaceToBrand(TOKEN, "sp1", null);

        expect(result.space.brand_id).toBeNull();

        const [, opts] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
        const sentBody = JSON.parse(opts.body);
        expect(sentBody.brand_id).toBeNull();
    });

    it("throws on error response", async () => {
        vi.stubGlobal("fetch", mockFetch(400, { detail: "Space not found" }));
        await expect(mapClickupSpaceToBrand(TOKEN, "sp-missing", "b-1")).rejects.toThrow(
            "Brand mapping failed (400)",
        );
    });
});
