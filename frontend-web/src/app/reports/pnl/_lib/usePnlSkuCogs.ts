"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import {
  listPnlSkuCogs,
  savePnlSkuCogs,
  type PnlSkuCogs,
} from "./pnlApi";

export function usePnlSkuCogs(
  profileId: string | null,
  startMonth: string | null,
  endMonth: string | null,
  enabled: boolean,
) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [skus, setSkus] = useState<PnlSkuCogs[]>([]);
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

  const loadSkus = useCallback(async () => {
    if (!profileId || !startMonth || !endMonth || !enabled) {
      setSkus([]);
      setLoading(false);
      setErrorMessage(null);
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    try {
      const token = await getAccessToken();
      setSkus(await listPnlSkuCogs(token, profileId, startMonth, endMonth));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load SKU COGS");
    } finally {
      setLoading(false);
    }
  }, [enabled, endMonth, getAccessToken, profileId, startMonth]);

  const saveSkus = useCallback(
    async (entries: Array<{ sku: string; unit_cost: string | null }>) => {
      if (!profileId) {
        return;
      }
      setSaving(true);
      setErrorMessage(null);
      try {
        const token = await getAccessToken();
        await savePnlSkuCogs(token, profileId, entries);
        await loadSkus();
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Unable to save SKU COGS");
        throw error;
      } finally {
        setSaving(false);
      }
    },
    [getAccessToken, loadSkus, profileId],
  );

  useEffect(() => {
    void loadSkus();
  }, [loadSkus]);

  return {
    skus,
    loading,
    saving,
    errorMessage,
    loadSkus,
    saveSkus,
  };
}
