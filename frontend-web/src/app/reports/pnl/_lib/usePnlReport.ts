"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
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
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [report, setReport] = useState<PnlReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const getAccessToken = useCallback(async (): Promise<string> => {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) throw new Error("Please sign in again.");
    return session.access_token;
  }, [supabase]);

  const loadReport = useCallback(
    async (isRefresh: boolean) => {
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
        let lastError: unknown = null;

        for (let attempt = 1; attempt <= 2; attempt += 1) {
          try {
            const data = await getPnlReport(token, profileId, filterMode, startMonth, endMonth);
            setReport(data);
            lastError = null;
            break;
          } catch (error) {
            lastError = error;
            if (attempt === 2 || !isTransientReportError(error)) {
              throw error;
            }
            await delay(500);
          }
        }

        if (lastError === null) {
          setErrorMessage(null);
        }
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Unable to load P&L report");
      } finally {
        if (isRefresh) {
          setRefreshing(false);
        } else {
          setLoading(false);
        }
      }
    },
    [getAccessToken, profileId, filterMode, startMonth, endMonth],
  );

  useEffect(() => {
    void loadReport(false);
  }, [loadReport]);

  return { report, loading, refreshing, errorMessage, loadReport };
}
