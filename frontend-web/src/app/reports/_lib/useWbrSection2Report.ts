"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import { getWbrSection2Report, type WbrSection2Report } from "../wbr/_lib/wbrSection1Api";

export function useWbrSection2Report(profileId: string | null, weeks = 4) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [report, setReport] = useState<WbrSection2Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
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
        const nextReport = await getWbrSection2Report(token, profileId, weeks);
        setReport(nextReport);
      } catch (error) {
        setReport(null);
        setErrorMessage(error instanceof Error ? error.message : "Unable to load Section 2 report");
      } finally {
        if (isRefresh) {
          setRefreshing(false);
        } else {
          setLoading(false);
        }
      }
    },
    [getAccessToken, profileId, weeks]
  );

  useEffect(() => {
    void loadReport(false);
  }, [loadReport]);

  return {
    report,
    loading,
    refreshing,
    errorMessage,
    loadReport,
  };
}
