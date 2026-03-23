"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getAccessToken } from "@/lib/getAccessToken";
import { getPnlReport, type PnlFilterMode, type PnlReport } from "./pnlApi";

const TRANSIENT_REPORT_ERRORS = new Set(["Failed to fetch", "Failed to build P&L report"]);

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function isTransientReportError(error: unknown): boolean {
  return error instanceof Error && TRANSIENT_REPORT_ERRORS.has(error.message);
}

export function usePnlReport(
  profileId: string | null,
  filterMode: PnlFilterMode = "ytd",
  startMonth?: string,
  endMonth?: string,
) {
  const [report, setReport] = useState<PnlReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const requestIdRef = useRef(0);

  const loadReport = useCallback(
    async (isRefresh: boolean) => {
      const requestId = requestIdRef.current + 1;
      requestIdRef.current = requestId;

      if (!profileId) {
        setReport(null);
        setErrorMessage(null);
        setLoading(false);
        setRefreshing(false);
        return;
      }

      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setErrorMessage(null);

      try {
        const token = await getAccessToken();
        if (requestId !== requestIdRef.current) {
          return;
        }
        let lastError: unknown = null;

        for (let attempt = 1; attempt <= 2; attempt += 1) {
          try {
            const data = await getPnlReport(token, profileId, filterMode, startMonth, endMonth);
            if (requestId !== requestIdRef.current) {
              return;
            }
            setReport(data);
            lastError = null;
            break;
          } catch (error) {
            if (requestId !== requestIdRef.current) {
              return;
            }
            lastError = error;
            if (attempt === 2 || !isTransientReportError(error)) {
              throw error;
            }
            await delay(500);
          }
        }

        if (requestId === requestIdRef.current && lastError === null) {
          setErrorMessage(null);
        }
      } catch (error) {
        if (requestId === requestIdRef.current) {
          setErrorMessage(error instanceof Error ? error.message : "Unable to load P&L report");
        }
      } finally {
        if (requestId === requestIdRef.current) {
          if (isRefresh) {
            setRefreshing(false);
          } else {
            setLoading(false);
          }
        }
      }
    },
    [profileId, filterMode, startMonth, endMonth],
  );

  useEffect(() => {
    void loadReport(false);
  }, [loadReport]);

  return { report, loading, refreshing, errorMessage, loadReport };
}
