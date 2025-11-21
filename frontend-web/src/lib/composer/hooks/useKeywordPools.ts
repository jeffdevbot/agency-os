import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  ComposerKeywordPool,
  KeywordCleanSettings,
  RemovedKeywordEntry,
} from "@agency/lib/composer/types";
import { dedupeKeywords, mergeKeywords } from "@agency/lib/composer/keywords/utils";

interface GroupingConfig {
  basis: string;
  attributeName?: string;
  groupCount?: number;
  phrasesPerGroup?: number;
}

interface KeywordOverride {
  phrase: string;
  action: 'move' | 'remove' | 'add';
  sourceGroupId?: string | null;
  targetGroupLabel?: string;
  targetGroupIndex?: number;
}

interface UseKeywordPoolsResult {
  pools: ComposerKeywordPool[];
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  uploadKeywords: (
    poolType: "body" | "titles",
    keywords: string[],
    groupId?: string | null,
  ) => Promise<{ pool: ComposerKeywordPool | null; warning?: string }>;
  cleanPool: (poolId: string, config: KeywordCleanSettings) => Promise<ComposerKeywordPool | null>;
  manualRemove: (poolId: string, keyword: string) => Promise<ComposerKeywordPool | null>;
  manualRestore: (poolId: string, keyword: string) => Promise<ComposerKeywordPool | null>;
  deleteKeywords: (poolId: string) => Promise<ComposerKeywordPool | null>;
  approveClean: (poolId: string) => Promise<ComposerKeywordPool | null>;
  unapproveClean: (poolId: string) => Promise<ComposerKeywordPool | null>;
  generateGroupingPlan: (poolId: string, config: GroupingConfig) => Promise<ComposerKeywordPool | null>;
  getGroups: (poolId: string) => Promise<{ groups: any[]; overrides: any[] } | null>;
  addOverride: (poolId: string, override: KeywordOverride) => Promise<boolean>;
  resetOverrides: (poolId: string) => Promise<boolean>;
  approveGrouping: (poolId: string) => Promise<ComposerKeywordPool | null>;
  unapproveGrouping: (poolId: string) => Promise<ComposerKeywordPool | null>;
}

const byPoolType = (poolType: "body" | "titles") => (pool: ComposerKeywordPool) =>
  pool.poolType === poolType;

