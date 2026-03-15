"use client";

import { useCallback, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import { exportWbrWorkbook } from "../wbr/_lib/wbrSection1Api";

type ExportOptions = {
  weeks?: number;
  hideEmptyRows?: boolean;
  newestFirst?: boolean;
};

export function useWbrWorkbookExport(profileId: string | null) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [exporting, setExporting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const getAccessToken = useCallback(async (): Promise<string> => {
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session?.access_token) {
      throw new Error("Please sign in again.");
    }

    return session.access_token;
  }, [supabase]);

  const downloadWorkbook = useCallback(
    async (options?: ExportOptions) => {
      if (!profileId || exporting) return;
      setExporting(true);
      setErrorMessage(null);

      try {
        const token = await getAccessToken();
        const { blob, filename } = await exportWbrWorkbook(token, profileId, options);
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = filename;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Failed to export WBR workbook");
      } finally {
        setExporting(false);
      }
    },
    [exporting, getAccessToken, profileId]
  );

  return {
    exporting,
    errorMessage,
    downloadWorkbook,
  };
}
