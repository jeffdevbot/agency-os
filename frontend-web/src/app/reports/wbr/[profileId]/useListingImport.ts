"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import {
  importListingFile,
  importListingFileFromWindsor,
  listListingImportBatches,
  type WbrListingImportBatch,
  type WbrListingImportResult,
} from "../_lib/wbrApi";

type UseListingImportOptions = {
  onImportSuccess?: () => Promise<void> | void;
};

const ALLOWED_EXTENSIONS = [".txt", ".tsv", ".csv", ".xlsx", ".xlsm"];

export function useListingImport(profileId: string, options?: UseListingImportOptions) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [batches, setBatches] = useState<WbrListingImportBatch[]>([]);
  const [loadingBatches, setLoadingBatches] = useState(true);
  const [refreshingBatches, setRefreshingBatches] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [latestImport, setLatestImport] = useState<WbrListingImportResult | null>(null);

  const getAccessToken = useCallback(async (): Promise<string> => {
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session?.access_token) {
      throw new Error("Please sign in again.");
    }

    return session.access_token;
  }, [supabase]);

  const loadBatches = useCallback(
    async (isRefresh: boolean) => {
      if (isRefresh) {
        setRefreshingBatches(true);
      } else {
        setLoadingBatches(true);
      }

      setErrorMessage(null);

      try {
        const token = await getAccessToken();
        const loadedBatches = await listListingImportBatches(token, profileId);
        setBatches(loadedBatches);
      } catch (error) {
        setBatches([]);
        setErrorMessage(error instanceof Error ? error.message : "Unable to load listings imports");
      } finally {
        if (isRefresh) {
          setRefreshingBatches(false);
        } else {
          setLoadingBatches(false);
        }
      }
    },
    [getAccessToken, profileId]
  );

  useEffect(() => {
    void loadBatches(false);
  }, [loadBatches]);

  const handleUpload = useCallback(
    async (file: File) => {
      const lowerName = file.name.toLowerCase();
      if (!ALLOWED_EXTENSIONS.some((ext) => lowerName.endsWith(ext))) {
        setErrorMessage("Listings import supports .txt, .tsv, .csv, .xlsx, and .xlsm files only.");
        setSuccessMessage(null);
        return;
      }

      setUploading(true);
      setErrorMessage(null);
      setSuccessMessage(null);

      try {
        const token = await getAccessToken();
        const result = await importListingFile(token, profileId, file);
        setLatestImport(result);
        setSuccessMessage(`Imported ${result.summary.rows_loaded} child ASINs from "${file.name}".`);
        await loadBatches(true);
        if (options?.onImportSuccess) {
          await options.onImportSuccess();
        }
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Failed to import listings file");
      } finally {
        setUploading(false);
      }
    },
    [getAccessToken, loadBatches, options, profileId]
  );

  const handleWindsorImport = useCallback(
    async (windsorAccountId: string | null | undefined) => {
      if (!windsorAccountId?.trim()) {
        setErrorMessage("This profile is missing a Windsor account id.");
        setSuccessMessage(null);
        return;
      }

      setUploading(true);
      setErrorMessage(null);
      setSuccessMessage(null);

      try {
        const token = await getAccessToken();
        const result = await importListingFileFromWindsor(token, profileId);
        setLatestImport(result);
        setSuccessMessage(
          `Imported ${result.summary.rows_loaded} child ASINs from Windsor account ${windsorAccountId}.`
        );
        await loadBatches(true);
        if (options?.onImportSuccess) {
          await options.onImportSuccess();
        }
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Failed to import Windsor listings");
      } finally {
        setUploading(false);
      }
    },
    [getAccessToken, loadBatches, options, profileId]
  );

  return {
    batches,
    loadingBatches,
    refreshingBatches,
    uploading,
    errorMessage,
    successMessage,
    latestImport,
    loadBatches,
    handleUpload,
    handleWindsorImport,
  };
}
