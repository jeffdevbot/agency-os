"use client";

import { useEffect, useMemo, useState } from "react";
import type { ComposerKeywordPool, ComposerProject } from "@agency/lib/composer/types";
import { useKeywordPools } from "@/lib/composer/hooks/useKeywordPools";
import { useSkuGroups } from "@/lib/composer/hooks/useSkuGroups";
import { KeywordPoolPanel } from "./KeywordPoolPanel";

interface KeywordUploadStepProps {
  project: ComposerProject;
  onValidityChange?: (isValid: boolean) => void;
}

const MIN_KEYWORDS = 5;

const getPoolByType = (pools: ComposerKeywordPool[], type: "body" | "titles") =>
  pools.find((pool) => pool.poolType === type);

export const KeywordUploadStep = ({ project, onValidityChange }: KeywordUploadStepProps) => {
  const isDistinctMode = project.strategyType === "distinct";
  const { groups, isLoading: groupsLoading } = useSkuGroups(project.id);

  const [activeGroupId, setActiveGroupId] = useState<string | null>(null);

  useEffect(() => {
    if (!isDistinctMode) {
      setActiveGroupId(null);
      return;
    }
    if (groups.length && !activeGroupId) {
      setActiveGroupId(groups[0].id);
    }
  }, [isDistinctMode, groups, activeGroupId]);

  const {
    pools,
    isLoading: poolsLoading,
    error: poolsError,
    uploadKeywords,
  } = useKeywordPools(project.id, activeGroupId ?? undefined);

  const bodyPool = useMemo(() => getPoolByType(pools, "body"), [pools]);
  const titlesPool = useMemo(() => getPoolByType(pools, "titles"), [pools]);

  const isReady =
    (bodyPool?.rawKeywords.length ?? 0) >= MIN_KEYWORDS &&
    (titlesPool?.rawKeywords.length ?? 0) >= MIN_KEYWORDS;

  useEffect(() => {
    onValidityChange?.(isReady);
  }, [isReady, onValidityChange]);

  const handleUpload = (poolType: "body" | "titles") => async (keywords: string[]) => {
    const result = await uploadKeywords(poolType, keywords, activeGroupId ?? undefined);
    return { warning: result.warning };
  };

  const scopeLabel = isDistinctMode
    ? groupsLoading
      ? "Loading groups…"
      : `Scope: ${groups.length} group${groups.length === 1 ? "" : "s"}`
    : "Scope: Project (Variations)";

  return (
    <div className="space-y-8">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[#94a3b8]">
          Keyword Upload
        </p>
        <p className="text-sm text-[#475569]">
          Upload or paste raw keywords for Description/Bullets and Titles. We&apos;ll dedupe
          on ingest and flag low counts. Cleaning happens in the next step.
        </p>
        <p className="mt-1 text-xs text-[#64748b]">{scopeLabel}</p>
      </div>

      {isDistinctMode && (
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

      {poolsError && (
        <div className="rounded-xl bg-[#fef2f2] p-3 text-sm text-[#b91c1c]">
          {poolsError}
        </div>
      )}

      <div className="grid gap-6">
        <KeywordPoolPanel
          poolType="body"
          title="Description & Bullets"
          description="Upload raw keywords for descriptions and bullet points."
          pool={bodyPool}
          isLoading={poolsLoading}
          onUpload={handleUpload("body")}
        />
        <KeywordPoolPanel
          poolType="titles"
          title="Titles"
          description="Upload raw keywords geared toward titles."
          pool={titlesPool}
          isLoading={poolsLoading}
          onUpload={handleUpload("titles")}
        />
      </div>
    </div>
  );
};
