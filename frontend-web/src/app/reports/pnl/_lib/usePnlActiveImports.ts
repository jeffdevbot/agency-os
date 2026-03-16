"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import {
  listPnlImportMonths,
  listPnlImports,
} from "./pnlApi";
import {
  buildActiveImportSummaries,
  type PnlActiveImportSummary,
} from "./pnlActiveImportSummary";

export function usePnlActiveImports(profileId: string | null, monthsInView: string[]) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [allImports, setAllImports] = useState<Awaited<ReturnType<typeof listPnlImports>>>([]);
  const [allImportMonths, setAllImportMonths] = useState<Awaited<ReturnType<typeof listPnlImportMonths>>>([]);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const activeImports = useMemo<PnlActiveImportSummary[]>(
    () => buildActiveImportSummaries(allImports, allImportMonths, monthsInView),
    [allImportMonths, allImports, monthsInView],
  );

  const loadActiveImports = useCallback(async () => {
    if (!profileId) {
      setAllImports([]);
      setAllImportMonths([]);
      setErrorMessage(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    setErrorMessage(null);

    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session?.access_token) {
        throw new Error("Please sign in again.");
      }

      const [importsResult, importMonthsResult] = await Promise.allSettled([
        listPnlImports(session.access_token, profileId),
        listPnlImportMonths(session.access_token, profileId),
      ]);

      const imports = importsResult.status === "fulfilled" ? importsResult.value : [];
      const importMonths = importMonthsResult.status === "fulfilled" ? importMonthsResult.value : [];

      setAllImports(imports);
      setAllImportMonths(importMonths);

      if (importMonthsResult.status === "rejected") {
        throw importMonthsResult.reason;
      }

      if (importsResult.status === "rejected") {
        setErrorMessage(null);
      }
    } catch (error) {
      setAllImports([]);
      setAllImportMonths([]);
      setErrorMessage(
        error instanceof Error ? error.message : "Unable to load Monthly P&L import provenance",
      );
    } finally {
      setLoading(false);
    }
  }, [profileId, supabase]);

  useEffect(() => {
    void loadActiveImports();
  }, [loadActiveImports]);

  return { activeImports, loading, errorMessage, loadActiveImports };
}
