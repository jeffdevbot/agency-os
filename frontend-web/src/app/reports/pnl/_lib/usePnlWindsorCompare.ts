"use client";

import { useCallback, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import { getPnlWindsorCompare, type PnlWindsorCompare } from "./pnlApi";

export function usePnlWindsorCompare(profileId: string | null) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [comparison, setComparison] = useState<PnlWindsorCompare | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [loadedMonth, setLoadedMonth] = useState<string | null>(null);

  const getAccessToken = useCallback(async (): Promise<string> => {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) throw new Error("Please sign in again.");
    return session.access_token;
  }, [supabase]);

  const loadComparison = useCallback(async (entryMonth: string) => {
    if (!profileId) {
      setComparison(null);
      setLoadedMonth(null);
      setErrorMessage(null);
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    try {
      const token = await getAccessToken();
      const result = await getPnlWindsorCompare(token, profileId, entryMonth);
      setComparison(result);
      setLoadedMonth(entryMonth);
      return result;
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Unable to compare Windsor settlement data",
      );
      throw error;
    } finally {
      setLoading(false);
    }
  }, [getAccessToken, profileId]);

  const resetComparison = useCallback(() => {
    setComparison(null);
    setLoadedMonth(null);
    setErrorMessage(null);
    setLoading(false);
  }, []);

  return {
    comparison,
    loading,
    errorMessage,
    loadedMonth,
    loadComparison,
    resetComparison,
  };
}