export const useKeywordPools = (
  projectId: string | undefined,
  groupId?: string | null,
): UseKeywordPoolsResult => {
  const [pools, setPools] = useState<ComposerKeywordPool[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!projectId) return;
    setIsLoading(true);
    setError(null);
    try {
      const query = groupId ? `?groupId=${groupId}` : "";
      const response = await fetch(`/api/composer/projects/${projectId}/keyword-pools${query}`);
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.error || "Unable to load keyword pools");
      }
      setPools(data.pools ?? []);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Unable to load keyword pools");
    } finally {
      setIsLoading(false);
    }
  }, [projectId, groupId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const uploadKeywords = useCallback<
    UseKeywordPoolsResult["uploadKeywords"]
  >(async (poolType, keywords, scopedGroupId) => {
    if (!projectId) {
      return { pool: null };
    }
    const trimmed = dedupeKeywords(keywords);
    if (trimmed.length === 0) return { pool: null };

    setError(null);

    // Optimistic merge for UI responsiveness
    const snapshot = pools;
    let previousPools: ComposerKeywordPool[] | null = null;
    setPools((prev) => {
      previousPools = [...prev];
      const existing = prev.find(
        (p) =>
          p.poolType === poolType &&
          (scopedGroupId ?? null) === (p.groupId ?? null),
      );
      if (!existing) {
        const optimistic: ComposerKeywordPool = {
          id: `temp-${poolType}`,
          organizationId: "",
          projectId: projectId,
          groupId: scopedGroupId ?? null,
          poolType,
          status: "uploaded",
          rawKeywords: trimmed,
          cleanedKeywords: [],
          removedKeywords: [],
          cleanSettings: {},
          groupingConfig: {},
          cleanedAt: null,
          groupedAt: null,
          approvedAt: null,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        };
        return [...prev, optimistic];
      }
      const merged = mergeKeywords(existing.rawKeywords, trimmed);
      return prev.map((p) =>
        p.id === existing.id ? { ...p, rawKeywords: merged, status: "uploaded" } : p,
      );
    });

    try {
      const response = await fetch(`/api/composer/projects/${projectId}/keyword-pools`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          poolType,
          keywords: trimmed,
          groupId: scopedGroupId ?? undefined,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.error || "Unable to upload keywords");
      }
      const updatedPool = data.pool as ComposerKeywordPool;
      setPools((prev) => {
        const filtered = prev.filter((p) => p.id !== updatedPool.id);
        return [...filtered, updatedPool];
      });
      return { pool: updatedPool, warning: data.warning as string | undefined };
    } catch (uploadError) {
      setPools(snapshot ? [...snapshot] : []);
      setError(uploadError instanceof Error ? uploadError.message : "Unable to upload keywords");
      return { pool: null };
    }
  }, [projectId, pools]);

  const cleanPool = useCallback<
    UseKeywordPoolsResult["cleanPool"]
  >(async (poolId, config) => {
    setError(null);
    try {
      const response = await fetch(`/api/composer/keyword-pools/${poolId}/clean`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.error || "Unable to clean keyword pool");
      }
      const updatedPool = data.pool as ComposerKeywordPool;
      setPools((prev) => prev.map((p) => (p.id === poolId ? updatedPool : p)));
      return updatedPool;
    } catch (cleanError) {
      setError(cleanError instanceof Error ? cleanError.message : "Unable to clean keyword pool");
      return null;
    }
  }, []);

  const approveClean = useCallback<
    UseKeywordPoolsResult["approveClean"]
  >(async (poolId) => {
    setError(null);
    try {
      const response = await fetch(`/api/composer/keyword-pools/${poolId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "cleaned" }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.error || "Unable to approve cleaned keywords");
      }
      const updatedPool = data.pool as ComposerKeywordPool;
      setPools((prev) => prev.map((p) => (p.id === poolId ? updatedPool : p)));
      return updatedPool;
    } catch (approveError) {
      setError(approveError instanceof Error ? approveError.message : "Unable to approve keywords");
      return null;
    }
  }, []);

  const unapproveClean = useCallback<
    UseKeywordPoolsResult["unapproveClean"]
  >(async (poolId) => {
    setError(null);
    try {
      const response = await fetch(`/api/composer/keyword-pools/${poolId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "uploaded" }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.error || "Unable to unapprove keywords");
      }
      const updatedPool = data.pool as ComposerKeywordPool;
      setPools((prev) => prev.map((p) => (p.id === poolId ? updatedPool : p)));
      return updatedPool;
    } catch (unapproveError) {
      setError(unapproveError instanceof Error ? unapproveError.message : "Unable to unapprove keywords");
      return null;
    }
  }, []);

  const manualRemove = useCallback<UseKeywordPoolsResult["manualRemove"]>(
    async (poolId, keyword) => {
      const targetPool = pools.find((p) => p.id === poolId);
      if (!targetPool) return null;
      const cleaned = targetPool.cleanedKeywords ?? [];
      const filteredCleaned = cleaned.filter((k) => k.toLowerCase() !== keyword.toLowerCase());
      const removed: RemovedKeywordEntry[] = [
        ...(targetPool.removedKeywords ?? []),
        { term: keyword, reason: "manual" },
      ];
      setPools((prev) =>
        prev.map((p) =>
          p.id === poolId ? { ...p, cleanedKeywords: filteredCleaned, removedKeywords: removed } : p,
        ),
      );
      setError(null);
      try {
        const response = await fetch(`/api/composer/keyword-pools/${poolId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            cleanedKeywords: filteredCleaned,
            removedKeywords: removed,
          }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.error || "Unable to remove keyword");
        }
        const updatedPool = data.pool as ComposerKeywordPool;
        setPools((prev) => prev.map((p) => (p.id === poolId ? updatedPool : p)));
        return updatedPool;
      } catch (removeError) {
        setError(removeError instanceof Error ? removeError.message : "Unable to remove keyword");
        setPools((prev) => prev.map((p) => (p.id === poolId ? targetPool : p)));
        return null;
      }
    },
    [pools],
  );

  const manualRestore = useCallback<UseKeywordPoolsResult["manualRestore"]>(
    async (poolId, keyword) => {
      const targetPool = pools.find((p) => p.id === poolId);
      if (!targetPool) return null;
      const removedList = targetPool.removedKeywords ?? [];
      const remainingRemoved = removedList.filter(
        (entry) => entry.term.toLowerCase() !== keyword.toLowerCase(),
      );
      const cleaned = [...(targetPool.cleanedKeywords ?? []), keyword];
      setPools((prev) =>
        prev.map((p) =>
          p.id === poolId ? { ...p, cleanedKeywords: cleaned, removedKeywords: remainingRemoved } : p,
        ),
      );
      setError(null);
      try {
        const response = await fetch(`/api/composer/keyword-pools/${poolId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            cleanedKeywords: cleaned,
            removedKeywords: remainingRemoved,
          }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.error || "Unable to restore keyword");
        }
        const updatedPool = data.pool as ComposerKeywordPool;
        setPools((prev) => prev.map((p) => (p.id === poolId ? updatedPool : p)));
        return updatedPool;
      } catch (restoreError) {
        setError(restoreError instanceof Error ? restoreError.message : "Unable to restore keyword");
        setPools((prev) => prev.map((p) => (p.id === poolId ? targetPool : p)));
        return null;
      }
    },
    [pools],
  );

  const deleteKeywords = useCallback<UseKeywordPoolsResult["deleteKeywords"]>(
    async (poolId) => {
      const targetPool = pools.find((p) => p.id === poolId);
      if (!targetPool) return null;
      const cleared: ComposerKeywordPool = {
        ...targetPool,
        rawKeywords: [],
        cleanedKeywords: [],
        removedKeywords: [],
        status: "uploaded",
        cleanedAt: null,
        groupedAt: null,
        approvedAt: null,
      };
      setPools((prev) => prev.map((p) => (p.id === poolId ? cleared : p)));
      setError(null);
      try {
        const response = await fetch(`/api/composer/keyword-pools/${poolId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ rawKeywords: [] }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.error || "Unable to delete keywords");
        }
        const updated = data.pool as ComposerKeywordPool;
        setPools((prev) => prev.map((p) => (p.id === poolId ? updated : p)));
        return updated;
      } catch (deleteError) {
        setError(deleteError instanceof Error ? deleteError.message : "Unable to delete keywords");
        setPools((prev) => prev.map((p) => (p.id === poolId ? targetPool : p)));
        return null;
      }
    },
    [pools],
  );

  const generateGroupingPlan = useCallback<UseKeywordPoolsResult["generateGroupingPlan"]>(
    async (poolId, config) => {
      setError(null);
      try {
        const response = await fetch(`/api/composer/keyword-pools/${poolId}/grouping-plan`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ config }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.error || "Unable to generate grouping plan");
        }
        const updatedPool = data.pool as ComposerKeywordPool;
        setPools((prev) => prev.map((p) => (p.id === poolId ? updatedPool : p)));
        return updatedPool;
      } catch (groupingError) {
        setError(groupingError instanceof Error ? groupingError.message : "Unable to generate grouping plan");
        return null;
      }
    },
    [],
  );

  const getGroups = useCallback<UseKeywordPoolsResult["getGroups"]>(
    async (poolId) => {
      setError(null);
      try {
        const response = await fetch(`/api/composer/keyword-pools/${poolId}/groups`);
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.error || "Unable to fetch groups");
        }
        return { groups: data.groups || [], overrides: data.overrides || [] };
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : "Unable to fetch groups");
        return null;
      }
    },
    [],
  );

  const addOverride = useCallback<UseKeywordPoolsResult["addOverride"]>(
    async (poolId, override) => {
      setError(null);
      try {
        const response = await fetch(`/api/composer/keyword-pools/${poolId}/group-overrides`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(override),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.error || "Unable to add override");
        }
        // Log but don't throw - override tracking is non-blocking
        return true;
      } catch (overrideError) {
        console.error("Override tracking failed:", overrideError);
        // Return true anyway - the UI operation should proceed
        return true;
      }
    },
    [],
  );

  const resetOverrides = useCallback<UseKeywordPoolsResult["resetOverrides"]>(
    async (poolId) => {
      setError(null);
      try {
        const response = await fetch(`/api/composer/keyword-pools/${poolId}/group-overrides`, {
          method: "DELETE",
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.error || "Unable to reset overrides");
        }
        return true;
      } catch (resetError) {
        setError(resetError instanceof Error ? resetError.message : "Unable to reset overrides");
        return false;
      }
    },
    [],
  );

  const approveGrouping = useCallback<UseKeywordPoolsResult["approveGrouping"]>(
    async (poolId) => {
      setError(null);
      try {
        const response = await fetch(`/api/composer/keyword-pools/${poolId}/approve-grouping`, {
          method: "POST",
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.error || "Unable to approve grouping");
        }
        const updatedPool = data.pool as ComposerKeywordPool;
        setPools((prev) => prev.map((p) => (p.id === poolId ? updatedPool : p)));
        return updatedPool;
      } catch (approveError) {
        setError(approveError instanceof Error ? approveError.message : "Unable to approve grouping");
        return null;
      }
    },
    [],
  );

  const unapproveGrouping = useCallback<UseKeywordPoolsResult["unapproveGrouping"]>(
    async (poolId) => {
      setError(null);
      try {
        const response = await fetch(`/api/composer/keyword-pools/${poolId}?action=unapprove`, {
          method: "DELETE",
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.error || "Unable to unapprove grouping");
        }
        const updatedPool = data.pool as ComposerKeywordPool;
        setPools((prev) => prev.map((p) => (p.id === poolId ? updatedPool : p)));
        return updatedPool;
      } catch (unapproveError) {
        setError(unapproveError instanceof Error ? unapproveError.message : "Unable to unapprove grouping");
        return null;
      }
    },
    [],
  );

  // Derived helpers for panels (optional)
  useMemo(() => pools.filter(byPoolType("body")), [pools]);

  return {
    pools,
    isLoading,
    error,
    refresh,
    uploadKeywords,
    cleanPool,
    manualRemove,
    manualRestore,
    deleteKeywords,
    approveClean,
    unapproveClean,
    generateGroupingPlan,
    getGroups,
    addOverride,
    resetOverrides,
    approveGrouping,
    unapproveGrouping,
  };
};
