"use client";

import { useState, useEffect } from "react";
import clsx from "clsx";

interface GeneratedContent {
  id: string;
  projectId: string;
  skuId: string;
  version: number;
  title: string;
  bullets: string[];
  description: string;
  backendKeywords: string;
  modelUsed: string | null;
  promptVersion: string | null;
  approved: boolean;
  approvedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

type AttributePreferences = {
  mode?: "auto" | "overrides";
  rules?: Record<string, { sections: ("title" | "bullets" | "description" | "backend_keywords")[] }>;
} | null;

interface Sku {
  id: string;
  skuCode: string;
  productName: string | null;
  attributePreferences?: AttributePreferences;
}

interface StageCProps {
  projectId: string;
  projectStatus: string | null;
  skus: Sku[];
  onApprove: () => void;
  onUnapprove: () => void;
  onExport: () => void;
  exportLoading: boolean;
  approveLoading: boolean;
  isArchived: boolean;
}

export default function StageC({
  projectId,
  projectStatus,
  skus,
  onApprove,
  onUnapprove,
  onExport,
  exportLoading,
  approveLoading,
  isArchived,
}: StageCProps) {
  const normalizeStageStatus = (status: string | null | undefined): string => {
    const value = typeof status === "string" ? status.toLowerCase() : "draft";
    if (value === "stage_a_approved") return "stage_a_approved";
    if (value === "stage_b_approved") return "stage_b_approved";
    if (value === "stage_c_approved") return "stage_c_approved";
    if (value === "approved") return "approved";
    if (value === "archived") return "archived";
    return "draft";
  };
  const normalizedStatus = normalizeStageStatus(projectStatus);
  const [contents, setContents] = useState<Record<string, GeneratedContent | null>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generatingAll, setGeneratingAll] = useState(false);
  const [generatingSample, setGeneratingSample] = useState(false);
  const [regeneratingSkus, setRegeneratingSkus] = useState<Set<string>>(new Set());
  const [editingSkus, setEditingSkus] = useState<Record<string, Partial<GeneratedContent>>>({});
  const [savingSkus, setSavingSkus] = useState<Set<string>>(new Set());
  const [bulkPrefs, setBulkPrefs] = useState<AttributePreferences>({ mode: "auto" });
  const [savingAllPrefs, setSavingAllPrefs] = useState(false);
  const [variantAttributes, setVariantAttributes] = useState<{ id: string; name: string }[]>([]);
  const [attrsLoading, setAttrsLoading] = useState(false);
  const [lastSavedPrefsKey, setLastSavedPrefsKey] = useState<string>("");
  const [attrPrefsOpen, setAttrPrefsOpen] = useState<Record<string, boolean>>({});

  const isStageUnlocked =
    normalizedStatus === "stage_b_approved" ||
    normalizedStatus === "stage_c_approved" ||
    normalizedStatus === "approved";
  const isLocked = !isStageUnlocked;
  const isStageCLocked = normalizedStatus === "stage_c_approved" || normalizedStatus === "approved";
  const canUnapproveC = normalizedStatus === "stage_c_approved";
  const isLockedByApproved = normalizedStatus === "approved";
  const canExport = normalizedStatus === "stage_c_approved" || normalizedStatus === "approved";

  // Load generated content for all SKUs
  useEffect(() => {
    const loadContents = async () => {
      setLoading(true);
      try {
        const contentBySku: Record<string, GeneratedContent | null> = {};

        for (const sku of skus) {
          const res = await fetch(`/api/scribe/projects/${projectId}/generated-content/${sku.id}`);
          if (res.ok) {
            const data = (await res.json()) as GeneratedContent;
            contentBySku[sku.id] = data;
          } else if (res.status === 404) {
            contentBySku[sku.id] = null;
          }
        }

        setContents(contentBySku);
      } catch (err) {
        console.error("Failed to load generated content:", err);
      } finally {
        setLoading(false);
      }
    };

    if (skus.length > 0) {
      void loadContents();
    }
  }, [projectId, skus]);

