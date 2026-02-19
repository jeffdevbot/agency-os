/**
 * API client for ClickUp Space Registry admin endpoints (C6B).
 *
 * Calls the FastAPI backend directly via NEXT_PUBLIC_BACKEND_URL.
 * All functions require a Supabase JWT access token for admin auth.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type SpaceClassification = "brand_scoped" | "shared_service" | "unknown";

export type ClickupSpace = {
    space_id: string;
    name: string;
    team_id: string;
    classification: SpaceClassification;
    brand_id: string | null;
    active: boolean;
    last_seen_at: string | null;
    last_synced_at: string | null;
    created_at: string;
};

export type SyncResult = {
    ok: boolean;
    synced: number;
    spaces: ClickupSpace[];
};

export type ListSpacesParams = {
    classification?: SpaceClassification;
    include_inactive?: boolean;
    search?: string;
};

export type SpaceActionResult = {
    ok: boolean;
    space: ClickupSpace;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const getBackendUrl = (): string => {
    const url = process.env.NEXT_PUBLIC_BACKEND_URL;
    if (!url) {
        throw new Error("NEXT_PUBLIC_BACKEND_URL is not configured");
    }
    return url;
};

const parseErrorDetail = async (response: Response): Promise<string> => {
    try {
        const body = await response.json();
        if (typeof body?.detail === "string") return body.detail;
        if (typeof body?.message === "string") return body.message;
        return JSON.stringify(body);
    } catch {
        return response.statusText || `HTTP ${response.status}`;
    }
};

const authHeaders = (token: string): Record<string, string> => ({
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
});

// ---------------------------------------------------------------------------
// API Functions
// ---------------------------------------------------------------------------

/**
 * Trigger a sync of ClickUp spaces from the workspace into the registry.
 */
export const syncClickupSpaces = async (token: string): Promise<SyncResult> => {
    const response = await fetch(`${getBackendUrl()}/admin/clickup-spaces/sync`, {
        method: "POST",
        headers: authHeaders(token),
    });
    if (!response.ok) {
        const detail = await parseErrorDetail(response);
        throw new Error(`Sync failed (${response.status}): ${detail}`);
    }
    return (await response.json()) as SyncResult;
};

/**
 * List registered ClickUp spaces with optional filters.
 */
export const listClickupSpaces = async (
    token: string,
    params?: ListSpacesParams,
): Promise<ClickupSpace[]> => {
    const url = new URL(`${getBackendUrl()}/admin/clickup-spaces`);
    if (params?.classification) {
        url.searchParams.set("classification", params.classification);
    }
    if (params?.include_inactive) {
        url.searchParams.set("include_inactive", "true");
    }

    const response = await fetch(url.toString(), {
        method: "GET",
        headers: authHeaders(token),
    });
    if (!response.ok) {
        const detail = await parseErrorDetail(response);
        throw new Error(`Failed to list spaces (${response.status}): ${detail}`);
    }
    const body = (await response.json()) as { spaces: ClickupSpace[] };
    return body.spaces ?? [];
};

/**
 * Update the classification of a registered ClickUp space.
 */
export const classifyClickupSpace = async (
    token: string,
    spaceId: string,
    classification: SpaceClassification,
): Promise<SpaceActionResult> => {
    const response = await fetch(
        `${getBackendUrl()}/admin/clickup-spaces/classify`,
        {
            method: "POST",
            headers: authHeaders(token),
            body: JSON.stringify({ space_id: spaceId, classification }),
        },
    );
    if (!response.ok) {
        const detail = await parseErrorDetail(response);
        throw new Error(`Classification failed (${response.status}): ${detail}`);
    }
    return (await response.json()) as SpaceActionResult;
};

/**
 * Map (or unmap) a registered ClickUp space to a brand.
 * Pass `null` for brandId to unmap.
 */
export const mapClickupSpaceToBrand = async (
    token: string,
    spaceId: string,
    brandId: string | null,
): Promise<SpaceActionResult> => {
    const response = await fetch(
        `${getBackendUrl()}/admin/clickup-spaces/map-brand`,
        {
            method: "POST",
            headers: authHeaders(token),
            body: JSON.stringify({ space_id: spaceId, brand_id: brandId }),
        },
    );
    if (!response.ok) {
        const detail = await parseErrorDetail(response);
        throw new Error(`Brand mapping failed (${response.status}): ${detail}`);
    }
    return (await response.json()) as SpaceActionResult;
};
