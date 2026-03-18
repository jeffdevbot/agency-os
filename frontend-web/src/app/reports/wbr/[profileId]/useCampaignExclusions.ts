"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import {
  exportWbrCampaignExclusionsCsv,
  importWbrCampaignExclusionsCsv,
  listWbrCampaignExclusions,
  type ImportWbrCampaignExclusionSummary,
  type WbrCampaignExclusionItem,
} from "../_lib/campaignExclusionApi";

export function useCampaignExclusions(profileId: string) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [items, setItems] = useState<WbrCampaignExclusionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [exportingCsv, setExportingCsv] = useState(false);
  const [importingCsv, setImportingCsv] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [latestImportSummary, setLatestImportSummary] =
    useState<ImportWbrCampaignExclusionSummary | null>(null);

  const getAccessToken = useCallback(async (): Promise<string> => {
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session?.access_token) {
      throw new Error("Please sign in again.");
    }

    return session.access_token;
  }, [supabase]);

  const loadItems = useCallback(
    async (isRefresh: boolean) => {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      setErrorMessage(null);

      try {
        const token = await getAccessToken();
        const nextItems = await listWbrCampaignExclusions(token, profileId);
        setItems(nextItems);
      } catch (error) {
        setItems([]);
        setErrorMessage(
          error instanceof Error ? error.message : "Unable to load campaign exclusions"
        );
      } finally {
        if (isRefresh) {
          setRefreshing(false);
        } else {
          setLoading(false);
        }
      }
    },
    [getAccessToken, profileId]
  );

  useEffect(() => {
    void loadItems(false);
  }, [loadItems]);

  const downloadCsv = useCallback(async () => {
    setExportingCsv(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const token = await getAccessToken();
      const blob = await exportWbrCampaignExclusionsCsv(token, profileId);
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `wbr-campaign-exclusions-${profileId}.csv`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
      setSuccessMessage("Downloaded campaign exclusion CSV.");
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to export campaign exclusion CSV"
      );
    } finally {
      setExportingCsv(false);
    }
  }, [getAccessToken, profileId]);

  const uploadCsv = useCallback(
    async (file: File) => {
      if (!file.name.toLowerCase().endsWith(".csv")) {
        setErrorMessage("Campaign exclusion import supports .csv files only.");
        setSuccessMessage(null);
        return;
      }

      setImportingCsv(true);
      setErrorMessage(null);
      setSuccessMessage(null);

      try {
        const token = await getAccessToken();
        const summary = await importWbrCampaignExclusionsCsv(token, profileId, file);
        setLatestImportSummary(summary);
        setSuccessMessage(
          `Imported campaign exclusions: ${summary.rows_excluded} excluded, ${summary.rows_cleared} cleared, ${summary.rows_unchanged} unchanged.`
        );
        await loadItems(true);
      } catch (error) {
        setErrorMessage(
          error instanceof Error ? error.message : "Failed to import campaign exclusion CSV"
        );
      } finally {
        setImportingCsv(false);
      }
    },
    [getAccessToken, loadItems, profileId]
  );

  return {
    items,
    loading,
    refreshing,
    exportingCsv,
    importingCsv,
    errorMessage,
    successMessage,
    latestImportSummary,
    loadItems,
    downloadCsv,
    uploadCsv,
  };
}
