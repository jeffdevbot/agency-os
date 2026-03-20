"use client";

import { useCallback, useEffect, useState } from "react";
import { getAccessToken } from "@/lib/getAccessToken";
import {
  listPnlOtherExpenses,
  savePnlOtherExpenses,
  type PnlOtherExpenses,
} from "./pnlApi";

const EMPTY_OTHER_EXPENSES: PnlOtherExpenses = {
  expense_types: [],
  months: [],
};

export function usePnlOtherExpenses(
  profileId: string | null,
  startMonth: string | null,
  endMonth: string | null,
  enabled: boolean,
) {
  const [otherExpenses, setOtherExpenses] = useState<PnlOtherExpenses>(EMPTY_OTHER_EXPENSES);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadOtherExpenses = useCallback(async () => {
    if (!profileId || !startMonth || !endMonth || !enabled) {
      setOtherExpenses(EMPTY_OTHER_EXPENSES);
      setLoading(false);
      setErrorMessage(null);
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    try {
      const token = await getAccessToken();
      setOtherExpenses(await listPnlOtherExpenses(token, profileId, startMonth, endMonth));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load other expenses");
    } finally {
      setLoading(false);
    }
  }, [enabled, endMonth, profileId, startMonth]);

  const saveOtherExpenses = useCallback(
    async (payload: {
      expense_types: Array<{ key: string; enabled: boolean }>;
      months: Array<{ entry_month: string; values: Record<string, string | null> }>;
    }) => {
      if (!profileId || !startMonth || !endMonth) {
        return;
      }
      setSaving(true);
      setErrorMessage(null);
      try {
        const token = await getAccessToken();
        await savePnlOtherExpenses(token, profileId, {
          start_month: startMonth,
          end_month: endMonth,
          expense_types: payload.expense_types,
          months: payload.months,
        });
        await loadOtherExpenses();
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Unable to save other expenses");
        throw error;
      } finally {
        setSaving(false);
      }
    },
    [endMonth, loadOtherExpenses, profileId, startMonth],
  );

  useEffect(() => {
    void loadOtherExpenses();
  }, [loadOtherExpenses]);

  return {
    otherExpenses,
    loading,
    saving,
    errorMessage,
    loadOtherExpenses,
    saveOtherExpenses,
  };
}
