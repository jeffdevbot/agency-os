"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import {
  createWbrSnapshot,
  importPacvueWorkbook,
  listPacvueImportBatches,
  type WbrPacvueImportBatch,
  type WbrPacvueImportResult,
} from "../_lib/wbrApi";

const MAX_PACVUE_UPLOAD_MB = 40;
const MAX_PACVUE_UPLOAD_BYTES = MAX_PACVUE_UPLOAD_MB * 1024 * 1024;

type UsePacvueImportOptions = {
  onImportSuccess?: () => Promise<void> | void;
};

export function usePacvueImport(profileId: string, options?: UsePacvueImportOptions) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [batches, setBatches] = useState<WbrPacvueImportBatch[]>([]);
  const [loadingBatches, setLoadingBatches] = useState(true);
  const [refreshingBatches, setRefreshingBatches] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [creatingSnapshot, setCreatingSnapshot] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [latestImport, setLatestImport] = useState<WbrPacvueImportResult | null>(null);

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
        const loadedBatches = await listPacvueImportBatches(token, profileId);
        setBatches(loadedBatches);
      } catch (error) {
        setBatches([]);
        setErrorMessage(error instanceof Error ? error.message : "Unable to load Pacvue imports");
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
      if (!lowerName.endsWith(".xlsx") && !lowerName.endsWith(".xlsm")) {
        setErrorMessage("Pacvue import currently supports .xlsx and .xlsm files only.");
        setSuccessMessage(null);
        return;
      }

      if (file.size > MAX_PACVUE_UPLOAD_BYTES) {
        setErrorMessage(
          `Pacvue workbook exceeds the ${MAX_PACVUE_UPLOAD_MB}MB upload limit. Export a smaller file and try again.`
        );
        setSuccessMessage(null);
        return;
      }

      setUploading(true);
      setErrorMessage(null);
      setSuccessMessage(null);

      try {
        const token = await getAccessToken();
        const result = await importPacvueWorkbook(token, profileId, file);
        setLatestImport(result);
        setSuccessMessage(
          result.summary.invalid_rows_skipped > 0
            ? `Imported ${result.summary.rows_loaded} campaign mappings from "${file.name}". Skipped ${result.summary.invalid_rows_skipped} invalid tag row${result.summary.invalid_rows_skipped === 1 ? "" : "s"}; those campaigns will stay in Unmapped / Legacy until fixed upstream.`
            : `Imported ${result.summary.rows_loaded} campaign mappings from "${file.name}".`
        );
        await loadBatches(true);
        if (options?.onImportSuccess) {
          await options.onImportSuccess();
        }
      } catch (error) {
        if (error instanceof TypeError && error.message === "Failed to fetch") {
          setErrorMessage(
            `Pacvue workbook upload failed before the server responded. If the file is large, keep it under ${MAX_PACVUE_UPLOAD_MB}MB and try again.`
          );
        } else {
          setErrorMessage(
            error instanceof Error ? error.message : "Failed to import Pacvue workbook"
          );
        }
      } finally {
        setUploading(false);
      }
    },
    [getAccessToken, loadBatches, options, profileId]
  );

  const handleCreateFreshSnapshot = useCallback(async () => {
    setCreatingSnapshot(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const token = await getAccessToken();
      const snapshot = await createWbrSnapshot(token, profileId, {
        weeks: 4,
        snapshot_kind: "manual",
        include_raw: false,
      });
      const weekEndingNote = snapshot.week_ending ? ` Week ending ${snapshot.week_ending}.` : "";
      setSuccessMessage(`Created fresh snapshot from current WBR data.${weekEndingNote}`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to create fresh snapshot");
    } finally {
      setCreatingSnapshot(false);
    }
  }, [getAccessToken, profileId]);

  return {
    batches,
    loadingBatches,
    refreshingBatches,
    uploading,
    creatingSnapshot,
    errorMessage,
    successMessage,
    latestImport,
    loadBatches,
    handleUpload,
    handleCreateFreshSnapshot,
  };
}
