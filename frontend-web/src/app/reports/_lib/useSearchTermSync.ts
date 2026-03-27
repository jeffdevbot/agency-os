"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import type { WbrProfile } from "../wbr/_lib/wbrApi";
import {
  listSearchTermSyncRuns,
  runSearchTermBackfill,
  runSearchTermDailyRefresh,
  type WbrSyncRun,
} from "../wbr/_lib/wbrAmazonAdsApi";

const OBSERVED_STR_RETENTION_DAYS = 60;

const formatDateInput = (value: Date): string => {
  const year = value.getFullYear();
  const month = `${value.getMonth() + 1}`.padStart(2, "0");
  const day = `${value.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const strRetentionStartDate = (today: Date): Date => {
  const start = new Date(today);
  start.setDate(today.getDate() - (OBSERVED_STR_RETENTION_DAYS - 1));
  return start;
};

const previousDay = (today: Date): Date => {
  const prev = new Date(today);
  prev.setDate(today.getDate() - 1);
  return prev;
};

export function useSearchTermSync(profile: WbrProfile | null) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const today = useMemo(() => new Date(), []);
  const todayIso = useMemo(() => formatDateInput(today), [today]);
  const retentionStartIso = useMemo(
    () => formatDateInput(strRetentionStartDate(today)),
    [today],
  );

  const [runs, setRuns] = useState<WbrSyncRun[]>([]);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [refreshingRuns, setRefreshingRuns] = useState(false);
  const [runningBackfill, setRunningBackfill] = useState(false);
  const [runningDailyRefresh, setRunningDailyRefresh] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [backfillDateFrom, setBackfillDateFrom] = useState("");
  const [backfillDateTo, setBackfillDateTo] = useState("");

  useEffect(() => {
    if (!profile) {
      setBackfillDateFrom("");
      setBackfillDateTo("");
      return;
    }
    setBackfillDateFrom(retentionStartIso);
    setBackfillDateTo(formatDateInput(previousDay(today)));
  }, [profile, retentionStartIso, today]);

  const getAccessToken = useCallback(async (): Promise<string> => {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) {
      throw new Error("Please sign in again.");
    }
    return session.access_token;
  }, [supabase]);

  const loadRuns = useCallback(
    async (isRefresh: boolean) => {
      if (!profile?.id) {
        setRuns([]);
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
        const nextRuns = await listSearchTermSyncRuns(token, profile.id);
        setRuns(nextRuns);
      } catch (error) {
        setRuns([]);
        setErrorMessage(
          error instanceof Error ? error.message : "Unable to load STR sync runs",
        );
      } finally {
        if (isRefresh) {
          setRefreshingRuns(false);
        } else {
          setLoadingRuns(false);
        }
      }
    },
    [getAccessToken, profile],
  );

  useEffect(() => {
    void loadRuns(false);
  }, [loadRuns]);

  const hasRunningRuns = runs.some((run) => run.status === "running");

  useEffect(() => {
    if (!profile?.id || !hasRunningRuns) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void loadRuns(true);
    }, 15000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [hasRunningRuns, loadRuns, profile?.id]);

  const handleRunBackfill = useCallback(async () => {
    if (!profile?.id) {
      setErrorMessage("WBR profile not found.");
      return;
    }
    if (!backfillDateFrom || !backfillDateTo) {
      setErrorMessage("Choose both a start date and end date.");
      return;
    }
    if (backfillDateFrom > backfillDateTo) {
      setErrorMessage("Start date must be on or before the end date.");
      return;
    }
    if (backfillDateTo > todayIso) {
      setErrorMessage("End date must be today or earlier.");
      return;
    }
    if (backfillDateFrom < retentionStartIso) {
      setErrorMessage(
        `Start date must be ${retentionStartIso} or later (about ${OBSERVED_STR_RETENTION_DAYS} days inclusive).`,
      );
      return;
    }

    setRunningBackfill(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const token = await getAccessToken();
      const result = await runSearchTermBackfill(token, profile.id, {
        date_from: backfillDateFrom,
        date_to: backfillDateTo,
        chunk_days: 14,
      });
      setSuccessMessage(
        `STR backfill queued across ${result.chunks.length} chunk(s). Worker-sync will poll Amazon and finalize in the background.`,
      );
      await loadRuns(true);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to run STR backfill",
      );
    } finally {
      setRunningBackfill(false);
    }
  }, [
    backfillDateFrom,
    backfillDateTo,
    getAccessToken,
    loadRuns,
    profile,
    retentionStartIso,
    todayIso,
  ]);

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
      const result = await runSearchTermDailyRefresh(token, profile.id);
      setSuccessMessage(
        `STR daily refresh queued for ${result.date_from} to ${result.date_to}. Worker-sync will finalize in the background.`,
      );
      await loadRuns(true);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to run STR daily refresh",
      );
    } finally {
      setRunningDailyRefresh(false);
    }
  }, [getAccessToken, loadRuns, profile]);

  const latestRun = runs[0] ?? null;

  return {
    runs,
    latestRun,
    loadingRuns,
    refreshingRuns,
    hasRunningRuns,
    runningBackfill,
    runningDailyRefresh,
    errorMessage,
    successMessage,
    backfillDateFrom,
    backfillDateTo,
    todayIso,
    retentionStartIso,
    observedRetentionDays: OBSERVED_STR_RETENTION_DAYS,
    setBackfillDateFrom,
    setBackfillDateTo,
    loadRuns,
    handleRunBackfill,
    handleRunDailyRefresh,
  };
}
