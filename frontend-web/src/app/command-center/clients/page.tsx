"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

type Client = {
  id: string;
  name: string;
  status: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

type ApiError = { error: { code: string; message: string } };

export default function CommandCenterClientsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [clients, setClients] = useState<Client[]>([]);

  const [newName, setNewName] = useState("");

  const loadClients = useCallback(async () => {
    setLoading(true);
    setErrorMessage(null);

    const response = await fetch("/api/command-center/clients", { cache: "no-store" });
    const json = (await response.json()) as { clients?: Client[] } & Partial<ApiError>;
    if (!response.ok) {
      setClients([]);
      setLoading(false);
      setErrorMessage(json.error?.message ?? "Unable to load clients");
      return;
    }

    setClients(json.clients ?? []);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetch("/api/command-center/clients", { cache: "no-store" })
      .then(async (response) => {
        const json = (await response.json()) as { clients?: Client[] } & Partial<ApiError>;
        if (!response.ok) {
          setClients([]);
          setLoading(false);
          setErrorMessage(json.error?.message ?? "Unable to load clients");
          return;
        }

        setClients(json.clients ?? []);
        setLoading(false);
      })
      .catch(() => {
        setClients([]);
        setLoading(false);
        setErrorMessage("Unable to load clients");
      });
  }, []);

  const onCreate = useCallback(async () => {
    setSaving(true);
    setErrorMessage(null);

    const response = await fetch("/api/command-center/clients", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name: newName }),
    });
    const json = (await response.json()) as Partial<ApiError>;
    if (!response.ok) {
      setSaving(false);
      setErrorMessage(json.error?.message ?? "Unable to create client");
      return;
    }

    setNewName("");
    setSaving(false);
    await loadClients();
  }, [loadClients, newName]);

  const onArchive = useCallback(
    async (clientId: string) => {
      const confirmed = window.confirm("Archive this client?");
      if (!confirmed) return;

      setSaving(true);
      setErrorMessage(null);

      const response = await fetch(`/api/command-center/clients/${clientId}/archive`, {
        method: "POST",
      });
      const json = (await response.json()) as Partial<ApiError>;
      if (!response.ok) {
        setSaving(false);
        setErrorMessage(json.error?.message ?? "Unable to archive client");
        return;
      }

      setSaving(false);
      await loadClients();
    },
    [loadClients],
  );

  const onDelete = useCallback(
    async (clientId: string, status: string) => {
      const confirmed = window.confirm(
        status === "archived"
          ? "Delete this client permanently? This cannot be undone."
          : "Delete this client permanently? This will archive it first. This cannot be undone.",
      );
      if (!confirmed) return;

      setSaving(true);
      setErrorMessage(null);

      if (status !== "archived") {
        const archiveResponse = await fetch(`/api/command-center/clients/${clientId}/archive`, {
          method: "POST",
        });
        const archiveJson = (await archiveResponse.json()) as Partial<ApiError>;
        if (!archiveResponse.ok) {
          setSaving(false);
          setErrorMessage(archiveJson.error?.message ?? "Unable to archive client");
          return;
        }
      }

      const response = await fetch(`/api/command-center/clients/${clientId}`, {
        method: "DELETE",
      });
      const json = (await response.json()) as Partial<ApiError>;
      if (!response.ok) {
        setSaving(false);
        setErrorMessage(json.error?.message ?? "Unable to delete client");
        return;
      }

      setSaving(false);
      await loadClients();
    },
    [loadClients],
  );

  return (
    <main className="space-y-6">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-[#0f172a]">Clients</h1>
            <p className="mt-2 text-sm text-[#4c576f]">
              Create clients, then add brands and assign roles.
            </p>
          </div>
          <button
            onClick={loadClients}
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
            disabled={loading || saving}
          >
            Refresh
          </button>
        </div>

        {errorMessage ? (
          <p className="mt-6 rounded-2xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {errorMessage}
          </p>
        ) : null}
      </div>

      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h2 className="text-lg font-semibold text-[#0f172a]">Add Client</h2>
        <div className="mt-4 flex flex-wrap gap-3">
          <input
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
            className="min-w-[280px] flex-1 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm"
            placeholder="Client name"
            disabled={saving}
          />
          <button
            onClick={onCreate}
            className="rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab]"
            disabled={saving || newName.trim().length === 0}
          >
            {saving ? "Saving…" : "Create"}
          </button>
        </div>
      </div>

      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h2 className="text-lg font-semibold text-[#0f172a]">All Clients</h2>
        {loading ? (
          <p className="mt-4 text-sm text-[#4c576f]">Loading…</p>
        ) : clients.length === 0 ? (
          <p className="mt-4 text-sm text-[#4c576f]">No clients yet.</p>
        ) : (
          <div className="mt-4 divide-y divide-slate-200">
	            {clients.map((client) => (
	              <div key={client.id} className="flex flex-wrap items-center justify-between gap-4 py-4">
	                <div>
	                  <div className="text-sm font-semibold text-[#0f172a]">{client.name}</div>
	                  <div className="mt-1 text-xs text-[#4c576f]">{client.status}</div>
	                </div>
	                <div className="flex flex-wrap items-center gap-2">
	                  <Link
	                    href={`/command-center/clients/${client.id}`}
	                    className="rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-[#0a6fd6] shadow transition hover:shadow-lg"
	                  >
	                    Manage
	                  </Link>
	                  <button
	                    onClick={() => onArchive(client.id)}
	                    className="rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-[#b91c1c] shadow transition hover:shadow-lg"
	                    disabled={saving || client.status === "archived"}
	                  >
	                    Archive
	                  </button>
	                  {client.status === "archived" ? (
	                    <button
	                      onClick={() => onDelete(client.id, client.status)}
	                      className="rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-[#b91c1c] shadow transition hover:shadow-lg"
	                      disabled={saving}
	                    >
	                      Delete
	                    </button>
	                  ) : (
	                    <button
	                      onClick={() => onDelete(client.id, client.status)}
	                      className="rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-[#b91c1c] shadow transition hover:shadow-lg"
	                      disabled={saving}
	                    >
	                      Delete
	                    </button>
	                  )}
	                </div>
	              </div>
	            ))}
	          </div>
	        )}
      </div>
    </main>
  );
}
