"use client";

import { useCallback, useMemo, useState, useEffect } from "react";
import {
  closestCenter,
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  defaultKeyboardCoordinateGetter,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type UniqueIdentifier,
} from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import {
  parseTitleBlueprint,
  computeFixedTitleAndRemaining,
  assembleTitle,
  TITLE_SEPARATORS,
  AMAZON_TITLE_MAX_LEN,
  type TitleBlueprint,
  type TitleBlock,
  type TitleSeparator,
  type SkuTitleData,
} from "@/lib/scribe/titleBlueprint";

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

interface VariantAttribute {
  id: string;
  name: string;
}

interface Sku {
  id: string;
  skuCode: string;
  productName: string | null;
}

interface SkuVariantValues {
  [skuId: string]: {
    [attributeId: string]: string;
  };
}

interface TitleBlueprintCardProps {
  projectId: string;
  /** Raw formatPreferences from API (may contain title blueprint) */
  initialFormatPreferences?: Record<string, unknown> | null;
  variantAttributes: VariantAttribute[];
  skus: Sku[];
  skuVariantValues: SkuVariantValues;
}

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------

const DEFAULT_BLUEPRINT: TitleBlueprint = {
  separator: " - ",
  blocks: [{ type: "sku_field", key: "product_name" }],
};

const arrayMove = <T,>(array: T[], from: number, to: number): T[] => {
  const copy = [...array];
  const [item] = copy.splice(from, 1);
  copy.splice(to, 0, item);
  return copy;
};

function getBlockDndId(block: TitleBlock): string {
  switch (block.type) {
    case "sku_field":
      return `sku_field:${block.key}`;
    case "variant_attribute":
      return `variant_attribute:${block.attributeId}`;
    case "llm_phrase":
      return `llm_phrase:${block.key}`;
    default:
      return "unknown";
  }
}

function getBlockLabel(block: TitleBlock, variantAttributes: VariantAttribute[]): string {
  switch (block.type) {
    case "sku_field":
      return "Product Name";
    case "variant_attribute": {
      const attr = variantAttributes.find((a) => a.id === block.attributeId);
      return attr?.name || "Unknown Attribute";
    }
    case "llm_phrase":
      return "Feature Phrase (AI)";
    default:
      return "Unknown";
  }
}

function getAvailableBlocks(
  currentBlocks: TitleBlock[],
  variantAttributes: VariantAttribute[]
): { block: TitleBlock; label: string }[] {
  const available: { block: TitleBlock; label: string }[] = [];

  // Product Name (only if not already added)
  const hasProductName = currentBlocks.some(
    (b) => b.type === "sku_field" && b.key === "product_name"
  );
  if (!hasProductName) {
    available.push({
      block: { type: "sku_field", key: "product_name" },
      label: "Product Name",
    });
  }

  // Variant Attributes (only if not already added)
  for (const attr of variantAttributes) {
    const hasAttr = currentBlocks.some(
      (b) => b.type === "variant_attribute" && b.attributeId === attr.id
    );
    if (!hasAttr) {
      available.push({
        block: { type: "variant_attribute", attributeId: attr.id },
        label: attr.name,
      });
    }
  }

  // LLM Phrase (only if not already added - max 1 allowed)
  const hasLlmPhrase = currentBlocks.some((b) => b.type === "llm_phrase");
  if (!hasLlmPhrase) {
    available.push({
      block: { type: "llm_phrase", key: "feature_phrase" },
      label: "Feature Phrase (AI)",
    });
  }

  return available;
}

