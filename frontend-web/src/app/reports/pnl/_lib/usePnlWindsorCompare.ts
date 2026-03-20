"use client";

import { useCallback, useState } from "react";
import { getAccessToken } from "@/lib/getAccessToken";
import { getPnlWindsorCompare, type PnlWindsorCompare } from "./pnlApi";

export function usePnlWindsorCompare(profileId: string | null) {
  const [comparison, setComparison] = useState<PnlWindsorCompare | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [loadedMonth, setLoadedMonth] = useState<string | null>(null);
  const [loadedMarketplaceScope, setLoadedMarketplaceScope] = useState<
    "all" | "amazon_com_only" | "amazon_com_and_ca" | null
  >(null);

  const loadComparison = useCallback(async (
    entryMonth: string,
    marketplaceScope: "all" | "amazon_com_only" | "amazon_com_and_ca",
  ) => {
    if (!profileId) {
      setComparison(null);
      setLoadedMonth(null);
      setLoadedMarketplaceScope(null);
      setErrorMessage(null);
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    try {
      const token = await getAccessToken();
      const result = await getPnlWindsorCompare(token, profileId, entryMonth, marketplaceScope);
      setComparison(result);
      setLoadedMonth(entryMonth);
      setLoadedMarketplaceScope(marketplaceScope);
      return result;
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Unable to compare Windsor settlement data",
      );
      throw error;
    } finally {
      setLoading(false);
    }
  }, [profileId]);

  const resetComparison = useCallback(() => {
    setComparison(null);
    setLoadedMonth(null);
    setLoadedMarketplaceScope(null);
    setErrorMessage(null);
    setLoading(false);
  }, []);

  return {
    comparison,
    loading,
    errorMessage,
    loadedMonth,
    loadedMarketplaceScope,
    loadComparison,
    resetComparison,
  };
}
