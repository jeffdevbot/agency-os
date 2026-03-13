"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import {
  listWbrChildAsins,
  setWbrChildAsinMapping,
  type WbrChildAsinItem,
} from "../_lib/asinMappingApi";

export function useAsinMappings(profileId: string) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [childAsins, setChildAsins] = useState<WbrChildAsinItem[]>([]);
  const [search, setSearch] = useState("");
  const [unmappedOnly, setUnmappedOnly] = useState(false);
  const [draftRowIds, setDraftRowIds] = useState<Record<string, string>>({});
  const [savingRows, setSavingRows] = useState<Record<string, boolean>>({});

  const getAccessToken = useCallback(async (): Promise<string> => {
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session?.access_token) {
      throw new Error("Please sign in again.");
    }

    return session.access_token;
  }, [supabase]);

  const syncDrafts = useCallback((items: WbrChildAsinItem[]) => {
    setDraftRowIds(
      Object.fromEntries(items.map((item) => [item.child_asin, item.mapped_row_id ?? ""]))
    );
  }, []);

  const loadChildAsins = useCallback(
    async (isRefresh: boolean) => {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      setErrorMessage(null);

      try {
        const token = await getAccessToken();
        const items = await listWbrChildAsins(token, profileId);
        setChildAsins(items);
        syncDrafts(items);
      } catch (error) {
        setChildAsins([]);
        syncDrafts([]);
        setErrorMessage(error instanceof Error ? error.message : "Unable to load child ASIN catalog");
      } finally {
        if (isRefresh) {
          setRefreshing(false);
        } else {
          setLoading(false);
        }
      }
    },
    [getAccessToken, profileId, syncDrafts]
  );

  useEffect(() => {
    void loadChildAsins(false);
  }, [loadChildAsins]);

  const filteredChildAsins = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    return childAsins.filter((item) => {
      if (unmappedOnly && item.mapped_row_id) return false;
      if (!normalizedSearch) return true;
      return (
        item.child_asin.toLowerCase().includes(normalizedSearch) ||
        (item.child_sku ?? "").toLowerCase().includes(normalizedSearch) ||
        (item.child_product_name ?? "").toLowerCase().includes(normalizedSearch) ||
        (item.mapped_row_label ?? "").toLowerCase().includes(normalizedSearch)
      );
    });
  }, [childAsins, search, unmappedOnly]);

  const counts = useMemo(() => {
    const total = childAsins.length;
    const mapped = childAsins.filter((item) => Boolean(item.mapped_row_id)).length;
    return {
      total,
      mapped,
      unmapped: total - mapped,
    };
  }, [childAsins]);

  const updateDraftRowId = (childAsin: string, rowId: string) => {
    setDraftRowIds((prev) => ({ ...prev, [childAsin]: rowId }));
  };

  const saveMapping = async (item: WbrChildAsinItem) => {
    const draftRowId = draftRowIds[item.child_asin] ?? "";
    const nextRowId = draftRowId || null;

    setSavingRows((prev) => ({ ...prev, [item.child_asin]: true }));
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const token = await getAccessToken();
      const result = await setWbrChildAsinMapping(token, profileId, item.child_asin, nextRowId);
      setChildAsins((prev) =>
        prev.map((current) =>
          current.child_asin === item.child_asin
            ? {
                ...current,
                mapped_row_id: result.mapped_row_id,
                mapped_row_label: result.mapped_row_label,
                mapped_row_active: result.mapped_row_active,
              }
            : current
        )
      );
      setDraftRowIds((prev) => ({ ...prev, [item.child_asin]: result.mapped_row_id ?? "" }));
      setSuccessMessage(
        result.mapped_row_id
          ? `Mapped ${item.child_asin} to ${result.mapped_row_label}.`
          : `Cleared mapping for ${item.child_asin}.`
      );
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to save ASIN mapping");
    } finally {
      setSavingRows((prev) => ({ ...prev, [item.child_asin]: false }));
    }
  };

  return {
    loading,
    refreshing,
    errorMessage,
    successMessage,
    childAsins,
    filteredChildAsins,
    counts,
    search,
    unmappedOnly,
    draftRowIds,
    savingRows,
    setSearch,
    setUnmappedOnly,
    updateDraftRowId,
    saveMapping,
    loadChildAsins,
  };
}
