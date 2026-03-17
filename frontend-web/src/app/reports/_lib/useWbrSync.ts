"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import type { WbrProfile } from "../wbr/_lib/wbrApi";
import {
  listWbrSyncRuns,
  runWbrWindsorBusinessBackfill,
  runWbrWindsorBusinessDailyRefresh,
  type WbrSyncRun,
} from "../wbr/_lib/wbrSection1Api";

const previousFullWeekEnd = (weekStartDay: "sunday" | "monday"): Date => {
  const today = new Date();
  const dayOfWeek = today.getDay();
  const currentWeekStartOffset = weekStartDay === "monday" ? (dayOfWeek === 0 ? 6 : dayOfWeek - 1) : dayOfWeek;
  const currentWeekStart = new Date(today);
  currentWeekStart.setDate(today.getDate() - currentWeekStartOffset);
  const previousEnd = new Date(currentWeekStart);
  previousEnd.setDate(currentWeekStart.getDate() - 1);
  return previousEnd;
};

const formatDateInput = (value: Date): string => {
  const year = value.getFullYear();
  const month = `${value.getMonth() + 1}`.padStart(2, "0");
  const day = `${value.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
};

export function useWbrSync(profile: WbrProfile | null) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const todayIso = useMemo(() => formatDateInput(new Date()), []);
  const [runs, setRuns] = useState<WbrSyncRun[]>([]);
  const [section3Runs, setSection3Runs] = useState<WbrSyncRun[]>([]);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [refreshingRuns, setRefreshingRuns] = useState(false);
  const [runningBackfill, setRunningBackfill] = useState(false);
  const [runningDailyRefresh, setRunningDailyRefresh] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [backfillStartDate, setBackfillStartDate] = useState("");
  const [backfillEndDate, setBackfillEndDate] = useState("");
  const [chunkDays, setChunkDays] = useState("7");

  const getAccessToken = useCallback(async (): Promise<string> => {
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session?.access_token) {
      throw new Error("Please sign in again.");
    }

    return session.access_token;
  }, [supabase]);

  useEffect(() => {
    if (!profile) {
      setBackfillStartDate("");
      setBackfillEndDate("");
      return;
    }

    const defaultEnd = previousFullWeekEnd(profile.week_start_day);
    const defaultStart = profile.backfill_start_date
      ? profile.backfill_start_date
      : formatDateInput(new Date(defaultEnd.getFullYear(), defaultEnd.getMonth(), defaultEnd.getDate() - 27));

    setBackfillStartDate(defaultStart);
    setBackfillEndDate(formatDateInput(defaultEnd));
  }, [profile]);

  const loadRuns = useCallback(
    async (isRefresh: boolean) => {
      if (!profile?.id) {
        setRuns([]);
        setSection3Runs([]);
        setLoadingRuns(false);
        setRefreshingRuns(false);
        return;
      }

      if (isRefresh) {
        setRefreshingRuns(true);
      } else {
        setLoadingRuns(true);
      }
      setErrorMessage(null);

      try {
        const token = await getAccessToken();
        const [nextRuns, invRuns, retRuns] = await Promise.all([
          listWbrSyncRuns(token, profile.id, "windsor_business"),
          listWbrSyncRuns(token, profile.id, "windsor_inventory"),
          listWbrSyncRuns(token, profile.id, "windsor_returns"),
        ]);
        setRuns(nextRuns);
        setSection3Runs(
          [...invRuns, ...retRuns].sort(
            (a, b) => new Date(b.created_at ?? "").getTime() - new Date(a.created_at ?? "").getTime()
          )
        );
      } catch (error) {
        setRuns([]);
        setSection3Runs([]);
        setErrorMessage(error instanceof Error ? error.message : "Unable to load WBR sync runs");
      } finally {
        if (isRefresh) {
          setRefreshingRuns(false);
        } else {
          setLoadingRuns(false);
        }
      }
    },
    [getAccessToken, profile]
  );

  useEffect(() => {
    void loadRuns(false);
  }, [loadRuns]);

  const handleRunBackfill = useCallback(async () => {
    if (!profile?.id) {
      setErrorMessage("WBR profile not found.");
      return;
    }
    if (!backfillStartDate || !backfillEndDate) {
      setErrorMessage("Choose both a backfill start date and end date.");
      return;
    }
    if (backfillStartDate > backfillEndDate) {
      setErrorMessage("Backfill start date must be on or before the end date.");
      return;
    }
    if (backfillEndDate > todayIso) {
      setErrorMessage("Backfill end date must be today or earlier.");
      return;
    }

    setRunningBackfill(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const token = await getAccessToken();
      const result = await runWbrWindsorBusinessBackfill(token, profile.id, {
        date_from: backfillStartDate,
        date_to: backfillEndDate,
        chunk_days: Number(chunkDays) || 7,
      });
      const totalRowsLoaded = result.chunks.reduce((sum, chunk) => sum + chunk.rows_loaded, 0);
      setSuccessMessage(
        `Backfill completed across ${result.chunks.length} chunk(s). Loaded ${totalRowsLoaded} daily ASIN facts.`
      );
      await loadRuns(true);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to run Windsor business backfill");
    } finally {
      setRunningBackfill(false);
    }
  }, [backfillEndDate, backfillStartDate, chunkDays, getAccessToken, loadRuns, profile, todayIso]);

  const handleRunDailyRefresh = useCallback(async () => {
    if (!profile?.id) {
      setErrorMessage("WBR profile not found.");
      return;
    }

    setRunningDailyRefresh(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const token = await getAccessToken();
      const result = await runWbrWindsorBusinessDailyRefresh(token, profile.id);
      const parts = [
        `Manual refresh loaded ${result.chunk.rows_loaded} daily ASIN facts for ${result.date_from} to ${result.date_to}.`,
      ];
      if (result.section3) {
        const inv = result.section3.inventory;
        const ret = result.section3.returns;
        if (inv?.status === "error") {
          parts.push(`Inventory sync failed: ${inv.detail ?? "unknown error"}`);
        } else if (inv?.rows_loaded != null) {
          const afnNote =
            inv.afn_only_asin_count && inv.afn_only_asin_count > 0
              ? ` ${inv.afn_only_asin_count} AFN-only ASINs excluded from v1 snapshot.`
              : "";
          parts.push(`Inventory: ${inv.rows_loaded} ASINs loaded.${afnNote}`);
        }
        if (ret?.status === "error") {
          parts.push(`Returns sync failed: ${ret.detail ?? "unknown error"}`);
        } else if (ret?.rows_loaded != null) {
          parts.push(`Returns: ${ret.rows_loaded} facts loaded.`);
        }
      }
      setSuccessMessage(parts.join(" "));
      await loadRuns(true);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to run Windsor business manual refresh");
    } finally {
      setRunningDailyRefresh(false);
    }
  }, [getAccessToken, loadRuns, profile]);

  return {
    runs,
    section3Runs,
    loadingRuns,
    refreshingRuns,
    runningBackfill,
    runningDailyRefresh,
    errorMessage,
    successMessage,
    backfillStartDate,
    backfillEndDate,
    todayIso,
    chunkDays,
    setBackfillStartDate,
    setBackfillEndDate,
    setChunkDays,
    loadRuns,
    handleRunBackfill,
    handleRunDailyRefresh,
  };
}
