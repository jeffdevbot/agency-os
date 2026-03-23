"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getAccessToken } from "@/lib/getAccessToken";
import { getPnlYoYReport, type PnlYoYReport } from "./pnlApi";

const TRANSIENT_REPORT_ERRORS = new Set(["Failed to fetch", "Failed to build P&L YoY report"]);

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function isTransientReportError(error: unknown): boolean {
  return error instanceof Error && TRANSIENT_REPORT_ERRORS.has(error.message);
}

export function usePnlYoYReport(profileId: string | null, year: number) {
  const [report, setReport] = useState<PnlYoYReport | null>(null);
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

        for (let attempt = 1; attempt <= 3; attempt += 1) {
          try {
            const data = await getPnlYoYReport(token, profileId, year);
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
            if (attempt === 3 || !isTransientReportError(error)) {
              throw error;
            }
            await delay(300 * attempt);
          }
        }

        if (requestId === requestIdRef.current && lastError === null) {
          setErrorMessage(null);
        }
      } catch (error) {
        if (requestId === requestIdRef.current) {
          setErrorMessage(error instanceof Error ? error.message : "Unable to load P&L YoY report");
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
    [profileId, year],
  );

  useEffect(() => {
    void loadReport(false);
  }, [loadReport]);

  return { report, loading, refreshing, errorMessage, loadReport };
}
