"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import {
  loadActiveClients,
  findClientBySlug,
  type Client,
} from "../../_lib/reportClientData";
import { listPnlProfiles, type PnlProfile } from "./pnlApi";

const normalizeMarketplaceCode = (value: string) => value.trim().toUpperCase();

export type PnlClientSummary = {
  client: Client;
  profile: PnlProfile | null;
};

export function useResolvedPnlProfile(clientSlug: string, marketplaceCode: string) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [resolved, setResolved] = useState<PnlClientSummary | null>(null);

  const loadRoute = useCallback(async () => {
    setLoading(true);
    setErrorMessage(null);

    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session?.access_token) throw new Error("Please sign in again.");

      const clients = await loadActiveClients();
      const client = findClientBySlug(clients, clientSlug);
      if (!client) throw new Error("Client not found.");

      const profiles = await listPnlProfiles(session.access_token, client.id);
      const matched = profiles.find(
        (p) => normalizeMarketplaceCode(p.marketplace_code) === normalizeMarketplaceCode(marketplaceCode),
      );

      setResolved({ client, profile: matched ?? null });
    } catch (error) {
      setResolved(null);
      setErrorMessage(error instanceof Error ? error.message : "Unable to resolve P&L route");
    } finally {
      setLoading(false);
    }
  }, [clientSlug, marketplaceCode, supabase]);

  useEffect(() => {
    void loadRoute();
  }, [loadRoute]);

  return { loading, errorMessage, resolved, loadRoute };
}