  const handleGenerateAll = async () => {
    setGeneratingAll(true);
    setError(null);

    try {
      const res = await fetch(`/api/scribe/projects/${projectId}/generate-copy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "all" }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? "Failed to generate copy");
      }

      const { jobId } = (await res.json()) as { jobId: string };
      await pollJobStatus(jobId, null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate copy");
      setGeneratingAll(false);
    }
  };

  const handleGenerateSample = async () => {
    if (skus.length === 0) return;

    setGeneratingSample(true);
    setError(null);

    try {
      const res = await fetch(`/api/scribe/projects/${projectId}/generate-copy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "sample", skuIds: [skus[0].id] }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? "Failed to generate sample");
      }

      const { jobId } = (await res.json()) as { jobId: string };
      await pollJobStatus(jobId, skus[0].id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate sample");
      setGeneratingSample(false);
    }
  };

  const handleRegenerate = async (skuId: string) => {
    setRegeneratingSkus((prev) => new Set(prev).add(skuId));
    setError(null);

    try {
      const res = await fetch(`/api/scribe/projects/${projectId}/skus/${skuId}/regenerate-copy`, {
        method: "POST",
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? "Failed to regenerate copy");
      }

      const { jobId } = (await res.json()) as { jobId: string };
      await pollJobStatus(jobId, skuId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to regenerate copy");
      setRegeneratingSkus((prev) => {
        const next = new Set(prev);
        next.delete(skuId);
        return next;
      });
    }
  };

  const pollJobStatus = async (jobId: string, skuId: string | null) => {
    const poll = async (): Promise<void> => {
      const res = await fetch(`/api/scribe/jobs/${jobId}`);
      if (!res.ok) return;

      const job = (await res.json()) as { status: string };

      if (job.status === "succeeded") {
        // Reload content for affected SKUs
        if (skuId) {
          await reloadContent(skuId);
          setRegeneratingSkus((prev) => {
            const next = new Set(prev);
            next.delete(skuId);
            return next;
          });
        } else {
          // Reload all SKUs
          for (const sku of skus) {
            await reloadContent(sku.id);
          }
          setGeneratingAll(false);
          setGeneratingSample(false);
        }
      } else if (job.status === "failed") {
        setError("Generation failed. Please try again.");
        setGeneratingAll(false);
        setGeneratingSample(false);
        if (skuId) {
          setRegeneratingSkus((prev) => {
            const next = new Set(prev);
            next.delete(skuId);
            return next;
          });
        }
      } else if (job.status === "queued" || job.status === "running") {
        setTimeout(() => void poll(), 2000);
      }
    };

    await poll();
  };

  const reloadContent = async (skuId: string) => {
    const res = await fetch(`/api/scribe/projects/${projectId}/generated-content/${skuId}`);
    if (res.ok) {
      const data = (await res.json()) as GeneratedContent;
      setContents((prev) => ({ ...prev, [skuId]: data }));
      setEditingSkus((prev) => ({ ...prev, [skuId]: data }));
    }
  };

  const handleSave = async (skuId: string) => {
    const edits = editingSkus[skuId];
    if (!edits) return;

    setSavingSkus((prev) => new Set(prev).add(skuId));
    setError(null);

    try {
      const body: Partial<{
        title: string;
        bullets: string[];
        description: string;
        backend_keywords: string;
      }> = {};
      if (edits.title !== undefined) body.title = edits.title;
      if (edits.bullets !== undefined) body.bullets = edits.bullets;
      if (edits.description !== undefined) body.description = edits.description;
      if (edits.backendKeywords !== undefined) body.backend_keywords = edits.backendKeywords;

      const res = await fetch(`/api/scribe/projects/${projectId}/generated-content/${skuId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const responseBody = await res.json().catch(() => ({}));
        throw new Error(responseBody?.error?.message ?? "Failed to save");
      }

      const updated = (await res.json()) as GeneratedContent;
      setContents((prev) => ({ ...prev, [skuId]: updated }));
      setEditingSkus((prev) => ({ ...prev, [skuId]: updated }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSavingSkus((prev) => {
        const next = new Set(prev);
        next.delete(skuId);
        return next;
      });
    }
  };

  const updateEditField = (
    skuId: string,
    field: keyof GeneratedContent,
    value: GeneratedContent[keyof GeneratedContent],
  ) => {
    setEditingSkus((prev) => ({
      ...prev,
      [skuId]: {
        ...(prev[skuId] || contents[skuId] || {}),
        [field]: value,
      },
    }));
  };

  const handleSaveAttrPrefsAll = async (prefs: AttributePreferences) => {
    if (!prefs) return;
    setSavingAllPrefs(true);
    setError(null);
    try {
      await Promise.all(
        skus.map((sku) =>
          fetch(`/api/scribe/projects/${projectId}/skus/${sku.id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ attribute_preferences: prefs }),
          }).then((res) => {
            if (!res.ok) {
              return res.json().then((body) => {
                throw new Error(body?.error?.message ?? "Failed to save preferences");
              });
            }
            return res;
          }),
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save preferences");
    } finally {
      setSavingAllPrefs(false);
    }
  };

  useEffect(() => {
    if (skus.length > 0) {
      const firstPrefs = skus[0].attributePreferences;
      setBulkPrefs(firstPrefs ?? { mode: "auto" });
    }
  }, [skus]);

  // Load variant attributes for checkbox rendering
  useEffect(() => {
    const loadAttrs = async () => {
      setAttrsLoading(true);
      try {
        const res = await fetch(`/api/scribe/projects/${projectId}/variant-attributes`);
        if (!res.ok) {
          throw new Error("Failed to load variant attributes");
        }
        const rows = (await res.json()) as { id: string; name: string }[];
        setVariantAttributes(rows || []);
      } catch (err) {
        // prefer non-blocking: show no attrs if fetch fails
        setVariantAttributes([]);
        console.error(err);
      } finally {
        setAttrsLoading(false);
      }
    };
    void loadAttrs();
  }, [projectId]);

  // Persist bulk prefs when they change (avoid duplicate saves)
  useEffect(() => {
    const nextKey = JSON.stringify(bulkPrefs ?? {});
    if (nextKey === lastSavedPrefsKey) return;
    setLastSavedPrefsKey(nextKey);
    if (bulkPrefs) void handleSaveAttrPrefsAll(bulkPrefs);
  }, [bulkPrefs, lastSavedPrefsKey]);

  // Initialize editing state for each SKU
  useEffect(() => {
    const initial: Record<string, Partial<GeneratedContent>> = {};
    Object.entries(contents).forEach(([skuId, content]) => {
      if (content) {
        initial[skuId] = content;
      }
    });
    setEditingSkus(initial);
  }, [contents]);

  const hasAnyContent = Object.values(contents).some((c) => c !== null);
  const canApprove = skus.every((sku) => contents[sku.id] !== null);

  if (isLocked) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border-2 border-slate-300 bg-slate-50 py-16">
        <p className="text-lg font-semibold text-slate-700">Stage C is locked</p>
        <p className="text-sm text-slate-600">Unlock Stage C after Stage B approval</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-sm text-slate-600">Loading generated content...</p>
      </div>
    );
  }

  // Empty state
  if (!hasAnyContent) {
    return (
      <div className="flex flex-col gap-6">
        {error && (
          <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
        )}

        <div className="rounded-2xl border-2 border-slate-300 bg-white p-8">
          <h3 className="mb-4 text-xl font-semibold text-slate-900">Stage C: Copy Generation</h3>
          <div className="mb-6 space-y-2 text-sm text-slate-600">
            <p>
              Generate Amazon listing content (title, bullets, description, backend keywords) based on your approved
              topics from Stage B.
            </p>
            <p className="font-semibold">Requirements:</p>
            <ul className="list-disc pl-6">
              <li>Title: Max 200 characters</li>
              <li>Bullets: Exactly 5 bullets, max 500 characters each</li>
              <li>Description: Max 2000 characters</li>
              <li>Backend Keywords: Max 249 bytes</li>
            </ul>
          </div>

          <div className="flex gap-3">
            <button
              className="rounded-2xl bg-[#0a6fd6] px-6 py-3 text-sm font-semibold text-white shadow-lg transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:opacity-50"
              onClick={handleGenerateAll}
              disabled={generatingAll || isArchived || isStageCLocked}
            >
              {generatingAll ? "Generating..." : "Generate All"}
            </button>
            <button
              className="rounded-2xl border border-slate-300 px-6 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              onClick={handleGenerateSample}
              disabled={generatingSample || skus.length === 0 || isArchived || isStageCLocked}
            >
              {generatingSample ? "Generating..." : "Generate Sample (First SKU)"}
            </button>
          </div>

          {/* Attribute preferences can be set before first generation */}
          {skus.length > 0 && !isArchived && (
            <div className="mt-8 space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-slate-800">Attribute Preferences</p>
                  <p className="text-xs text-slate-600">
                    Decide how variant attributes should be used in copy before you generate.
                  </p>
                </div>
              </div>
              <div className="rounded-lg border border-dashed border-slate-300 bg-white p-3 shadow-sm">
                <p className="text-sm font-semibold text-slate-800">Attribute Preferences (All SKUs)</p>
                <p className="text-xs text-slate-600">Applies everywhere when you generate.</p>
                <div className="mt-3">
                  <AttributePreferencesControl
                    currentPrefs={bulkPrefs}
                    onChange={(prefs) => {
                      setBulkPrefs(prefs);
                      void handleSaveAttrPrefsAll(prefs);
                    }}
                    variantAttributes={variantAttributes}
                    loading={attrsLoading}
                    disabled={isStageCLocked}
                  />
                </div>
                {savingAllPrefs && <p className="mt-2 text-xs text-slate-500">Saving…</p>}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Bulk Attribute Preferences (always visible when SKUs exist) */}
      {skus.length > 0 && !isArchived && (
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          {savingAllPrefs && <p className="text-xs text-slate-500 text-right">Saving…</p>}
          <AttributePreferencesControl
            currentPrefs={bulkPrefs}
            onChange={(prefs) => {
              const prevKey = JSON.stringify(bulkPrefs ?? {});
              const nextKey = JSON.stringify(prefs ?? {});
              if (prevKey === nextKey) return;
              setBulkPrefs(prefs);
            }}
            variantAttributes={variantAttributes}
            loading={attrsLoading}
            disabled={isStageCLocked}
          />
        </div>
      )}

      {/* Approve / Unapprove Toolbar */}
      {!isArchived && (
        <div className="flex justify-end gap-3">
          {canExport && (
            <button
              className="rounded-2xl border border-slate-300 px-6 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              onClick={onExport}
              disabled={exportLoading}
            >
              {exportLoading ? "Exporting..." : "Export CSV"}
            </button>
          )}
          <button
            className={clsx(
              "rounded-2xl px-6 py-3 text-sm font-semibold text-white shadow-lg transition disabled:cursor-not-allowed disabled:opacity-50",
              canUnapproveC ? "bg-slate-600 hover:bg-slate-500" : "bg-emerald-600 hover:bg-emerald-500",
            )}
            onClick={canUnapproveC ? onUnapprove : onApprove}
            disabled={
              approveLoading ||
              isLockedByApproved ||
              (!canUnapproveC && (!canApprove || isStageCLocked))
            }
          >
            {approveLoading
              ? canUnapproveC
                ? "Unapproving..."
                : "Approving..."
              : canUnapproveC
                ? "Unapprove Stage C"
                : isLockedByApproved
                  ? "Stage C Locked"
                  : "Approve Stage C"}
          </button>
        </div>
      )}

      {error && (
        <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      {skus.map((sku) => {
        const content = contents[sku.id];
        const editing = editingSkus[sku.id] || content || {};
        const isRegenerating = regeneratingSkus.has(sku.id);
        const isSaving = savingSkus.has(sku.id);
        const attrPrefsExpanded = attrPrefsOpen[sku.id] ?? false;

        return (
          <div key={sku.id} className="rounded-2xl border-2 border-slate-300 bg-white shadow-lg">
            {/* SKU Header */}
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
              <div>
                <h3 className="text-lg font-semibold text-slate-900">SKU: {sku.skuCode}</h3>
                {sku.productName && <p className="text-sm text-slate-600">{sku.productName}</p>}
                {content && (
                  <p className="text-xs text-slate-500">
                    Version {content.version} • Updated {new Date(content.updatedAt).toLocaleString()}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-3">
                {!isArchived && (
                  <>
                    <button
                      className="rounded-2xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                      onClick={() => setAttrPrefsOpen((prev) => ({ ...prev, [sku.id]: !attrPrefsExpanded }))}
                      disabled={isRegenerating || isStageCLocked}
                    >
                      {attrPrefsExpanded ? "Hide Prefs" : "Attribute Prefs"}
                    </button>
                    <button
                      className="rounded-2xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                      onClick={() => handleRegenerate(sku.id)}
                      disabled={isRegenerating || isStageCLocked}
                    >
                      {isRegenerating ? "Regenerating..." : "Regenerate"}
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Content */}
            {content ? (
              <div className="space-y-4 px-6 py-4">
                {/* Title */}
                <div>
                  <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-600">
                    Title (max 200 chars)
                  </label>
                  <input
                    className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none disabled:bg-slate-100"
                    value={editing.title || ""}
                    onChange={(e) => updateEditField(sku.id, "title", e.target.value)}
                    maxLength={200}
                    disabled={isArchived || isStageCLocked}
                  />
                  <p className="mt-1 text-xs text-slate-500">{(editing.title || "").length} / 200</p>
                </div>

                {/* Bullets */}
                <div>
                  <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-600">
                    Bullets (exactly 5, max 500 chars each)
                  </label>
                  {(editing.bullets || []).map((bullet, idx) => (
                    <div key={idx} className="mb-2">
                      <textarea
                        className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none disabled:bg-slate-100"
                        value={bullet}
                        onChange={(e) => {
                          const newBullets = [...(editing.bullets || [])];
                          newBullets[idx] = e.target.value;
                          updateEditField(sku.id, "bullets", newBullets);
                        }}
                        rows={3}
                        maxLength={500}
                        disabled={isArchived || isStageCLocked}
                      />
                      <p className="mt-1 text-xs text-slate-500">
                        Bullet {idx + 1}: {bullet.length} / 500
                      </p>
                    </div>
                  ))}
                </div>

                {/* Description */}
                <div>
                  <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-600">
                    Description (max 2000 chars)
                  </label>
                  <textarea
                    className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none disabled:bg-slate-100"
                    value={editing.description || ""}
                    onChange={(e) => updateEditField(sku.id, "description", e.target.value)}
                    rows={6}
                    maxLength={2000}
                    disabled={isArchived || isStageCLocked}
                  />
                  <p className="mt-1 text-xs text-slate-500">{(editing.description || "").length} / 2000</p>
                </div>

                {/* Backend Keywords */}
                <div>
                  <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-600">
                    Backend Keywords (max 249 bytes)
                  </label>
                  <textarea
                    className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none disabled:bg-slate-100"
                    value={editing.backendKeywords || ""}
                    onChange={(e) => updateEditField(sku.id, "backendKeywords", e.target.value)}
                    rows={3}
                    disabled={isArchived || isStageCLocked}
                  />
                  <p className="mt-1 text-xs text-slate-500">
                    {new TextEncoder().encode(editing.backendKeywords || "").length} / 249 bytes
                  </p>
                </div>

                {/* Save Button */}
                {!isArchived && (
                  <div className="flex justify-end">
                    <button
                      className="rounded-2xl bg-emerald-600 px-6 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
                      onClick={() => handleSave(sku.id)}
                      disabled={isSaving || isStageCLocked}
                    >
                      {isSaving ? "Saving..." : "Save Changes"}
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="px-6 py-8 text-center">
                <p className="text-sm text-slate-600">No content generated yet.</p>
                {!isArchived && (
                  <button
                    className="mt-4 rounded-2xl bg-[#0a6fd6] px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:opacity-50"
                    onClick={() => handleRegenerate(sku.id)}
                    disabled={isRegenerating || isStageCLocked}
                  >
                    {isRegenerating ? "Generating..." : "Generate Copy"}
                  </button>
                )}
              </div>
            )}
          </div>
        );
      })}

    </div>
  );
}

const SECTION_LABELS: { key: "title" | "bullets" | "description" | "backend_keywords"; label: string }[] = [
  { key: "title", label: "Title" },
  { key: "bullets", label: "Bullets" },
  { key: "description", label: "Description" },
  { key: "backend_keywords", label: "Backend Keywords" },
];

function AttributePreferencesControl({
  currentPrefs,
  onChange,
  variantAttributes,
  loading,
  disabled = false,
}: {
  currentPrefs?: AttributePreferences;
  onChange: (prefs: AttributePreferences) => void;
  variantAttributes: { id: string; name: string }[];
  loading?: boolean;
  disabled?: boolean;
}) {
  const [mode, setMode] = useState<"auto" | "overrides">(currentPrefs?.mode || "auto");
  const [rules, setRules] = useState<Record<string, { sections: ("title" | "bullets" | "description" | "backend_keywords")[] }>>(
    currentPrefs?.rules || {},
  );

  useEffect(() => {
    const nextMode = currentPrefs?.mode || "auto";
    const nextRules = currentPrefs?.rules || {};
    const nextRulesKey = JSON.stringify(nextRules);
    setMode((prev) => (prev === nextMode ? prev : nextMode));
    setRules((prev) => {
      const prevKey = JSON.stringify(prev || {});
      return prevKey === nextRulesKey ? prev : nextRules;
    });
  }, [currentPrefs]);

  const toggleSection = (attrName: string, section: (typeof SECTION_LABELS)[number]["key"], checked: boolean) => {
    const existing = rules[attrName]?.sections || [];
    const nextSections = checked ? Array.from(new Set([...existing, section])) : existing.filter((s) => s !== section);
    const next = { ...rules };
    if (nextSections.length === 0) {
      delete next[attrName];
    } else {
      next[attrName] = { sections: nextSections };
    }
    setRules(next);
    if (mode === "overrides") {
      onChange({ mode: "overrides", rules: next });
    }
  };

  const isOverrides = mode === "overrides";

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-4">
        <label className="flex items-center gap-2">
          <input
            type="radio"
            checked={mode === "auto"}
            onChange={() => {
              setMode("auto");
              onChange({ mode: "auto" });
            }}
            className="h-4 w-4 text-blue-600"
            disabled={disabled}
          />
          <span className="text-sm text-slate-700">Auto (smart defaults)</span>
        </label>
        <label className="flex items-center gap-2">
          <input
            type="radio"
            checked={mode === "overrides"}
            onChange={() => {
              setMode("overrides");
              onChange({ mode: "overrides", rules });
            }}
            className="h-4 w-4 text-blue-600"
            disabled={disabled}
          />
          <span className="text-sm text-slate-700">Overrides (choose sections)</span>
        </label>
      </div>

      {loading ? (
        <p className="text-xs text-slate-500">Loading attributes…</p>
      ) : variantAttributes.length === 0 ? (
        <p className="text-xs text-slate-500">No variant attributes yet. Add attributes in Stage A to target them here.</p>
      ) : isOverrides ? (
        <div className="space-y-3 rounded border border-slate-200 bg-white p-3">
          {variantAttributes.map((attr) => {
            const selectedSections = rules[attr.name]?.sections || [];
            return (
              <div key={attr.id} className="flex flex-col gap-2 border-b border-slate-100 pb-3 last:border-b-0 last:pb-0">
                <p className="text-sm font-semibold text-slate-800">{attr.name}</p>
                <div className="flex flex-wrap gap-3">
                  {SECTION_LABELS.map((section) => (
                    <label key={section.key} className="flex items-center gap-2 text-sm text-slate-700">
                      <input
                        type="checkbox"
                        checked={selectedSections.includes(section.key)}
                        onChange={(e) => toggleSection(attr.name, section.key, e.target.checked)}
                        disabled={!isOverrides || disabled}
                        className="h-4 w-4 text-blue-600"
                      />
                      <span>{section.label}</span>
                    </label>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
