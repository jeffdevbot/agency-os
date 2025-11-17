"use client";

import { useMemo, useRef, useState, type ChangeEvent } from "react";
import type { ComposerSkuVariant } from "../../../../../../../lib/composer/types";
import { useSkuCsvImport } from "@/lib/composer/hooks/useSkuCsvImport";

interface SkuTableProps {
  projectId: string;
  variants: ComposerSkuVariant[];
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;
  onDelete: (variantId: string) => Promise<void>;
  onChange: React.Dispatch<React.SetStateAction<ComposerSkuVariant[]>>;
}

const isTemporaryId = (id: string | undefined) => !!id && id.startsWith("temp-");

const statusLabel = (isSaving: boolean, error: string | null) => {
  if (isSaving) return { text: "Saving…", className: "text-[#92400e]" };
  if (error) return { text: "Error saving SKUs", className: "text-[#b91c1c]" };
  return { text: "Saved", className: "text-[#15803d]" };
};

export const SkuTable = ({
  projectId,
  variants,
  isLoading,
  isSaving,
  error,
  onDelete,
  onChange,
}: SkuTableProps) => {
  const { isParsing, parseError, parseFromRaw } = useSkuCsvImport();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [manualAttributeKeys, setManualAttributeKeys] = useState<string[]>([]);

  const attributeKeys = useMemo(() => {
    const keys = new Set<string>(manualAttributeKeys);
    variants.forEach((variant) => {
      Object.keys(variant.attributes ?? {}).forEach((key) => {
        if (key) keys.add(key);
      });
    });
    return Array.from(keys).sort((a, b) => a.localeCompare(b));
  }, [manualAttributeKeys, variants]);

  const rowErrors = useMemo(() => {
    const result: Record<string, { sku?: string }> = {};
    variants.forEach((variant, index) => {
      const key = variant.id ?? variant.sku ?? `temp-${index}`;
      const sku = variant.sku?.trim() ?? "";
      const asin = variant.asin?.trim() ?? "";
      const parentSku = variant.parentSku?.trim() ?? "";
      const notes = variant.notes?.trim() ?? "";
      const hasAttributeData = Object.values(variant.attributes ?? {}).some(
        (value) => (value ?? "").toString().trim().length > 0,
      );
      const hasContent = asin || parentSku || notes || hasAttributeData;
      if (!sku && hasContent) {
        result[key] = { sku: "SKU required" };
      }
    });
    return result;
  }, [variants]);

  const hasValidationErrors = Object.keys(rowErrors).length > 0;

  const updateVariant = (variantId: string | undefined, updates: Partial<ComposerSkuVariant>) => {
    if (!variantId) return;
    onChange((prev) =>
      prev.map((variant) => (variant.id === variantId ? { ...variant, ...updates } : variant)),
    );
  };

  const updateAttribute = (variantId: string | undefined, key: string, value: string) => {
    if (!variantId) return;
    onChange((prev) =>
      prev.map((variant) => {
        if (variant.id !== variantId) return variant;
        const attributes = { ...(variant.attributes ?? {}) };
        attributes[key] = value.trim().length ? value : null;
        return { ...variant, attributes };
      }),
    );
  };

  const addRow = () => {
    const tempId = `temp-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    onChange((prev) => [
      ...prev,
      {
        id: tempId,
        organizationId: "temp",
        projectId,
        groupId: null,
        sku: "",
        asin: null,
        parentSku: null,
        attributes: {},
        notes: null,
        createdAt: new Date().toISOString(),
      },
    ]);
  };

  const handleDelete = async (variant: ComposerSkuVariant) => {
    if (isTemporaryId(variant.id)) {
      onChange((prev) => prev.filter((entry) => entry.id !== variant.id));
      return;
    }
    await onDelete(variant.id);
  };

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      await importFromRaw(text);
    } finally {
      event.target.value = "";
    }
  };

  const importFromRaw = async (raw: string) => {
    try {
      const result = await parseFromRaw(projectId, { source: "csv", raw });
      const detectedAttributes = result.detectedAttributes ?? [];
      setManualAttributeKeys((prev) =>
        Array.from(new Set([...prev, ...detectedAttributes])),
      );
      onChange((prev) => {
        const map = new Map<string, ComposerSkuVariant>();
        prev.forEach((variant) => {
          map.set(variant.sku.toLowerCase(), variant);
        });
        result.variants.forEach((variant, index) => {
          const key = variant.sku.toLowerCase();
          const existing = map.get(key);
          const merged: ComposerSkuVariant = existing
            ? {
                ...existing,
                sku: variant.sku,
                asin: variant.asin ?? existing.asin ?? null,
                parentSku: variant.parentSku ?? existing.parentSku ?? null,
                attributes: {
                  ...(existing.attributes ?? {}),
                  ...(variant.attributes ?? {}),
                },
                notes: variant.notes ?? existing.notes ?? null,
              }
            : {
                id: `temp-${Date.now()}-${index}`,
                organizationId: existing?.organizationId ?? "temp",
                projectId: existing?.projectId ?? projectId,
                groupId: existing?.groupId ?? null,
                sku: variant.sku,
                asin: variant.asin ?? null,
                parentSku: variant.parentSku ?? null,
                attributes: variant.attributes ?? {},
                notes: variant.notes ?? null,
                createdAt: existing?.createdAt ?? new Date().toISOString(),
              };
          map.set(key, merged);
        });
        return Array.from(map.values());
      });
    } catch (error) {
      console.error("Composer CSV import error", error);
    }
  };

  const addAttributeColumn = () => {
    const name =
      typeof window !== "undefined" ? window.prompt("New attribute column name") : null;
    if (!name) return;
    const trimmed = name.trim();
    if (!trimmed) return;
    setManualAttributeKeys((prev) => (prev.includes(trimmed) ? prev : [...prev, trimmed]));
    onChange((prev) =>
      prev.map((variant) => ({
        ...variant,
        attributes: {
          ...(variant.attributes ?? {}),
          [trimmed]: variant.attributes?.[trimmed] ?? null,
        },
      })),
    );
  };

  return (
    <section className="rounded-2xl border border-[#cbd5f5] bg-white/90 p-6 shadow-inner">
      <header className="mb-4 flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[#94a3b8]">SKUs</p>
            <h2 className="text-2xl font-semibold text-[#0f172a]">Variants</h2>
            <p className="text-xs text-[#475569]">
              Upload a CSV with columns: <strong>sku</strong> (required), <strong>asin</strong>{" "}
              (optional), optional <strong>parent_sku</strong>, and any attribute columns (e.g.,
              color, size).
            </p>
          </div>
          {(() => {
            const { className, text } = statusLabel(isSaving, error);
            return <span className={`text-xs font-semibold ${className}`}>{text}</span>;
          })()}
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-full border border-[#0a6fd6] px-4 py-1.5 text-xs font-semibold text-[#0a6fd6] shadow-sm disabled:opacity-40"
            onClick={() => fileInputRef.current?.click()}
            disabled={isParsing}
          >
            {isParsing ? "Parsing…" : "Upload CSV"}
          </button>
          <button
            type="button"
            className="rounded-full border border-dashed border-[#0a6fd6] px-4 py-1.5 text-xs font-semibold text-[#0a6fd6]"
            onClick={addAttributeColumn}
          >
            + Attribute
          </button>
        </div>
      </header>

      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,text/csv"
        className="hidden"
        onChange={handleFileChange}
      />

      {(error || parseError) && (
        <p className="mb-3 text-sm text-[#b91c1c]">{error ?? parseError}</p>
      )}
      {hasValidationErrors && (
        <p className="mb-3 text-xs text-[#b45309]">Every non-empty row needs both SKU and ASIN.</p>
      )}

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-[#e2e8f0] text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-[#475569]">
              <th className="px-4 py-2">SKU</th>
              <th className="px-4 py-2">ASIN</th>
              <th className="px-4 py-2">Parent SKU</th>
              {attributeKeys.map((key) => (
                <th key={key} className="px-4 py-2">
                  {key}
                </th>
              ))}
              <th className="px-4 py-2">Notes</th>
              <th className="px-4 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#e2e8f0]">
            {isLoading ? (
              <tr>
                <td colSpan={attributeKeys.length + 5} className="px-4 py-6 text-center text-[#94a3b8]">
                  Loading variants…
                </td>
              </tr>
            ) : variants.length === 0 ? (
              <tr>
                <td colSpan={attributeKeys.length + 5} className="px-4 py-6 text-center text-[#94a3b8]">
                  No SKUs captured yet. Use “Add row” or upload a CSV.
                </td>
              </tr>
            ) : (
              variants.map((variant, index) => {
                const rowKey = variant.id ?? variant.sku ?? `temp-${index}`;
                const errorsForRow = rowErrors[rowKey];
                return (
                  <tr key={rowKey}>
                    <td className="px-4 py-2 align-top">
                      <input
                        className={`w-full min-w-[200px] rounded-lg border px-3 py-1 text-sm focus:border-[#0a6fd6] focus:outline-none ${
                          errorsForRow?.sku ? "border-[#f87171]" : "border-[#cbd5f5]"
                        }`}
                        value={variant.sku}
                        onChange={(event) => updateVariant(variant.id, { sku: event.target.value })}
                      />
                      {errorsForRow?.sku && (
                        <p className="mt-1 text-xs text-[#b91c1c]">{errorsForRow.sku}</p>
                      )}
                    </td>
                    <td className="px-4 py-2 align-top">
                      <input
                        className="w-full min-w-[200px] rounded-lg border border-[#cbd5f5] px-3 py-1 text-sm focus:border-[#0a6fd6] focus:outline-none"
                        value={variant.asin ?? ""}
                        onChange={(event) => updateVariant(variant.id, { asin: event.target.value })}
                      />
                    </td>
                    <td className="px-4 py-2 align-top">
                      <input
                        className="w-full rounded-lg border border-[#cbd5f5] px-3 py-1 text-sm focus:border-[#0a6fd6] focus:outline-none"
                        value={variant.parentSku ?? ""}
                        onChange={(event) =>
                          updateVariant(variant.id, { parentSku: event.target.value || null })
                        }
                      />
                    </td>
                    {attributeKeys.map((key) => (
                      <td key={`${rowKey}-${key}`} className="px-4 py-2 align-top">
                        <input
                          className="w-full rounded-lg border border-[#cbd5f5] px-3 py-1 text-sm focus:border-[#0a6fd6] focus:outline-none"
                          value={variant.attributes?.[key] ?? ""}
                          onChange={(event) => updateAttribute(variant.id, key, event.target.value)}
                        />
                      </td>
                    ))}
                    <td className="px-4 py-2 align-top">
                      <textarea
                        className="w-full rounded-lg border border-[#cbd5f5] px-3 py-1 text-sm focus:border-[#0a6fd6] focus:outline-none"
                        rows={1}
                        value={variant.notes ?? ""}
                        onChange={(event) => updateVariant(variant.id, { notes: event.target.value })}
                      />
                    </td>
                    <td className="px-4 py-2 text-right align-top">
                      <button
                        type="button"
                        className="rounded-full px-3 py-1 text-xs font-semibold text-[#b91c1c]"
                        onClick={() => {
                          void handleDelete(variant);
                        }}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

  <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
    <button
      type="button"
      className="rounded-full border border-dashed border-[#0a6fd6] px-4 py-1.5 text-xs font-semibold text-[#0a6fd6]"
      onClick={addRow}
    >
      + Add row
    </button>
  </div>
    </section>
  );
};
