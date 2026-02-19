"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import {
    type ClickupSpace,
    type SpaceClassification,
    syncClickupSpaces,
    listClickupSpaces,
    classifyClickupSpace,
    mapClickupSpaceToBrand,
} from "@/lib/api/admin/clickupSpaces";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const CLASSIFICATION_OPTIONS: SpaceClassification[] = [
    "brand_scoped",
    "shared_service",
    "unknown",
];

const classificationMeta = (c: SpaceClassification) => {
    if (c === "brand_scoped")
        return { label: "Brand Scoped", cls: "bg-emerald-100 text-emerald-800" };
    if (c === "shared_service")
        return { label: "Shared Service", cls: "bg-blue-100 text-blue-800" };
    return { label: "Unknown", cls: "bg-slate-100 text-slate-700" };
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ClickupSpacesPage() {
    // State ------------------------------------------------------------------
    const [token, setToken] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [syncing, setSyncing] = useState(false);
    const [actionInFlight, setActionInFlight] = useState<string | null>(null);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);
    const [spaces, setSpaces] = useState<ClickupSpace[]>([]);

    // Filters
    const [search, setSearch] = useState("");
    const [classificationFilter, setClassificationFilter] = useState<
        "" | SpaceClassification
    >("");

    // Brand mapping inline edit
    const [editingBrandSpaceId, setEditingBrandSpaceId] = useState<string | null>(
        null,
    );
    const [editBrandValue, setEditBrandValue] = useState("");

    // Auth -------------------------------------------------------------------
    useEffect(() => {
        const supabase = getBrowserSupabaseClient();
        supabase.auth.getSession().then(({ data }: { data: { session: { access_token: string } | null } }) => {
            setToken(data.session?.access_token ?? null);
        });
    }, []);

    // Data loading -----------------------------------------------------------
    const loadSpaces = useCallback(async () => {
        if (!token) return;
        setLoading(true);
        setErrorMessage(null);
        try {
            const data = await listClickupSpaces(token, {
                classification: classificationFilter || undefined,
            });
            setSpaces(data);
        } catch (err) {
            setSpaces([]);
            setErrorMessage(
                err instanceof Error ? err.message : "Unable to load spaces",
            );
        } finally {
            setLoading(false);
        }
    }, [token, classificationFilter]);

    useEffect(() => {
        if (token) {
            loadSpaces();
        }
    }, [token, loadSpaces]);

    // Filtered view ----------------------------------------------------------
    const filtered = useMemo(() => {
        const q = search.trim().toLowerCase();
        if (!q) return spaces;
        return spaces.filter(
            (s) =>
                s.name.toLowerCase().includes(q) ||
                s.space_id.toLowerCase().includes(q) ||
                s.team_id.toLowerCase().includes(q),
        );
    }, [spaces, search]);

    // Flash helpers ----------------------------------------------------------
    const flash = useCallback((msg: string) => {
        setSuccessMessage(msg);
        setTimeout(() => setSuccessMessage(null), 3000);
    }, []);

    // Actions ----------------------------------------------------------------
    const onSync = useCallback(async () => {
        if (!token) return;
        setSyncing(true);
        setErrorMessage(null);
        try {
            const result = await syncClickupSpaces(token);
            flash(`Synced ${result.synced} space${result.synced === 1 ? "" : "s"}`);
            await loadSpaces();
        } catch (err) {
            setErrorMessage(
                err instanceof Error ? err.message : "Sync failed",
            );
        } finally {
            setSyncing(false);
        }
    }, [token, loadSpaces, flash]);

    const onClassify = useCallback(
        async (spaceId: string, classification: SpaceClassification) => {
            if (!token) return;
            setActionInFlight(spaceId);
            setErrorMessage(null);
            try {
                await classifyClickupSpace(token, spaceId, classification);
                flash(`Classified as ${classification.replace("_", " ")}`);
                await loadSpaces();
            } catch (err) {
                setErrorMessage(
                    err instanceof Error ? err.message : "Classification failed",
                );
            } finally {
                setActionInFlight(null);
            }
        },
        [token, loadSpaces, flash],
    );

    const onMapBrand = useCallback(
        async (spaceId: string, brandId: string | null) => {
            if (!token) return;
            setActionInFlight(spaceId);
            setErrorMessage(null);
            try {
                await mapClickupSpaceToBrand(token, spaceId, brandId);
                flash(brandId ? `Mapped to brand ${brandId}` : "Brand unmapped");
                setEditingBrandSpaceId(null);
                setEditBrandValue("");
                await loadSpaces();
            } catch (err) {
                setErrorMessage(
                    err instanceof Error ? err.message : "Brand mapping failed",
                );
            } finally {
                setActionInFlight(null);
            }
        },
        [token, loadSpaces, flash],
    );

    const busy = syncing || actionInFlight !== null;

    // Render -----------------------------------------------------------------
    return (
        <main className="space-y-6">
            {/* Header */}
            <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                        <h1 className="text-2xl font-semibold text-[#0f172a]">
                            ClickUp Spaces
                        </h1>
                        <p className="mt-2 text-sm text-[#4c576f]">
                            Sync, classify, and map ClickUp spaces to brands for safe task
                            routing.
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
                        <button
                            onClick={onSync}
                            disabled={busy || !token}
                            className="rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {syncing ? "Syncing…" : "Sync Spaces"}
                        </button>
                        <Link
                            href="/command-center"
                            className="text-sm font-semibold text-[#0a6fd6] hover:underline"
                        >
                            Back to Command Center
                        </Link>
                    </div>
                </div>

                {/* Success toast */}
                {successMessage ? (
                    <p className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                        {successMessage}
                    </p>
                ) : null}

                {/* Error banner */}
                {errorMessage ? (
                    <p className="mt-4 rounded-2xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
                        {errorMessage}
                    </p>
                ) : null}
            </div>

            {/* Filter bar */}
            <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
                <div className="flex flex-wrap items-center gap-3">
                    <input
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="min-w-[240px] flex-1 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm"
                        placeholder="Search by name, space ID, or team ID…"
                        disabled={loading}
                    />
                    <select
                        value={classificationFilter}
                        onChange={(e) =>
                            setClassificationFilter(
                                e.target.value as "" | SpaceClassification,
                            )
                        }
                        className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-[#0f172a] shadow"
                        disabled={loading}
                    >
                        <option value="">All classifications</option>
                        {CLASSIFICATION_OPTIONS.map((c) => (
                            <option key={c} value={c}>
                                {classificationMeta(c).label}
                            </option>
                        ))}
                    </select>
                </div>
            </div>

            {/* Table */}
            <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
                <h2 className="text-lg font-semibold text-[#0f172a]">
                    Registered Spaces
                </h2>

                {loading ? (
                    <p className="mt-4 text-sm text-[#4c576f]">Loading…</p>
                ) : filtered.length === 0 ? (
                    <p className="mt-4 text-sm text-[#4c576f]">
                        {spaces.length === 0
                            ? "No spaces registered. Click \"Sync Spaces\" to import from ClickUp."
                            : "No spaces match your filters."}
                    </p>
                ) : (
                    <div className="mt-4 overflow-x-auto rounded-2xl border border-slate-200 bg-white">
                        <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                            <thead className="bg-[#f7faff]">
                                <tr className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">
                                    <th className="px-4 py-3">Name</th>
                                    <th className="px-4 py-3">Space ID</th>
                                    <th className="px-4 py-3">Team ID</th>
                                    <th className="px-4 py-3">Classification</th>
                                    <th className="px-4 py-3">Brand</th>
                                    <th className="px-4 py-3 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-200 bg-white">
                                {filtered.map((space) => {
                                    const meta = classificationMeta(space.classification);
                                    const isEditing = editingBrandSpaceId === space.space_id;
                                    const isActionTarget = actionInFlight === space.space_id;

                                    return (
                                        <tr
                                            key={space.space_id}
                                            className="align-top hover:bg-slate-50"
                                        >
                                            <td className="px-4 py-4 font-semibold text-[#0f172a]">
                                                {space.name}
                                            </td>
                                            <td className="px-4 py-4 font-mono text-xs text-slate-600">
                                                {space.space_id}
                                            </td>
                                            <td className="px-4 py-4 font-mono text-xs text-slate-600">
                                                {space.team_id}
                                            </td>
                                            <td className="px-4 py-4">
                                                <select
                                                    value={space.classification}
                                                    onChange={(e) =>
                                                        onClassify(
                                                            space.space_id,
                                                            e.target.value as SpaceClassification,
                                                        )
                                                    }
                                                    disabled={busy}
                                                    className={`rounded-full px-2.5 py-1 text-xs font-semibold ${meta.cls} cursor-pointer border-0 outline-none disabled:cursor-not-allowed disabled:opacity-60`}
                                                >
                                                    {CLASSIFICATION_OPTIONS.map((c) => (
                                                        <option key={c} value={c}>
                                                            {classificationMeta(c).label}
                                                        </option>
                                                    ))}
                                                </select>
                                            </td>
                                            <td className="px-4 py-4">
                                                {isEditing ? (
                                                    <div className="flex items-center gap-2">
                                                        <input
                                                            value={editBrandValue}
                                                            onChange={(e) =>
                                                                setEditBrandValue(e.target.value)
                                                            }
                                                            className="w-48 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs"
                                                            placeholder="Brand ID (UUID)"
                                                            disabled={isActionTarget}
                                                        />
                                                        <button
                                                            onClick={() =>
                                                                onMapBrand(
                                                                    space.space_id,
                                                                    editBrandValue.trim() || null,
                                                                )
                                                            }
                                                            disabled={isActionTarget}
                                                            className="rounded-xl bg-[#0a6fd6] px-2 py-1 text-xs font-semibold text-white hover:bg-[#0959ab] disabled:opacity-60"
                                                        >
                                                            {isActionTarget ? "…" : "Save"}
                                                        </button>
                                                        <button
                                                            onClick={() => {
                                                                setEditingBrandSpaceId(null);
                                                                setEditBrandValue("");
                                                            }}
                                                            disabled={isActionTarget}
                                                            className="rounded-xl bg-white px-2 py-1 text-xs font-semibold text-[#0f172a] shadow hover:shadow-lg disabled:opacity-60"
                                                        >
                                                            Cancel
                                                        </button>
                                                    </div>
                                                ) : (
                                                    <div className="flex items-center gap-2">
                                                        {space.brand_id ? (
                                                            <span className="rounded-full bg-[#f1f5ff] px-3 py-1 text-xs font-semibold text-[#0f172a]">
                                                                {space.brand_id}
                                                            </span>
                                                        ) : (
                                                            <span className="text-xs text-[#64748b]">
                                                                Unmapped
                                                            </span>
                                                        )}
                                                        <button
                                                            onClick={() => {
                                                                setEditingBrandSpaceId(space.space_id);
                                                                setEditBrandValue(space.brand_id ?? "");
                                                            }}
                                                            disabled={busy}
                                                            className="rounded-xl bg-white px-2 py-1 text-xs font-semibold text-[#0a6fd6] shadow transition hover:shadow-lg disabled:opacity-60"
                                                        >
                                                            {space.brand_id ? "Change" : "Map"}
                                                        </button>
                                                        {space.brand_id ? (
                                                            <button
                                                                onClick={() =>
                                                                    onMapBrand(space.space_id, null)
                                                                }
                                                                disabled={busy}
                                                                className="rounded-xl bg-white px-2 py-1 text-xs font-semibold text-[#b91c1c] shadow transition hover:shadow-lg disabled:opacity-60"
                                                            >
                                                                Unmap
                                                            </button>
                                                        ) : null}
                                                    </div>
                                                )}
                                                {isEditing ? (
                                                    <p className="mt-1 text-xs text-[#64748b]">
                                                        Enter the brand UUID. Brand lookup is not yet
                                                        available from this endpoint.
                                                    </p>
                                                ) : null}
                                            </td>
                                            <td className="px-4 py-4 text-right">
                                                {isActionTarget ? (
                                                    <span className="text-xs text-[#4c576f]">
                                                        Working…
                                                    </span>
                                                ) : null}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}

                <div className="mt-3 text-xs text-slate-500">
                    {filtered.length} space{filtered.length === 1 ? "" : "s"} shown
                </div>
            </div>
        </main>
    );
}
