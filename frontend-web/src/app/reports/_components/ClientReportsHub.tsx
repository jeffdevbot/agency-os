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
};

const sortProfiles = (a: ClientProfileSummary["profiles"][number], b: ClientProfileSummary["profiles"][number]) =>
  a.marketplace_code.localeCompare(b.marketplace_code) || a.display_name.localeCompare(b.display_name);

export default function ClientReportsHub({ clientSlug }: Props) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [summary, setSummary] = useState<ClientProfileSummary | null>(null);

  const loadSummary = useCallback(async () => {
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
      const match = findClientSummaryBySlug(result.summaries, clientSlug);
      if (!match) {
        throw new Error("Client report hub not found.");
      }
      setSummary({
        client: match.client,
        profiles: match.profiles.slice().sort(sortProfiles),
      });
    } catch (error) {
      setSummary(null);
      setErrorMessage(error instanceof Error ? error.message : "Unable to load client report hub");
    } finally {
      setLoading(false);
    }
  }, [clientSlug, supabase]);

  useEffect(() => {
    void loadSummary();
  }, [loadSummary]);

  return (
    <main className="space-y-4">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-2xl font-semibold text-[#0f172a]">
          {summary?.client.name ?? "Client Reports"}
        </h1>
        <p className="mt-2 text-sm text-[#4c576f]">
          Select a marketplace-specific WBR profile. Settings and sync operations live inside each marketplace.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            onClick={() => void loadSummary()}
            disabled={loading}
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
          <Link
            href="/reports"
            className="rounded-2xl bg-[#e8eefc] px-4 py-3 text-sm font-semibold text-[#0f172a] transition hover:bg-[#d7e1fb]"
          >
            Back to Reports
          </Link>
          <Link
            href="/reports/wbr/setup"
            className="rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.25)] transition hover:bg-[#0959ab]"
          >
            Add New WBR
          </Link>
        </div>

        {errorMessage ? (
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {errorMessage}
          </p>
        ) : null}

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {loading ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-[#64748b]">
              Loading marketplace profiles...
            </div>
          ) : !summary || summary.profiles.length === 0 ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-[#64748b]">
              No WBR profiles exist for this client yet.
            </div>
          ) : (
            summary.profiles.map((profile) => (
              <div
                key={profile.id}
                className="rounded-2xl border border-slate-200 bg-white p-5 shadow transition hover:-translate-y-0.5 hover:shadow-lg"
              >
                <Link
                  href={`/reports/${clientSlug}/${profile.marketplace_code.toLowerCase()}/wbr`}
                  className="inline-flex items-center rounded-lg text-lg font-semibold text-[#0f172a] transition hover:text-[#0a6fd6]"
                >
                  {`WBR - ${profile.marketplace_code}`}
                </Link>
                <p className="mt-1 text-sm text-[#4c576f]">{profile.display_name}</p>
                <p className="mt-1 text-sm text-[#4c576f]">
                  Week start: {profile.week_start_day} • Status: {profile.status}
                </p>

                <div className="mt-4 flex flex-wrap gap-3">
                  <Link
                    href={`/reports/${clientSlug}/${profile.marketplace_code.toLowerCase()}/wbr`}
                    className="text-sm font-semibold text-[#0a6fd6] hover:underline"
                  >
                    Open WBR
                  </Link>
                  <Link
                    href={`/reports/${clientSlug}/${profile.marketplace_code.toLowerCase()}/wbr/settings`}
                    className="text-sm font-semibold text-[#0a6fd6] hover:underline"
                  >
                    Settings
                  </Link>
                  <Link
                    href={`/reports/${clientSlug}/${profile.marketplace_code.toLowerCase()}/wbr/sync`}
                    className="text-sm font-semibold text-[#0a6fd6] hover:underline"
                  >
                    Sync
                  </Link>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </main>
  );
}
