"use client";

import { useCallback, useEffect, useState } from "react";
import { getAccessToken } from "@/lib/getAccessToken";
import {
  listPnlSkuCogs,
  savePnlSkuCogs,
  type PnlSkuCogs,
} from "./pnlApi";

export function usePnlSkuCogs(
  profileId: string | null,
  enabled: boolean,
) {
  const [skus, setSkus] = useState<PnlSkuCogs[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadSkus = useCallback(async () => {
    if (!profileId || !enabled) {
      setSkus([]);
      setLoading(false);
      setErrorMessage(null);
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    try {
      const token = await getAccessToken();
      setSkus(await listPnlSkuCogs(token, profileId));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load SKU COGS");
    } finally {
      setLoading(false);
    }
  }, [enabled, profileId]);

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
    [loadSkus, profileId],
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
