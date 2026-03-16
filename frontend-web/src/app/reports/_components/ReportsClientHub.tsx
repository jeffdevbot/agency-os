"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { loadActiveClients, slugifyClientName, type Client } from "../_lib/reportClientData";

const sortClients = (a: Client, b: Client): number => a.name.localeCompare(b.name);

export default function ReportsClientHub() {
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
      setErrorMessage(error instanceof Error ? error.message : "Unable to load report clients");
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
        <h1 className="text-2xl font-semibold text-[#0f172a]">Reports</h1>
        <p className="mt-2 text-sm text-[#4c576f]">
          Start with the client. Each marketplace now exposes two distinct reporting surfaces:
          WBR for weekly operations and Monthly P&amp;L for finance.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            onClick={() => void loadClients()}
            disabled={loading}
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {errorMessage ? (
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {errorMessage}
          </p>
        ) : null}

        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-5">
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[#0a6fd6]">WBR</p>
            <p className="mt-2 text-lg font-semibold text-[#0f172a]">Weekly Business Review</p>
            <p className="mt-2 text-sm text-[#4c576f]">
              Operational reporting with live traffic, sales, advertising, inventory, and sync
              workflows.
            </p>
          </div>
          <div className="rounded-2xl border border-[#dbe4f0] bg-[#fff8ed] p-5">
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[#9a5b16]">
              Monthly P&amp;L
            </p>
            <p className="mt-2 text-lg font-semibold text-[#0f172a]">Monthly Profit &amp; Loss</p>
            <p className="mt-2 text-sm text-[#4c576f]">
              Finance reporting from Amazon transaction uploads, separate from WBR syncs and row
              modeling.
            </p>
          </div>
        </div>

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
                href={`/reports/${slugifyClientName(client.name)}`}
                className="rounded-2xl border border-slate-200 bg-white p-5 shadow transition hover:-translate-y-0.5 hover:shadow-lg"
              >
                <p className="text-lg font-semibold text-[#0f172a]">{client.name}</p>
                <p className="mt-1 text-sm text-[#4c576f]">Open marketplace reports for this client.</p>
                <p className="mt-4 text-sm font-semibold text-[#0a6fd6]">Open Client Reports</p>
              </Link>
            ))
          )}
        </div>
      </div>
    </main>
  );
}