function DraggableBlockRow({
  id,
  block,
  variantAttributes,
  saving,
  canRemove,
  onRemove,
}: {
  id: UniqueIdentifier;
  block: TitleBlock;
  variantAttributes: VariantAttribute[];
  saving: boolean;
  canRemove: boolean;
  onRemove: () => void;
}) {
  const {
    attributes,
    listeners,
    setNodeRef: setDraggableNodeRef,
    setActivatorNodeRef,
    transform,
    isDragging,
  } = useDraggable({
    id,
    disabled: saving,
  });

  const { setNodeRef: setDroppableNodeRef, isOver } = useDroppable({
    id,
    disabled: saving,
  });

  const setNodeRef = useCallback(
    (node: HTMLElement | null) => {
      setDraggableNodeRef(node);
      setDroppableNodeRef(node);
    },
    [setDraggableNodeRef, setDroppableNodeRef]
  );

  const style: React.CSSProperties = {
    transform: transform ? CSS.Transform.toString(transform) : undefined,
    opacity: isDragging ? 0.4 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={[
        "flex items-center gap-2 rounded-lg border bg-white px-3 py-2",
        isOver ? "border-[#0a6fd6]" : "border-slate-200",
        saving ? "opacity-70" : "",
      ].join(" ")}
    >
      {/* Drag handle */}
      <button
        ref={setActivatorNodeRef}
        type="button"
        className="cursor-grab select-none rounded px-1 text-slate-400 hover:text-slate-600 active:cursor-grabbing disabled:cursor-not-allowed disabled:opacity-40"
        aria-label={`Reorder block: ${getBlockLabel(block, variantAttributes)}`}
        disabled={saving}
        {...listeners}
        {...attributes}
      >
        ⋮⋮
      </button>

      {/* Block label */}
      <span className="flex-1 text-sm text-slate-700">
        {getBlockLabel(block, variantAttributes)}
        {block.type === "llm_phrase" && (
          <span className="ml-2 rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-700">
            AI
          </span>
        )}
      </span>

      {/* Remove button */}
      <button
        type="button"
        onClick={onRemove}
        disabled={!canRemove || saving}
        className="text-xs text-slate-400 hover:text-red-600 disabled:opacity-30"
        title="Remove"
      >
        ✕
      </button>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Component
// -----------------------------------------------------------------------------

export function TitleBlueprintCard({
  projectId,
  initialFormatPreferences,
  variantAttributes,
  skus,
  skuVariantValues,
}: TitleBlueprintCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [blueprint, setBlueprint] = useState<TitleBlueprint>(DEFAULT_BLUEPRINT);
  const [parseErrors, setParseErrors] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<UniqueIdentifier | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: defaultKeyboardCoordinateGetter })
  );

  // Initialize from props
  useEffect(() => {
    if (initialFormatPreferences?.title) {
      const result = parseTitleBlueprint(initialFormatPreferences.title);
      if (result.blueprint) {
        setBlueprint(result.blueprint);
        setParseErrors([]);
      } else {
        setParseErrors(result.errors);
        setBlueprint(DEFAULT_BLUEPRINT);
      }
    } else {
      setBlueprint(DEFAULT_BLUEPRINT);
      setParseErrors([]);
    }
  }, [initialFormatPreferences]);

  // Compute previews for all SKUs
  const previews = useMemo(() => {
    return skus.map((sku) => {
      const skuData: SkuTitleData = {
        productName: sku.productName,
        variantValuesByAttributeId: skuVariantValues[sku.id] || {},
      };

      const { fixedTitle, remainingForPhrase, needsSeparatorBeforePhrase } =
        computeFixedTitleAndRemaining(skuData, blueprint);

      // For preview, show placeholder for AI phrase
      const hasLlmBlock = blueprint.blocks.some((b) => b.type === "llm_phrase");
      const aiPlaceholder = hasLlmBlock ? "[AI phrase here]" : "";
      const previewTitle = assembleTitle(fixedTitle, blueprint.separator, aiPlaceholder);

      return {
        sku,
        fixedTitle,
        remainingForPhrase,
        needsSeparatorBeforePhrase,
        previewTitle,
        hasLlmBlock,
        isOverBudget: hasLlmBlock && remainingForPhrase <= 0,
        fixedTitleTooLong: fixedTitle.length > AMAZON_TITLE_MAX_LEN,
      };
    });
  }, [skus, skuVariantValues, blueprint]);

  // Count issues
  const issueCount = previews.filter((p) => p.isOverBudget || p.fixedTitleTooLong).length;

  // Save blueprint
  const saveBlueprint = async (newBlueprint: TitleBlueprint) => {
    setSaving(true);
    setSaveError(null);

    try {
      const res = await fetch(`/api/scribe/projects/${projectId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ formatPreferences: { title: newBlueprint } }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error?.message || "Failed to save blueprint");
      }
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save blueprint");
    } finally {
      setSaving(false);
    }
  };

  // Handler: change separator
  const handleSeparatorChange = (newSeparator: TitleSeparator) => {
    const newBlueprint = { ...blueprint, separator: newSeparator };
    setBlueprint(newBlueprint);
    saveBlueprint(newBlueprint);
  };

  // Handler: add block
  const handleAddBlock = (block: TitleBlock) => {
    const newBlueprint = {
      ...blueprint,
      blocks: [...blueprint.blocks, block],
    };
    setBlueprint(newBlueprint);
    saveBlueprint(newBlueprint);
  };

  // Handler: remove block
  const handleRemoveBlock = (index: number) => {
    const newBlocks = blueprint.blocks.filter((_, i) => i !== index);
    if (newBlocks.length === 0) {
      // Don't allow empty blocks
      return;
    }
    const newBlueprint = { ...blueprint, blocks: newBlocks };
    setBlueprint(newBlueprint);
    saveBlueprint(newBlueprint);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveId(null);
    if (!over || active.id === over.id) return;

    const oldIndex = blueprint.blocks.findIndex((b) => getBlockDndId(b) === active.id);
    const newIndex = blueprint.blocks.findIndex((b) => getBlockDndId(b) === over.id);
    if (oldIndex === -1 || newIndex === -1) return;

    const newBlocks = arrayMove(blueprint.blocks, oldIndex, newIndex);
    const newBlueprint = { ...blueprint, blocks: newBlocks };
    setBlueprint(newBlueprint);
    saveBlueprint(newBlueprint);
  };

  const availableBlocks = getAvailableBlocks(blueprint.blocks, variantAttributes);
  const activeBlock = activeId
    ? blueprint.blocks.find((b) => getBlockDndId(b) === activeId) ?? null
    : null;

  return (
    <div className="border-b border-slate-200">
      {/* Header - Collapsible */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex w-full items-center justify-between p-6 text-left transition-colors hover:bg-slate-50"
      >
        <div>
          <h3 className="text-sm font-semibold text-slate-800">
            <span className="mr-2">{isExpanded ? "▼" : "▶"}</span>
            Title Blueprint
          </h3>
          <p className="mt-0.5 text-xs text-slate-600">
            Define a consistent title structure across all SKUs
          </p>
        </div>
        <div className="flex items-center gap-3">
          {issueCount > 0 && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
              {issueCount} {issueCount === 1 ? "issue" : "issues"}
            </span>
          )}
        </div>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="border-t border-slate-100 px-6 pb-6">
          {/* Parse Errors */}
          {parseErrors.length > 0 && (
            <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3">
              <p className="text-sm font-medium text-amber-800">
                Saved blueprint had errors, using defaults:
              </p>
              <ul className="mt-1 list-inside list-disc text-xs text-amber-700">
                {parseErrors.map((err, i) => (
                  <li key={i}>{err}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Save Error */}
          {saveError && (
            <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3">
              <p className="text-sm text-red-800">{saveError}</p>
            </div>
          )}

          {/* Separator Selection */}
          <div className="mt-4">
            <label className="block text-xs font-medium text-slate-700">Separator</label>
            <select
              value={blueprint.separator}
              onChange={(e) => handleSeparatorChange(e.target.value as TitleSeparator)}
              disabled={saving}
              className="mt-1 w-full max-w-xs rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-[#0a6fd6] focus:outline-none focus:ring-1 focus:ring-[#0a6fd6] disabled:opacity-50"
            >
              {TITLE_SEPARATORS.map((sep) => (
                <option key={sep} value={sep}>
                  {sep === " - "
                    ? "Hyphen ( - )"
                    : sep === " — "
                      ? "Em Dash ( — )"
                      : sep === ", "
                        ? "Comma (, )"
                        : "Pipe ( | )"}
                </option>
              ))}
            </select>
          </div>

          {/* Blocks Builder */}
          <div className="mt-4">
            <label className="block text-xs font-medium text-slate-700 mb-2">
              Title Blocks (in order)
            </label>

            {/* Current Blocks */}
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragStart={({ active }) => setActiveId(active.id)}
              onDragCancel={() => setActiveId(null)}
              onDragEnd={handleDragEnd}
            >
              <div className="space-y-2">
                {blueprint.blocks.map((block, index) => {
                  const id = getBlockDndId(block);
                  return (
                    <DraggableBlockRow
                      key={id}
                      id={id}
                      block={block}
                      variantAttributes={variantAttributes}
                      saving={saving}
                      canRemove={blueprint.blocks.length > 1}
                      onRemove={() => handleRemoveBlock(index)}
                    />
                  );
                })}
              </div>

              <DragOverlay>
                {activeBlock ? (
                  <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-lg">
                    <span className="select-none text-slate-400">⋮⋮</span>
                    <span className="text-sm text-slate-700">
                      {getBlockLabel(activeBlock, variantAttributes)}
                      {activeBlock.type === "llm_phrase" && (
                        <span className="ml-2 rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-700">
                          AI
                        </span>
                      )}
                    </span>
                  </div>
                ) : null}
              </DragOverlay>
            </DndContext>

            {/* Add Block Dropdown */}
            {availableBlocks.length > 0 && (
              <div className="mt-3">
                <select
                  value=""
                  onChange={(e) => {
                    const idx = parseInt(e.target.value, 10);
                    if (!isNaN(idx) && availableBlocks[idx]) {
                      handleAddBlock(availableBlocks[idx].block);
                    }
                  }}
                  disabled={saving}
                  className="w-full max-w-xs rounded-lg border border-dashed border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-600 focus:border-[#0a6fd6] focus:outline-none disabled:opacity-50"
                >
                  <option value="">+ Add block...</option>
                  {availableBlocks.map((item, idx) => (
                    <option key={idx} value={idx}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* Preview Table */}
          <div className="mt-6">
            <div className="rounded-lg bg-slate-50 p-3 border border-slate-200">
              <p className="text-xs text-slate-500 mb-2">Preview by SKU:</p>
              <div className="rounded-lg border border-slate-200 overflow-hidden bg-white">
                <div className="max-h-64 overflow-y-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 sticky top-0">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">
                        SKU
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">
                        Title Preview
                      </th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-slate-600 w-24">
                        Fixed / AI Budget
                      </th>
                    </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                    {previews.map((preview) => (
                      <tr
                        key={preview.sku.id}
                        className={
                          preview.isOverBudget || preview.fixedTitleTooLong
                            ? "bg-red-50"
                            : ""
                        }
                      >
                        <td className="px-3 py-2 text-slate-700 font-mono text-xs whitespace-nowrap">
                          {preview.sku.skuCode}
                        </td>
                        <td className="px-3 py-2 text-slate-700 text-xs font-mono">
                          <span className="line-clamp-2">{preview.previewTitle || "(empty)"}</span>
                        </td>
                        <td className="px-3 py-2 text-right whitespace-nowrap">
                          <span className="text-xs text-slate-500">
                            {preview.fixedTitle.length}
                          </span>
                          {preview.hasLlmBlock && (
                            <>
                              <span className="text-xs text-slate-400 mx-1">/</span>
                              <span
                                className={`text-xs ${
                                  preview.remainingForPhrase <= 0
                                    ? "text-red-600 font-medium"
                                    : preview.remainingForPhrase < 30
                                      ? "text-amber-600"
                                      : "text-green-600"
                                }`}
                              >
                                {preview.remainingForPhrase}
                              </span>
                            </>
                          )}
                        </td>
                      </tr>
                    ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              Fixed = characters used by non-AI blocks. AI Budget = remaining characters for the
              Feature Phrase (max {AMAZON_TITLE_MAX_LEN} total).
            </p>
          </div>

          {/* Saving indicator */}
          {saving && (
            <p className="mt-3 text-xs text-slate-500">Saving...</p>
          )}
        </div>
      )}
    </div>
  );
}
