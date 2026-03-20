"use client";

import { useCallback, useState } from "react";

import { getAccessToken } from "@/lib/getAccessToken";

import { exportPnlWorkbook, type PnlFilterMode } from "./pnlApi";

type ExportOptions = {
  filterMode: PnlFilterMode;
  startMonth?: string;
  endMonth?: string;
  showTotals: boolean;
};

export function usePnlWorkbookExport(profileId: string | null) {
  const [exporting, setExporting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const downloadWorkbook = useCallback(
    async (options: ExportOptions) => {
      if (!profileId || exporting) return;
      setExporting(true);
      setErrorMessage(null);

      try {
        const token = await getAccessToken();
        const { blob, filename } = await exportPnlWorkbook(token, profileId, options);
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = filename;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Failed to export P&L workbook");
      } finally {
        setExporting(false);
      }
    },
    [exporting, profileId],
  );

  return {
    exporting,
    errorMessage,
    downloadWorkbook,
  };
}
