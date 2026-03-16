"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import { getPnlReport, type PnlFilterMode, type PnlReport } from "./pnlApi";

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
        const data = await getPnlReport(token, profileId, filterMode, startMonth, endMonth);
        setReport(data);
      } catch (error) {
        setReport(null);
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
