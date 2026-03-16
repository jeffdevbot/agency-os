"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import {
  loadClientReportSurfaceSummaryBySlug,
  type ClientReportSurfaceSummary,
} from "../_lib/reportClientData";

type Props = {
  clientSlug: string;
};

export default function ClientReportsHub({ clientSlug }: Props) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [summary, setSummary] = useState<ClientReportSurfaceSummary | null>(null);

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

      const match = await loadClientReportSurfaceSummaryBySlug(session.access_token, clientSlug);
      setSummary(match);
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
          Select the marketplace, then choose the reporting surface. WBR and Monthly P&amp;L are
          separate products that now live side by side under `/reports`.
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
          ) : !summary || summary.marketplaces.length === 0 ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-[#64748b]">
              No report surfaces exist for this client yet. Create a WBR profile to seed a new
              marketplace, or open Monthly P&amp;L once a marketplace route exists.
            </div>
          ) : (
            summary.marketplaces.map((marketplace) => {
              const marketplaceSlug = marketplace.marketplace_code.toLowerCase();
              const wbrProfile = marketplace.wbr_profile;
              const pnlProfile = marketplace.pnl_profile;

              return (
                <div
                  key={marketplace.marketplace_code}
                  className="rounded-2xl border border-slate-200 bg-white p-5 shadow transition hover:-translate-y-0.5 hover:shadow-lg"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-lg font-semibold text-[#0f172a]">
                        {marketplace.marketplace_code} Marketplace
                      </p>
                      <p className="mt-1 text-sm text-[#4c576f]">
                        {wbrProfile?.display_name ??
                          "Use this marketplace route to access either WBR or Monthly P&L."}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <span
                        className={`rounded-full px-3 py-1 text-xs font-semibold ${
                          wbrProfile
                            ? "bg-[#e8eefc] text-[#0a6fd6]"
                            : "bg-[#f1f5f9] text-[#64748b]"
                        }`}
                      >
                        {wbrProfile ? "WBR configured" : "WBR not configured"}
                      </span>
                      <span
                        className={`rounded-full px-3 py-1 text-xs font-semibold ${
                          pnlProfile
                            ? "bg-[#fff4dd] text-[#9a5b16]"
                            : "bg-[#f8fafc] text-[#64748b]"
                        }`}
                      >
                        {pnlProfile ? "Monthly P&L profile ready" : "Monthly P&L profile not created"}
                      </span>
                    </div>
                  </div>

                  {wbrProfile ? (
                    <p className="mt-3 text-sm text-[#4c576f]">
                      WBR: {wbrProfile.display_name} • Week start: {wbrProfile.week_start_day} •
                      Status: {wbrProfile.status}
                    </p>
                  ) : (
                    <p className="mt-3 text-sm text-[#4c576f]">
                      WBR setup is still optional for Monthly P&amp;L on this marketplace route.
                    </p>
                  )}

                  {pnlProfile ? (
                    <p className="mt-1 text-sm text-[#4c576f]">
                      Monthly P&amp;L: {pnlProfile.currency_code} • Status: {pnlProfile.status}
                    </p>
                  ) : (
                    <p className="mt-1 text-sm text-[#4c576f]">
                      Open Monthly P&amp;L to create the finance profile and upload transaction
                      data.
                    </p>
                  )}

                  <div className="mt-4 flex flex-wrap gap-3">
                    <Link
                      href={`/reports/${clientSlug}/${marketplaceSlug}/pnl`}
                      className="rounded-xl bg-[#0f172a] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#1e293b]"
                    >
                      {pnlProfile ? "Open Monthly P&L" : "Open Monthly P&L Setup"}
                    </Link>
                    {wbrProfile ? (
                      <>
                        <Link
                          href={`/reports/${clientSlug}/${marketplaceSlug}/wbr`}
                          className="rounded-xl bg-[#0a6fd6] px-4 py-2 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.2)] transition hover:bg-[#0959ab]"
                        >
                          Open WBR
                        </Link>
                        <Link
                          href={`/reports/${clientSlug}/${marketplaceSlug}/wbr/settings`}
                          className="text-sm font-semibold text-[#0a6fd6] hover:underline"
                        >
                          Settings
                        </Link>
                        <Link
                          href={`/reports/${clientSlug}/${marketplaceSlug}/wbr/sync`}
                          className="text-sm font-semibold text-[#0a6fd6] hover:underline"
                        >
                          Sync
                        </Link>
                      </>
                    ) : (
                      <Link
                        href="/reports/wbr/setup"
                        className="text-sm font-semibold text-[#0a6fd6] hover:underline"
                      >
                        Set up WBR
                      </Link>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </main>
  );
}
