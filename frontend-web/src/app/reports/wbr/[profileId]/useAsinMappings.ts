"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import {
  exportWbrChildAsinMappingCsv,
  importWbrChildAsinMappingCsv,
  listWbrChildAsins,
  setWbrChildAsinMapping,
  type ImportWbrChildAsinMappingSummary,
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
  const [importingCsv, setImportingCsv] = useState(false);
  const [exportingCsv, setExportingCsv] = useState(false);
  const [latestCsvImportSummary, setLatestCsvImportSummary] =
    useState<ImportWbrChildAsinMappingSummary | null>(null);

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
      if (unmappedOnly && item.scope_status !== "unmapped") return false;
      if (!normalizedSearch) return true;
      return (
        item.child_asin.toLowerCase().includes(normalizedSearch) ||
        (item.child_sku ?? "").toLowerCase().includes(normalizedSearch) ||
        (item.child_product_name ?? "").toLowerCase().includes(normalizedSearch) ||
        (item.mapped_row_label ?? "").toLowerCase().includes(normalizedSearch) ||
        item.scope_status.toLowerCase().includes(normalizedSearch) ||
        (item.exclusion_reason ?? "").toLowerCase().includes(normalizedSearch)
      );
    });
  }, [childAsins, search, unmappedOnly]);

  const counts = useMemo(() => {
    const total = childAsins.length;
    const mapped = childAsins.filter((item) => Boolean(item.mapped_row_id)).length;
    const unmapped = childAsins.filter((item) => item.scope_status === "unmapped").length;
    const excluded = childAsins.filter((item) => item.scope_status === "excluded").length;
    return {
      total,
      mapped,
      unmapped,
      excluded,
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
                is_excluded: false,
                scope_status: result.mapped_row_id ? "included" : "unmapped",
                exclusion_reason: null,
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

  const downloadMappingCsv = useCallback(async () => {
    setExportingCsv(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const token = await getAccessToken();
      const blob = await exportWbrChildAsinMappingCsv(token, profileId);
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `wbr-asin-mapping-${profileId}.csv`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
      setSuccessMessage("Downloaded ASIN mapping CSV.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to export ASIN mapping CSV");
    } finally {
      setExportingCsv(false);
    }
  }, [getAccessToken, profileId]);

  const uploadMappingCsv = useCallback(
    async (file: File) => {
      if (!file.name.toLowerCase().endsWith(".csv")) {
        setErrorMessage("ASIN mapping import supports .csv files only.");
        setSuccessMessage(null);
        return;
      }

      setImportingCsv(true);
      setErrorMessage(null);
      setSuccessMessage(null);

      try {
        const token = await getAccessToken();
        const summary = await importWbrChildAsinMappingCsv(token, profileId, file);
        setLatestCsvImportSummary(summary);
        setSuccessMessage(
          `Imported mapping CSV: ${summary.rows_updated} updated, ${summary.rows_cleared} cleared, ${summary.rows_excluded} excluded, ${summary.rows_unchanged} unchanged.`
        );
        await loadChildAsins(true);
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Failed to import ASIN mapping CSV");
      } finally {
        setImportingCsv(false);
      }
    },
    [getAccessToken, loadChildAsins, profileId]
  );

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
    importingCsv,
    exportingCsv,
    latestCsvImportSummary,
    setSearch,
    setUnmappedOnly,
    updateDraftRowId,
    saveMapping,
    downloadMappingCsv,
    uploadMappingCsv,
    loadChildAsins,
  };
}
