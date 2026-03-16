"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import {
  listPnlCogsMonths,
  savePnlCogsMonths,
  type PnlCogsMonth,
} from "./pnlApi";

export function usePnlCogsMonths(profileId: string | null, enabled: boolean) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [months, setMonths] = useState<PnlCogsMonth[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const getAccessToken = useCallback(async (): Promise<string> => {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) throw new Error("Please sign in again.");
    return session.access_token;
  }, [supabase]);

  const loadMonths = useCallback(async () => {
    if (!profileId || !enabled) {
      setMonths([]);
      setLoading(false);
      setErrorMessage(null);
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    try {
      const token = await getAccessToken();
      setMonths(await listPnlCogsMonths(token, profileId));
    } catch (error) {
      setMonths([]);
      setErrorMessage(error instanceof Error ? error.message : "Unable to load COGS months");
    } finally {
      setLoading(false);
    }
  }, [enabled, getAccessToken, profileId]);

  const saveMonths = useCallback(
    async (entries: Array<{ entry_month: string; amount: string | null }>) => {
      if (!profileId) {
        return;
      }
      setSaving(true);
      setErrorMessage(null);
      try {
        const token = await getAccessToken();
        const result = await savePnlCogsMonths(token, profileId, entries);
        setMonths(result);
        return result;
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Unable to save COGS months");
        throw error;
      } finally {
        setSaving(false);
      }
    },
    [getAccessToken, profileId],
  );

  useEffect(() => {
    void loadMonths();
  }, [loadMonths]);

  return {
    months,
    loading,
    saving,
    errorMessage,
    loadMonths,
    saveMonths,
  };
}
