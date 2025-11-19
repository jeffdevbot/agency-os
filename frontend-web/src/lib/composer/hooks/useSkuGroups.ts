import { useCallback, useEffect, useState } from "react";
import type { ComposerSkuGroup } from "@agency/lib/composer/types";

interface UseSkuGroupsResult {
  groups: ComposerSkuGroup[];
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  createGroup: (name: string, description?: string) => Promise<ComposerSkuGroup | null>;
  updateGroup: (groupId: string, updates: { name?: string; description?: string | null }) => Promise<void>;
  deleteGroup: (groupId: string) => Promise<void>;
  assignToGroup: (groupId: string, variantIds: string[]) => Promise<void>;
  unassignVariants: (variantIds: string[]) => Promise<void>;
}

export const useSkuGroups = (projectId: string | undefined): UseSkuGroupsResult => {
  const [groups, setGroups] = useState<ComposerSkuGroup[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!projectId) return;
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/composer/projects/${projectId}/groups`);
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.error || "Unable to load groups");
      }
      setGroups(data.groups ?? []);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Unable to load groups");
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const createGroup = useCallback(
    async (name: string, description?: string): Promise<ComposerSkuGroup | null> => {
      if (!projectId) return null;
      setError(null);
      try {
        const response = await fetch(`/api/composer/projects/${projectId}/groups`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, description }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.error || "Unable to create group");
        }
        const newGroup = data.group as ComposerSkuGroup;
        setGroups((prev) => [...prev, newGroup]);
        return newGroup;
      } catch (createError) {
        setError(createError instanceof Error ? createError.message : "Unable to create group");
        return null;
      }
    },
    [projectId],
  );

  const updateGroup = useCallback(
    async (groupId: string, updates: { name?: string; description?: string | null }) => {
      if (!projectId) return;
      setError(null);
      try {
        const response = await fetch(`/api/composer/projects/${projectId}/groups/${groupId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(updates),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.error || "Unable to update group");
        }
        const updatedGroup = data.group as ComposerSkuGroup;
        setGroups((prev) =>
          prev.map((g) => (g.id === groupId ? updatedGroup : g)),
        );
      } catch (updateError) {
        setError(updateError instanceof Error ? updateError.message : "Unable to update group");
        throw updateError;
      }
    },
    [projectId],
  );

  const deleteGroup = useCallback(
    async (groupId: string) => {
      if (!projectId) return;
      setError(null);
      try {
        const response = await fetch(`/api/composer/projects/${projectId}/groups/${groupId}`, {
          method: "DELETE",
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.error || "Unable to delete group");
        }
        setGroups((prev) => prev.filter((g) => g.id !== groupId));
      } catch (deleteError) {
        setError(deleteError instanceof Error ? deleteError.message : "Unable to delete group");
        throw deleteError;
      }
    },
    [projectId],
  );

  const assignToGroup = useCallback(
    async (groupId: string, variantIds: string[]) => {
      if (!projectId) return;
      setError(null);
      try {
        const response = await fetch(
          `/api/composer/projects/${projectId}/groups/${groupId}/assign`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ variantIds }),
          },
        );
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.error || "Unable to assign SKUs to group");
        }
      } catch (assignError) {
        setError(assignError instanceof Error ? assignError.message : "Unable to assign SKUs");
        throw assignError;
      }
    },
    [projectId],
  );

  const unassignVariants = useCallback(
    async (variantIds: string[]) => {
      if (!projectId) return;
      setError(null);
      try {
        const response = await fetch(`/api/composer/projects/${projectId}/variants/unassign`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ variantIds }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.error || "Unable to unassign SKUs");
        }
      } catch (unassignError) {
        setError(unassignError instanceof Error ? unassignError.message : "Unable to unassign SKUs");
        throw unassignError;
      }
    },
    [projectId],
  );

  return {
    groups,
    isLoading,
    error,
    refresh,
    createGroup,
    updateGroup,
    deleteGroup,
    assignToGroup,
    unassignVariants,
  };
};
