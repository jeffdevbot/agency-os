"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import { listWbrProfiles, type WbrProfile } from "./_lib/wbrApi";

type Client = {
  id: string;
  name: string;
  status: string;
};

type ClientsResponse = {
  clients?: Client[];
  error?: {
    message?: string;
  };
};

type WbrProfileListItem = WbrProfile & {
  client_name: string;
};

const sortByDisplayName = (a: WbrProfileListItem, b: WbrProfileListItem): number => {
  const labelCompare = a.client_name.localeCompare(b.client_name);
  if (labelCompare !== 0) return labelCompare;
  const marketplaceCompare = a.marketplace_code.localeCompare(b.marketplace_code);
  if (marketplaceCompare !== 0) return marketplaceCompare;
  return a.display_name.localeCompare(b.display_name);
};

export default function WbrPage() {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [partialErrorMessage, setPartialErrorMessage] = useState<string | null>(null);
  const [allProfileLoadsFailed, setAllProfileLoadsFailed] = useState(false);
  const [profiles, setProfiles] = useState<WbrProfileListItem[]>([]);

  const loadProfiles = useCallback(async () => {
    setLoading(true);
    setErrorMessage(null);
    setPartialErrorMessage(null);
    setAllProfileLoadsFailed(false);

    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session?.access_token) {
        throw new Error("Please sign in again.");
      }

      const clientsResponse = await fetch("/api/command-center/clients", { cache: "no-store" });
      const clientsJson = (await clientsResponse.json()) as ClientsResponse;
      if (!clientsResponse.ok) {
        throw new Error(clientsJson.error?.message ?? "Unable to load clients");
      }

      const activeClients = (clientsJson.clients ?? []).filter((client) => client.status !== "archived");
      const profileResults = await Promise.allSettled(
        activeClients.map(async (client) => {
          const clientProfiles = await listWbrProfiles(session.access_token, client.id);
          return clientProfiles.map((profile) => ({
            ...profile,
            client_name: client.name,
          }));
        })
      );

      const loadedProfiles: WbrProfileListItem[] = [];
      const failures: string[] = [];

      profileResults.forEach((result, index) => {
        if (result.status === "fulfilled") {
          loadedProfiles.push(...result.value);
          return;
        }

        const clientName = activeClients[index]?.name ?? activeClients[index]?.id ?? "unknown-client";
        const reason = result.reason instanceof Error ? result.reason.message : String(result.reason);
        failures.push(`${clientName}: ${reason}`);
      });

      setProfiles(loadedProfiles.sort(sortByDisplayName));

      if (failures.length > 0 && loadedProfiles.length === 0) {
        setErrorMessage("Unable to load WBR profiles for all clients.");
        setPartialErrorMessage(failures.join(" | "));
        setAllProfileLoadsFailed(true);
        return;
      }

      if (failures.length > 0) {
        setPartialErrorMessage(`Some clients failed to load: ${failures.join(" | ")}`);
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load WBR profiles");
      setProfiles([]);
    } finally {
      setLoading(false);
    }
  }, [supabase]);

  useEffect(() => {
    void loadProfiles();
  }, [loadProfiles]);

  return (
    <main className="space-y-4">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-2xl font-semibold text-[#0f172a]">Weekly Business Reports</h1>
        <p className="mt-2 text-sm text-[#4c576f]">
          WBR is now profile-based. Create a profile per client and marketplace, then open its workspace.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/reports/wbr/setup"
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            Setup New WBR Profile
          </Link>
          <button
            onClick={() => void loadProfiles()}
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

        <div className="mt-6 overflow-x-auto rounded-2xl border border-slate-200 bg-white">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-[#f7faff]">
              <tr className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">
                <th className="px-4 py-3">Profile</th>
                <th className="px-4 py-3">Client</th>
                <th className="px-4 py-3">Marketplace</th>
                <th className="px-4 py-3">Week Start</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-sm text-[#64748b]">
                    Loading profiles...
                  </td>
                </tr>
              ) : profiles.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-sm text-[#64748b]">
                    {allProfileLoadsFailed
                      ? "Unable to load profiles. See errors above and try refresh."
                      : "No WBR profiles found. Use setup to create the first profile."}
                  </td>
                </tr>
              ) : (
                profiles.map((profile) => (
                  <tr key={profile.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 text-[#0f172a]">{profile.display_name}</td>
                    <td className="px-4 py-3 text-[#0f172a]">{profile.client_name}</td>
                    <td className="px-4 py-3 text-[#0f172a]">{profile.marketplace_code}</td>
                    <td className="px-4 py-3 text-[#0f172a]">{profile.week_start_day}</td>
                    <td className="px-4 py-3 text-[#0f172a]">{profile.status}</td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/reports/wbr/${profile.id}`}
                        className="text-sm font-semibold text-[#0a6fd6] hover:underline"
                      >
                        Open Workspace
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
