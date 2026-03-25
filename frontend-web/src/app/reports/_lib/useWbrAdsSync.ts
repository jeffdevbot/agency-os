"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import type { WbrProfile } from "../wbr/_lib/wbrApi";
import {
  getAmazonAdsSyncCoverage,
  listAmazonAdsSyncRuns,
  runAmazonAdsBackfill,
  runAmazonAdsDailyRefresh,
  type WbrSyncCoverage,
  type WbrSyncRun,
} from "../wbr/_lib/wbrAmazonAdsApi";

const previousFullWeekEnd = (weekStartDay: "sunday" | "monday"): Date => {
  const today = new Date();
  const dayOfWeek = today.getDay();
  const currentWeekStartOffset =
    weekStartDay === "monday" ? (dayOfWeek === 0 ? 6 : dayOfWeek - 1) : dayOfWeek;
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

const OBSERVED_AMAZON_ADS_RETENTION_DAYS = 60;

const amazonAdsRetentionStartDate = (today: Date): Date => {
  const retentionStart = new Date(today);
  retentionStart.setDate(today.getDate() - (OBSERVED_AMAZON_ADS_RETENTION_DAYS - 1));
  return retentionStart;
};

export function useWbrAdsSync(profile: WbrProfile | null) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const today = useMemo(() => new Date(), []);
  const todayIso = useMemo(() => formatDateInput(today), [today]);
  const retentionStartIso = useMemo(
    () => formatDateInput(amazonAdsRetentionStartDate(today)),
    [today],
  );
  const [runs, setRuns] = useState<WbrSyncRun[]>([]);
  const [coverage, setCoverage] = useState<WbrSyncCoverage | null>(null);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [refreshingRuns, setRefreshingRuns] = useState(false);
  const [runningBackfill, setRunningBackfill] = useState(false);
  const [runningDailyRefresh, setRunningDailyRefresh] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [backfillStartDate, setBackfillStartDate] = useState("");
  const [backfillEndDate, setBackfillEndDate] = useState("");
  const [chunkDays, setChunkDays] = useState("14");

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
    const configuredStart = profile.backfill_start_date
      ? profile.backfill_start_date
      : formatDateInput(new Date(defaultEnd.getFullYear(), defaultEnd.getMonth(), defaultEnd.getDate() - 27));
    const defaultStart = configuredStart < retentionStartIso ? retentionStartIso : configuredStart;

    setBackfillStartDate(defaultStart);
    setBackfillEndDate(formatDateInput(defaultEnd));
  }, [profile, retentionStartIso]);

  const loadRuns = useCallback(
    async (isRefresh: boolean) => {
      if (!profile?.id || !profile.amazon_ads_profile_id) {
        setRuns([]);
        setCoverage(null);
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
        const [nextRuns, nextCoverage] = await Promise.all([
          listAmazonAdsSyncRuns(token, profile.id),
          getAmazonAdsSyncCoverage(token, profile.id),
        ]);
        setRuns(nextRuns);
        setCoverage(nextCoverage);
      } catch (error) {
        setRuns([]);
        setCoverage(null);
        setErrorMessage(error instanceof Error ? error.message : "Unable to load Amazon Ads sync runs");
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
    if (backfillStartDate < retentionStartIso) {
      setErrorMessage(
        `Amazon Ads backfill currently needs a start date of ${retentionStartIso} or later (about ${OBSERVED_AMAZON_ADS_RETENTION_DAYS} calendar days inclusive).`,
      );
      return;
    }

    setRunningBackfill(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const token = await getAccessToken();
      const result = await runAmazonAdsBackfill(token, profile.id, {
        date_from: backfillStartDate,
        date_to: backfillEndDate,
        chunk_days: Number(chunkDays) || 14,
      });
      setSuccessMessage(
        `Backfill queued across ${result.chunks.length} chunk(s). Worker-sync will poll Amazon and finalize the runs in the background.`,
      );
      await loadRuns(true);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to run Amazon Ads backfill");
    } finally {
      setRunningBackfill(false);
    }
  }, [backfillEndDate, backfillStartDate, chunkDays, getAccessToken, loadRuns, profile, retentionStartIso, todayIso]);

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
      const result = await runAmazonAdsDailyRefresh(token, profile.id);
      setSuccessMessage(
        `Manual refresh queued for ${result.date_from} to ${result.date_to}. Worker-sync will poll Amazon and finalize it in the background.`,
      );
      await loadRuns(true);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to run Amazon Ads manual refresh");
    } finally {
      setRunningDailyRefresh(false);
    }
  }, [getAccessToken, loadRuns, profile]);

  return {
    runs,
    coverage,
    loadingRuns,
    refreshingRuns,
    runningBackfill,
    runningDailyRefresh,
    errorMessage,
    successMessage,
    backfillStartDate,
    backfillEndDate,
    todayIso,
    retentionStartIso,
    observedRetentionDays: OBSERVED_AMAZON_ADS_RETENTION_DAYS,
    chunkDays,
    hasRunningRuns,
    setBackfillStartDate,
    setBackfillEndDate,
    setChunkDays,
    loadRuns,
    handleRunBackfill,
    handleRunDailyRefresh,
  };
}
