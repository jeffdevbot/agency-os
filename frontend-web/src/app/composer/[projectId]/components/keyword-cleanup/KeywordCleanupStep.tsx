"use client";

import { useEffect, useMemo, useState } from "react";
import type { ComposerKeywordPool, ComposerProject } from "@agency/lib/composer/types";
import { useKeywordPools } from "@/lib/composer/hooks/useKeywordPools";
import { useSkuGroups } from "@/lib/composer/hooks/useSkuGroups";
import { CleanedKeywordsList } from "./CleanedKeywordsList";
import { RemovedKeywordsList } from "./RemovedKeywordsList";

interface KeywordCleanupStepProps {
  project: ComposerProject;
  onValidityChange?: (isValid: boolean) => void;
}

const MIN_KEYWORDS = 5;

const getPool = (pools: ComposerKeywordPool[], type: "body" | "titles") =>
  pools.find((pool) => pool.poolType === type);

const hasReadyPools = (body?: ComposerKeywordPool, titles?: ComposerKeywordPool) => {
  const bodyReady =
    body && body.cleanedKeywords.length >= MIN_KEYWORDS && body.status === "cleaned";
  const titlesReady =
    titles && titles.cleanedKeywords.length >= MIN_KEYWORDS && titles.status === "cleaned";
  return Boolean(bodyReady && titlesReady);
};

