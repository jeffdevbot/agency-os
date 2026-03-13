"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import {
  findClientSummaryBySlug,
  loadClientProfileSummaries,
  type ClientProfileSummary,
} from "./reportClientData";
import type { WbrProfile } from "../wbr/_lib/wbrApi";

const normalizeMarketplaceCode = (value: string) => value.trim().toUpperCase();

export function useResolvedWbrProfile(clientSlug: string, marketplaceCode: string) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [summary, setSummary] = useState<ClientProfileSummary | null>(null);
  const [profile, setProfile] = useState<WbrProfile | null>(null);

  const loadRoute = useCallback(async () => {
    setLoading(true);
    setErrorMessage(null);

    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session?.access_token) {
        throw new Error("Please sign in again.");
      }

      const result = await loadClientProfileSummaries(session.access_token);
      const clientSummary = findClientSummaryBySlug(result.summaries, clientSlug);
      if (!clientSummary) {
        throw new Error("Client report hub not found.");
      }

      const matchedProfile =
        clientSummary.profiles.find(
          (item) =>
            normalizeMarketplaceCode(item.marketplace_code) ===
            normalizeMarketplaceCode(marketplaceCode)
        ) ?? null;

      if (!matchedProfile) {
        throw new Error(
          `No WBR profile found for ${clientSummary.client.name} / ${normalizeMarketplaceCode(marketplaceCode)}.`
        );
      }

      setSummary(clientSummary);
      setProfile(matchedProfile);
    } catch (error) {
      setSummary(null);
      setProfile(null);
      setErrorMessage(error instanceof Error ? error.message : "Unable to resolve WBR route");
    } finally {
      setLoading(false);
    }
  }, [clientSlug, marketplaceCode, supabase]);

  useEffect(() => {
    void loadRoute();
  }, [loadRoute]);

  return {
    loading,
    errorMessage,
    summary,
    profile,
    loadRoute,
  };
}
