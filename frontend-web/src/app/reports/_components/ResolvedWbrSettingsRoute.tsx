"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import {
  findClientSummaryBySlug,
  loadClientProfileSummaries,
  type ClientProfileSummary,
} from "../_lib/reportClientData";
import WbrProfileWorkspace from "../wbr/[profileId]/WbrProfileWorkspace";

type Props = {
  clientSlug: string;
  marketplaceCode: string;
};

const normalizeMarketplaceCode = (value: string) => value.trim().toUpperCase();

export default function ResolvedWbrSettingsRoute({ clientSlug, marketplaceCode }: Props) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [summary, setSummary] = useState<ClientProfileSummary | null>(null);
  const [profileId, setProfileId] = useState<string | null>(null);

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

      const profile =
        clientSummary.profiles.find(
          (item) =>
            normalizeMarketplaceCode(item.marketplace_code) ===
            normalizeMarketplaceCode(marketplaceCode)
        ) ?? null;

      if (!profile) {
        throw new Error(
          `No WBR profile found for ${clientSummary.client.name} / ${normalizeMarketplaceCode(marketplaceCode)}.`
        );
      }

      setSummary(clientSummary);
      setProfileId(profile.id);
    } catch (error) {
      setSummary(null);
      setProfileId(null);
      setErrorMessage(error instanceof Error ? error.message : "Unable to load WBR settings");
    } finally {
      setLoading(false);
    }
  }, [clientSlug, marketplaceCode, supabase]);

  useEffect(() => {
    void loadRoute();
  }, [loadRoute]);

  if (loading) {
    return (
      <main className="space-y-4">
        <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur text-sm text-[#64748b]">
          Loading WBR settings...
        </div>
      </main>
    );
  }

  if (!profileId || !summary) {
    return (
      <main className="space-y-4">
        <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          <h1 className="text-2xl font-semibold text-[#0f172a]">WBR Settings</h1>
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {errorMessage ?? "Unable to load WBR settings"}
          </p>
        </div>
      </main>
    );
  }

  return (
    <WbrProfileWorkspace
      profileId={profileId}
      clientSlug={clientSlug}
      marketplaceCode={marketplaceCode}
    />
  );
}