export const KeywordCleanupStep = ({ project, onValidityChange }: KeywordCleanupStepProps) => {
  const isDistinct = project.strategyType === "distinct";
  const { groups, isLoading: groupsLoading } = useSkuGroups(project.id);
  const [activeGroupId, setActiveGroupId] = useState<string | null>(null);

  useEffect(() => {
    if (!isDistinct) {
      setActiveGroupId(null);
      return;
    }
    if (groups.length && !activeGroupId) {
      setActiveGroupId(groups[0].id);
    }
  }, [isDistinct, groups, activeGroupId]);

  const {
    pools,
    isLoading,
    error,
    cleanPool,
    manualRemove,
    manualRestore,
    approveClean,
    refresh,
  } = useKeywordPools(project.id, activeGroupId ?? undefined);

  const bodyPool = useMemo(() => getPool(pools, "body"), [pools]);
  const titlesPool = useMemo(() => getPool(pools, "titles"), [pools]);

  const [config, setConfig] = useState({
    removeColors: false,
    removeSizes: false,
    removeBrandTerms: true,
    removeCompetitorTerms: true,
  });

  const ready = hasReadyPools(bodyPool, titlesPool);
  useEffect(() => {
    onValidityChange?.(ready);
  }, [ready, onValidityChange]);

  const handleClean = async (pool?: ComposerKeywordPool) => {
    if (!pool) return;
    await cleanPool(pool.id, config);
    void refresh();
  };

  const handleApprove = async (pool?: ComposerKeywordPool) => {
    if (!pool) return;
    await approveClean(pool.id);
    void refresh();
  };

  const renderPoolSection = (poolType: "body" | "titles", pool?: ComposerKeywordPool) => {
    const label = poolType === "body" ? "Description & Bullets" : "Titles";
    const cleanedCount = pool?.cleanedKeywords.length ?? 0;
    const removedCount = pool?.removedKeywords.length ?? 0;
    const rawCount = pool?.rawKeywords.length ?? 0;
    const canApprove = cleanedCount >= MIN_KEYWORDS && pool?.cleanedKeywords.length;
    return (
      <div className="rounded-2xl border border-[#e2e8f0] bg-[#f8fafc] p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-lg font-semibold text-[#0f172a]">{label}</h3>
            <p className="text-sm text-[#475569]">Clean, review, and approve this pool.</p>
          </div>
          <div className="text-xs text-[#475569]">
            Raw: {rawCount} • Cleaned: {cleanedCount} • Removed: {removedCount}
          </div>
        </div>

        <div className="mt-3 grid gap-3 md:grid-cols-4">
          <label className="flex items-center gap-2 text-sm text-[#0f172a]">
            <input
              type="checkbox"
              checked={config.removeColors}
              onChange={(e) => setConfig((c) => ({ ...c, removeColors: e.target.checked }))}
            />
            Remove Colors
          </label>
          <label className="flex items-center gap-2 text-sm text-[#0f172a]">
            <input
              type="checkbox"
              checked={config.removeSizes}
              onChange={(e) => setConfig((c) => ({ ...c, removeSizes: e.target.checked }))}
            />
            Remove Sizes
          </label>
          <label className="flex items-center gap-2 text-sm text-[#0f172a]">
            <input
              type="checkbox"
              checked={config.removeBrandTerms}
              onChange={(e) => setConfig((c) => ({ ...c, removeBrandTerms: e.target.checked }))}
            />
            Remove Brand Terms
          </label>
          <label className="flex items-center gap-2 text-sm text-[#0f172a]">
            <input
              type="checkbox"
              checked={config.removeCompetitorTerms}
              onChange={(e) => setConfig((c) => ({ ...c, removeCompetitorTerms: e.target.checked }))}
            />
            Remove Competitors
          </label>
        </div>

        <div className="mt-4 flex flex-wrap gap-3">
          <button
            className="rounded-full bg-[#0a6fd6] px-4 py-2 text-sm font-semibold text-white shadow disabled:opacity-40"
            onClick={() => void handleClean(pool)}
            disabled={isLoading}
          >
            Run Cleaning
          </button>
          <button
            className="rounded-full bg-[#16a34a] px-4 py-2 text-sm font-semibold text-white shadow disabled:opacity-40"
            onClick={() => void handleApprove(pool)}
            disabled={!canApprove || isLoading}
          >
            Approve & Continue
          </button>
          {pool?.status !== "cleaned" && (
            <span className="text-xs text-[#b45309]">Approve after cleaning to unlock next step.</span>
          )}
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div>
            <p className="text-sm font-semibold text-[#0f172a]">Cleaned Keywords</p>
            <p className="text-xs text-[#64748b]">Remove any keywords that don&apos;t belong.</p>
            <div className="mt-2 rounded-xl border border-[#e2e8f0] bg-white p-3">
              <CleanedKeywordsList
                keywords={pool?.cleanedKeywords ?? []}
                onRemove={(kw) => void manualRemove(pool?.id ?? "", kw)}
              />
            </div>
          </div>
          <div>
            <p className="text-sm font-semibold text-[#0f172a]">Removed Keywords</p>
            <p className="text-xs text-[#64748b]">Restore any that should stay.</p>
            <div className="mt-2 rounded-xl border border-[#e2e8f0] bg-white p-3">
              <RemovedKeywordsList
                removed={pool?.removedKeywords ?? []}
                onRestore={(kw) => void manualRestore(pool?.id ?? "", kw)}
              />
            </div>
          </div>
        </div>
      </div>
    );
  };

  const scopeLabel = isDistinct
    ? groupsLoading
      ? "Loading groups…"
      : `Scope: ${groups.length} group${groups.length === 1 ? "" : "s"}`
    : "Scope: Project (Variations)";

  return (
    <div className="space-y-8">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[#94a3b8]">
          Keyword Cleanup
        </p>
        <p className="text-sm text-[#475569]">
          Review cleaned keywords, restore removed terms, and approve to continue. Cleaning uses your
          project brand/competitor info and attribute-driven color/size filters.
        </p>
        <p className="mt-1 text-xs text-[#64748b]">{scopeLabel}</p>
      </div>

      {isDistinct && (
        <div className="space-y-2">
          <p className="text-sm font-semibold text-[#0f172a]">Select Group</p>
          <div className="flex flex-wrap gap-2">
            {groups.map((group) => {
              const isActive = group.id === activeGroupId;
              return (
                <button
                  key={group.id}
                  onClick={() => setActiveGroupId(group.id)}
                  className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                    isActive
                      ? "bg-[#0a6fd6] text-white shadow"
                      : "bg-[#eef2ff] text-[#475569] hover:-translate-y-0.5 hover:bg-white"
                  }`}
                >
                  {group.name}
                </button>
              );
            })}
            {groups.length === 0 && (
              <span className="rounded-full bg-[#fef3c7] px-3 py-1 text-xs font-semibold text-[#b45309]">
                Create SKU groups in Content Strategy first
              </span>
            )}
          </div>
        </div>
      )}

      {error && (
        <div className="rounded-xl bg-[#fef2f2] p-3 text-sm text-[#b91c1c]">
          {error}
        </div>
      )}

      <div className="space-y-6">
        {renderPoolSection("body", bodyPool)}
        {renderPoolSection("titles", titlesPool)}
      </div>
    </div>
  );
};
