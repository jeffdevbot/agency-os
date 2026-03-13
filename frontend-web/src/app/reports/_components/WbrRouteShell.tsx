"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import {
  findClientSummaryBySlug,
  loadClientProfileSummaries,
  type ClientProfileSummary,
} from "../_lib/reportClientData";

type Props = {
  clientSlug: string;
  marketplaceCode: string;
};

const normalizeMarketplaceCode = (value: string) => value.trim().toUpperCase();

export default function WbrRouteShell({ clientSlug, marketplaceCode }: Props) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [summary, setSummary] = useState<ClientProfileSummary | null>(null);
  const [profileId, setProfileId] = useState<string | null>(null);

  const normalizedMarketplace = normalizeMarketplaceCode(marketplaceCode);

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
          (item) => normalizeMarketplaceCode(item.marketplace_code) === normalizedMarketplace
        ) ?? null;
      if (!profile) {
        throw new Error(`No WBR profile found for ${clientSummary.client.name} / ${normalizedMarketplace}.`);
      }

      setSummary(clientSummary);
      setProfileId(profile.id);
    } catch (error) {
      setSummary(null);
      setProfileId(null);
      setErrorMessage(error instanceof Error ? error.message : "Unable to load WBR route");
    } finally {
      setLoading(false);
    }
  }, [clientSlug, normalizedMarketplace, supabase]);

  useEffect(() => {
    void loadRoute();
  }, [loadRoute]);

  return (
    <main className="space-y-4">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-2xl font-semibold text-[#0f172a]">
          {summary?.client.name ?? "WBR"} {normalizedMarketplace}
        </h1>
        <p className="mt-2 text-sm text-[#4c576f]">
          This is now the primary WBR route. The real report renderer will land here next; settings and sync live off this route.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            onClick={() => void loadRoute()}
            disabled={loading}
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
          <Link
            href={`/reports/${clientSlug}`}
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            Back to Marketplaces
          </Link>
          {profileId ? (
            <>
              <Link
                href={`/reports/${clientSlug}/${marketplaceCode}/wbr/settings`}
                className="rounded-2xl bg-[#e8eefc] px-4 py-3 text-sm font-semibold text-[#0f172a] transition hover:bg-[#d7e1fb]"
              >
                Settings
              </Link>
              <Link
                href={`/reports/${clientSlug}/${marketplaceCode}/wbr/sync`}
                className="rounded-2xl bg-[#e8eefc] px-4 py-3 text-sm font-semibold text-[#0f172a] transition hover:bg-[#d7e1fb]"
              >
                Sync
              </Link>
            </>
          ) : null}
        </div>

        {errorMessage ? (
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {errorMessage}
          </p>
        ) : null}

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-sm font-semibold text-[#0f172a]">Report Route</p>
            <p className="mt-2 text-sm text-[#4c576f]">
              Section 1 Windsor data will render here next, using the row tree and ASIN mappings already configured in settings.
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-sm font-semibold text-[#0f172a]">Next Build Slice</p>
            <p className="mt-2 text-sm text-[#4c576f]">
              Windsor Section 1 ingest into the v2 facts table, then a rolling 4-week table with row rollups and QA totals.
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
