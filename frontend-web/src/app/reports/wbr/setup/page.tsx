"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

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

export default function WbrSetupPage() {
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [clients, setClients] = useState<Client[]>([]);
  const [selectedClientId, setSelectedClientId] = useState("");

  useEffect(() => {
    fetch("/api/command-center/clients", { cache: "no-store" })
      .then(async (response) => {
        const json = (await response.json()) as ClientsResponse;
        if (!response.ok) {
          setErrorMessage(json.error?.message ?? "Unable to load clients");
          setClients([]);
          setLoading(false);
          return;
        }
        const active = (json.clients ?? []).filter((client) => client.status !== "archived");
        setClients(active);
        if (active.length > 0) {
          setSelectedClientId(active[0].id);
        }
        setLoading(false);
      })
      .catch(() => {
        setErrorMessage("Unable to load clients");
        setClients([]);
        setLoading(false);
      });
  }, []);

  const selectedClient = useMemo(
    () => clients.find((client) => client.id === selectedClientId) ?? null,
    [clients, selectedClientId]
  );

  return (
    <main className="space-y-4">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-2xl font-semibold text-[#0f172a]">Setup New WBR</h1>
        <p className="mt-2 text-sm text-[#4c576f]">
          New client onboarding for Windsor-based WBR ingestion and reporting.
        </p>

        <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-5">
          <label htmlFor="client" className="text-sm font-semibold text-[#0f172a]">
            Client
          </label>
          {loading ? (
            <p className="mt-2 text-sm text-[#4c576f]">Loading clients...</p>
          ) : clients.length === 0 ? (
            <div className="mt-2 space-y-2">
              <p className="text-sm text-[#4c576f]">
                No active clients available. Add one in Command Center first.
              </p>
              <Link
                href="/command-center/clients"
                className="inline-flex rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
              >
                Open Command Center Clients
              </Link>
            </div>
          ) : (
            <>
              <select
                id="client"
                value={selectedClientId}
                onChange={(event) => setSelectedClientId(event.target.value)}
                className="mt-2 w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
              >
                {clients.map((client) => (
                  <option key={client.id} value={client.id}>
                    {client.name}
                  </option>
                ))}
              </select>
            </>
          )}
        </div>

        <div className="mt-4 rounded-2xl border border-[#c7d8f5] bg-[#f7faff] p-5">
          <p className="text-sm font-semibold text-[#0f172a]">Intake checklist</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-[#4c576f]">
            <li>Confirm Windsor account IDs per marketplace (US, CA, etc).</li>
            <li>Confirm grouping strategy for rows (brand/category/custom mapping).</li>
            <li>Save WBR config, then run 3-day smoke ingest followed by 4 weekly chunks.</li>
            <li>Validate totals against manual WBR sheet before enabling nightly cron.</li>
          </ul>
        </div>

        {selectedClient ? (
          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href={`/reports/wbr/${selectedClient.id}`}
              className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
            >
              Continue for {selectedClient.name}
            </Link>
            <Link
              href="/reports/wbr"
              className="rounded-2xl bg-[#e8eefc] px-4 py-3 text-sm font-semibold text-[#0f172a] transition hover:bg-[#d7e1fb]"
            >
              Back to WBR
            </Link>
          </div>
        ) : null}

        {errorMessage ? (
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {errorMessage}
          </p>
        ) : null}
      </div>
    </main>
  );
}
