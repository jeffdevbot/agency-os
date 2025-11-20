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

type PoolType = "body" | "titles";

const getPool = (pools: ComposerKeywordPool[], type: PoolType) =>
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
  const [activePoolTab, setActivePoolTab] = useState<PoolType>("body");
  const [confirmReviewed, setConfirmReviewed] = useState<Record<PoolType, boolean>>({
    body: false,
    titles: false,
  });

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
    unapproveClean,
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

  const handleApprove = async (pool?: ComposerKeywordPool, poolType?: PoolType) => {
    if (!pool || !poolType) return;
    const isCurrentlyApproved = pool.status === "cleaned";

    if (isCurrentlyApproved) {
      await unapproveClean(pool.id);
    } else {
      await approveClean(pool.id);
      setConfirmReviewed((prev) => ({ ...prev, [poolType]: false }));
    }

    void refresh();
  };

  const handleContinueToNextPool = () => {
    if (activePoolTab === "body" && titlesPool) {
      setActivePoolTab("titles");
    }
  };

  const renderProgressIndicator = (pool?: ComposerKeywordPool) => {
    if (!pool) return null;

    const hasRun = pool.cleanedKeywords.length > 0 || pool.removedKeywords.length > 0;
    const isApproved = pool.status === "cleaned";

    return (
      <div className="mb-6 flex items-center gap-3">
        {/* Step 1: Run Cleaning */}
        <div className="flex items-center gap-2">
          <div
            className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold ${
              hasRun ? "bg-[#16a34a] text-white" : "bg-[#0a6fd6] text-white"
            }`}
          >
            {hasRun ? "✓" : "1"}
          </div>
          <span className={`text-sm font-medium ${hasRun ? "text-[#16a34a]" : "text-[#0a6fd6]"}`}>
            Run Cleaning
          </span>
        </div>

        <div className={`h-px flex-1 ${hasRun ? "bg-[#16a34a]" : "bg-[#cbd5e1]"}`} />

        {/* Step 2: Review & Edit */}
        <div className="flex items-center gap-2">
          <div
            className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold ${
              !hasRun ? "bg-[#cbd5e1] text-[#64748b]" : isApproved ? "bg-[#16a34a] text-white" : "bg-[#0a6fd6] text-white"
            }`}
          >
            {isApproved ? "✓" : "2"}
          </div>
          <span
            className={`text-sm font-medium ${
              !hasRun ? "text-[#94a3b8]" : isApproved ? "text-[#16a34a]" : "text-[#0a6fd6]"
            }`}
          >
            Review & Edit
          </span>
        </div>

        <div className={`h-px flex-1 ${isApproved ? "bg-[#16a34a]" : "bg-[#cbd5e1]"}`} />

        {/* Step 3: Approve */}
        <div className="flex items-center gap-2">
          <div
            className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold ${
              isApproved ? "bg-[#16a34a] text-white" : "bg-[#cbd5e1] text-[#64748b]"
            }`}
          >
            {isApproved ? "✓" : "3"}
          </div>
          <span className={`text-sm font-medium ${isApproved ? "text-[#16a34a]" : "text-[#94a3b8]"}`}>
            Approve
          </span>
        </div>
      </div>
    );
  };

  const renderPoolSection = (poolType: PoolType, pool?: ComposerKeywordPool) => {
    const label = poolType === "body" ? "Description & Bullets" : "Titles";
    const cleanedCount = pool?.cleanedKeywords.length ?? 0;
    const removedCount = pool?.removedKeywords.length ?? 0;
    const rawCount = pool?.rawKeywords.length ?? 0;
    const canApprove = cleanedCount >= MIN_KEYWORDS && pool?.cleanedKeywords.length;
    const isApproved = pool?.status === "cleaned";
    const shouldShowContinueButton = poolType === "body" && titlesPool && isApproved;

    return (
      <div className="space-y-6">
        {renderProgressIndicator(pool)}

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
          </div>

          <div className="mt-4 space-y-4">
            <CleanedKeywordsList
              keywords={pool?.cleanedKeywords ?? []}
              onRemove={(kw) => void manualRemove(pool?.id ?? "", kw)}
            />
            <RemovedKeywordsList
              removed={pool?.removedKeywords ?? []}
              onRestore={(kw) => void manualRestore(pool?.id ?? "", kw)}
            />
          </div>

          {/* Approval Section */}
          {pool && cleanedCount > 0 && (
            <div className="mt-6 border-t border-[#e2e8f0] pt-4">
              {isApproved ? (
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => void handleApprove(pool, poolType)}
                    className="flex items-center gap-2 rounded-full border-2 border-[#16a34a] bg-[#dcfce7] px-4 py-2 text-sm font-semibold text-[#16a34a] transition-colors hover:bg-[#bbf7d0]"
                  >
                    <span>✓ Approved</span>
                  </button>

                  {shouldShowContinueButton && (
                    <button
                      onClick={handleContinueToNextPool}
                      className="rounded-full bg-[#0a6fd6] px-4 py-2 text-sm font-semibold text-white shadow transition-colors hover:bg-[#0860bf]"
                    >
                      Continue to Titles Pool →
                    </button>
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  <label className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      checked={confirmReviewed[poolType]}
                      onChange={(e) =>
                        setConfirmReviewed((prev) => ({ ...prev, [poolType]: e.target.checked }))
                      }
                      className="mt-1"
                    />
                    <span className="text-sm text-[#475569]">
                      I have reviewed the cleaned and removed keywords
                    </span>
                  </label>
                  <button
                    className="rounded-full bg-[#16a34a] px-4 py-2 text-sm font-semibold text-white shadow disabled:opacity-40"
                    onClick={() => void handleApprove(pool, poolType)}
                    disabled={!canApprove || !confirmReviewed[poolType] || isLoading}
                  >
                    Approve This Pool
                  </button>
                  {!canApprove && (
                    <span className="block text-xs text-[#b45309]">
                      Approve after cleaning to unlock next step.
                    </span>
                  )}
                </div>
              )}
            </div>
          )}
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
        <div className="rounded-xl bg-[#fef2f2] p-3 text-sm text-[#b91c1c]">{error}</div>
      )}

      {/* Tab Navigation */}
      <div className="border-b border-[#e2e8f0]">
        <nav className="flex gap-2">
          <button
            onClick={() => setActivePoolTab("body")}
            className={`flex items-center gap-2 border-b-2 px-4 py-2 text-sm font-semibold transition-colors ${
              activePoolTab === "body"
                ? "border-[#0a6fd6] bg-[#eff6ff] text-[#0a6fd6]"
                : "border-transparent text-[#64748b] hover:border-[#cbd5e1] hover:text-[#0f172a]"
            }`}
          >
            <span>Description & Bullets</span>
            {bodyPool?.status === "cleaned" && (
              <span className="text-[#16a34a]">✓</span>
            )}
          </button>

          <button
            onClick={() => setActivePoolTab("titles")}
            className={`flex items-center gap-2 border-b-2 px-4 py-2 text-sm font-semibold transition-colors ${
              activePoolTab === "titles"
                ? "border-[#0a6fd6] bg-[#eff6ff] text-[#0a6fd6]"
                : "border-transparent text-[#64748b] hover:border-[#cbd5e1] hover:text-[#0f172a]"
            }`}
          >
            <span>Titles</span>
            {titlesPool?.status === "cleaned" && (
              <span className="text-[#16a34a]">✓</span>
            )}
          </button>
        </nav>
      </div>

      {/* Tab Panels */}
      <div>
        {activePoolTab === "body" && renderPoolSection("body", bodyPool)}
        {activePoolTab === "titles" && renderPoolSection("titles", titlesPool)}
      </div>

      {/* Overall Success Message */}
      {ready && (
        <div className="rounded-xl border border-[#16a34a] bg-[#dcfce7] p-4">
          <div className="flex items-center gap-2">
            <span className="text-xl text-[#16a34a]">✓</span>
            <p className="font-semibold text-[#16a34a]">All Keyword Pools Approved</p>
          </div>
          <p className="mt-1 text-sm text-[#15803d]">
            You can now proceed to the next step.
          </p>
        </div>
      )}
    </div>
  );
};
