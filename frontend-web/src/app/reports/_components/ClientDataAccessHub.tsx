"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { loadActiveClients, slugifyClientName, type Client } from "../_lib/reportClientData";

const sortClients = (a: Client, b: Client): number => a.name.localeCompare(b.name);

export default function ClientDataAccessHub() {
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [clients, setClients] = useState<Client[]>([]);

  const loadClients = useCallback(async () => {
    setLoading(true);
    setErrorMessage(null);

    try {
      const nextClients = await loadActiveClients();
      setClients(nextClients.sort(sortClients));
    } catch (error) {
      setClients([]);
      setErrorMessage(error instanceof Error ? error.message : "Unable to load clients");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadClients();
  }, [loadClients]);

  return (
    <main className="space-y-4">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-2xl font-semibold text-[#0f172a]">Reports / Client Data Access</h1>
        <p className="mt-2 max-w-4xl text-sm text-[#4c576f]">
          Start with the client. The detail page is where you verify connection state, jump into
          WBR Settings to enter Windsor account information, and open WBR Sync to run backfills or
          nightly sync setup.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            onClick={() => void loadClients()}
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

        <div className="mt-8 rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-5">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[#0a6fd6]">
            Setup Reminder
          </p>
          <ol className="mt-3 space-y-2 text-sm text-[#4c576f]">
            <li>1. Open the client you want to set up.</li>
            <li>2. Use WBR Settings to enter Windsor account id and import listings.</li>
            <li>3. Use WBR Sync to run SP-API and Ads API backfills and enable nightly sync.</li>
            <li>4. Return here later if you need to reauthorize Amazon Ads or Seller API.</li>
          </ol>
        </div>

        {errorMessage ? (
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {errorMessage}
          </p>
        ) : null}

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {loading ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-[#64748b]">
              Loading clients...
            </div>
          ) : clients.length === 0 ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-[#64748b]">
              No active clients found yet.
            </div>
          ) : (
            clients.map((client) => (
              <Link
                key={client.id}
                href={`/reports/client-data-access/${slugifyClientName(client.name)}`}
                className="rounded-2xl border border-slate-200 bg-white p-5 shadow transition hover:-translate-y-0.5 hover:shadow-lg"
              >
                <p className="text-lg font-semibold text-[#0f172a]">{client.name}</p>
                <p className="mt-1 text-sm text-[#4c576f]">
                  Open this client’s data access and setup controls.
                </p>
                <p className="mt-4 text-sm font-semibold text-[#0a6fd6]">Open Client Data Access</p>
              </Link>
            ))
          )}
        </div>
      </div>
    </main>
  );
}
