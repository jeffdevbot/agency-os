"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import {
  loadClientProfileSummaries,
  slugifyClientName,
  type ClientProfileSummary,
} from "../_lib/reportClientData";

const sortSummaries = (a: ClientProfileSummary, b: ClientProfileSummary): number =>
  a.client.name.localeCompare(b.client.name);

export default function ReportsClientHub() {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [partialErrorMessage, setPartialErrorMessage] = useState<string | null>(null);
  const [summaries, setSummaries] = useState<ClientProfileSummary[]>([]);

  const loadSummaries = useCallback(async () => {
    setLoading(true);
    setErrorMessage(null);
    setPartialErrorMessage(null);

    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session?.access_token) {
        throw new Error("Please sign in again.");
      }

      const result = await loadClientProfileSummaries(session.access_token);
      setSummaries(result.summaries.sort(sortSummaries));
      if (result.failures.length > 0) {
        setPartialErrorMessage(`Some clients failed to load: ${result.failures.join(" | ")}`);
      }
    } catch (error) {
      setSummaries([]);
      setErrorMessage(error instanceof Error ? error.message : "Unable to load report clients");
    } finally {
      setLoading(false);
    }
  }, [supabase]);

  useEffect(() => {
    void loadSummaries();
  }, [loadSummaries]);

  return (
    <main className="space-y-4">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-2xl font-semibold text-[#0f172a]">Reports</h1>
        <p className="mt-2 text-sm text-[#4c576f]">
          Start with the client. Marketplaces and report settings live one level deeper.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            onClick={() => void loadSummaries()}
            disabled={loading}
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
          <Link
            href="/reports/wbr/setup"
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            Setup New WBR Profile
          </Link>
        </div>

        {errorMessage ? (
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {errorMessage}
          </p>
        ) : null}

        {partialErrorMessage ? (
          <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            {partialErrorMessage}
          </p>
        ) : null}

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {loading ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-[#64748b]">
              Loading clients...
            </div>
          ) : summaries.length === 0 ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-[#64748b]">
              No report-ready clients found yet.
            </div>
          ) : (
            summaries.map((summary) => {
              const marketplaces = Array.from(
                new Set(summary.profiles.map((profile) => profile.marketplace_code))
              ).sort();

              return (
                <Link
                  key={summary.client.id}
                  href={`/reports/${slugifyClientName(summary.client.name)}`}
                  className="rounded-2xl border border-slate-200 bg-white p-5 shadow transition hover:-translate-y-0.5 hover:shadow-lg"
                >
                  <p className="text-lg font-semibold text-[#0f172a]">{summary.client.name}</p>
                  <p className="mt-1 text-sm text-[#4c576f]">
                    {summary.profiles.length === 0
                      ? "No WBR profiles yet."
                      : `${summary.profiles.length} WBR profile${summary.profiles.length === 1 ? "" : "s"} across ${marketplaces.join(", ")}`}
                  </p>
                  <p className="mt-4 text-sm font-semibold text-[#0a6fd6]">Open Client Reports</p>
                </Link>
              );
            })
          )}
        </div>
      </div>
    </main>
  );
}
