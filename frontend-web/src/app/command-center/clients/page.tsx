"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

type Brand = { id: string; name: string };

type Client = {
  id: string;
  name: string;
  status: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
  brands?: Brand[] | null;
};

type ApiError = { error: { code: string; message: string } };

const formatDate = (iso: string) => {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "2-digit", year: "numeric" }).format(d);
};

const statusMeta = (status: string) => {
  if (status === "archived") return { label: "Archived", cls: "bg-slate-100 text-slate-700" };
  if (status === "inactive") return { label: "Inactive", cls: "bg-amber-100 text-amber-800" };
  return { label: "Active", cls: "bg-emerald-100 text-emerald-800" };
};

const brandDisplay = (client: Client): { count: number; names: string[] } => {
  const names = (client.brands ?? []).map((b) => b.name).filter(Boolean);
  return { count: names.length, names };
};

export default function CommandCenterClientsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [clients, setClients] = useState<Client[]>([]);

  const [newName, setNewName] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive" | "archived">("all");
  const [multiBrandOnly, setMultiBrandOnly] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

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

  useEffect(() => {
    const onDoc = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null;
      if (!target) return;
      if (target.closest?.("[data-client-menu]")) return;
      setOpenMenuId(null);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
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

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (clients ?? []).filter((c) => {
      if (statusFilter !== "all" && c.status !== statusFilter) return false;
      if (multiBrandOnly && brandDisplay(c).count <= 1) return false;
      if (!q) return true;
      const brands = brandDisplay(c).names.join(" ").toLowerCase();
      return c.name.toLowerCase().includes(q) || brands.includes(q);
    });
  }, [clients, multiBrandOnly, search, statusFilter]);

  const activeClients = useMemo(
    () => filtered.filter((c) => c.status !== "archived"),
    [filtered],
  );
  const archivedClients = useMemo(
    () => filtered.filter((c) => c.status === "archived"),
    [filtered],
  );

  const stats = useMemo(() => {
    const totalClients = clients.length;
    const totalBrands = clients.reduce((sum, c) => sum + brandDisplay(c).count, 0);
    const multi = clients.filter((c) => brandDisplay(c).count > 1).length;
    return { totalClients, totalBrands, multi };
  }, [clients]);

  const ClientsTable = (props: { items: Client[] }) => {
    const { items } = props;
    return (
      <div className="mt-4 overflow-x-auto rounded-2xl border border-slate-200 bg-white">
        <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
          <thead className="bg-[#f7faff]">
            <tr className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">
              <th className="px-4 py-3">Client</th>
              <th className="px-4 py-3">Brands</th>
              <th className="px-4 py-3">Updated</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 bg-white">
            {items.map((client) => {
              const meta = statusMeta(client.status);
              const brands = brandDisplay(client);
              const shown = brands.names.slice(0, 3);
              const overflow = Math.max(0, brands.names.length - shown.length);

              return (
                <tr key={client.id} className="align-top hover:bg-slate-50">
                  <td className="px-4 py-4">
                    <div className="font-semibold text-[#0f172a]">{client.name}</div>
                    <div className="mt-1">
                      <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${meta.cls}`}>
                        {meta.label}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-4">
                    {brands.count === 0 ? (
                      <span className="text-[#64748b]">—</span>
                    ) : (
                      <div className="flex flex-wrap items-center gap-2">
                        {shown.map((name) => (
                          <span
                            key={name}
                            className="rounded-full bg-[#f1f5ff] px-3 py-1 text-xs font-semibold text-[#0f172a]"
                          >
                            {name}
                          </span>
                        ))}
                        {overflow > 0 ? (
                          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                            +{overflow} more
                          </span>
                        ) : null}
                      </div>
                    )}
                    <div className="mt-2 text-xs text-[#64748b]">{brands.count} brand{brands.count === 1 ? "" : "s"}</div>
                  </td>
                  <td className="px-4 py-4 text-[#0f172a]">{formatDate(client.updated_at)}</td>
                  <td className="px-4 py-4">
                    <div className="flex items-center justify-end gap-2">
                      <Link
                        href={`/command-center/clients/${client.id}`}
                        className="rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-[#0a6fd6] shadow transition hover:shadow-lg"
                      >
                        Manage
                      </Link>
                      <div className="relative" data-client-menu>
                        <button
                          type="button"
                          onClick={() => setOpenMenuId((cur) => (cur === client.id ? null : client.id))}
                          className="rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-[#0f172a] shadow transition hover:shadow-lg"
                          disabled={saving}
                          aria-haspopup="menu"
                          aria-expanded={openMenuId === client.id}
                        >
                          •••
                        </button>
                        {openMenuId === client.id ? (
                          <div className="absolute right-0 top-full z-20 mt-2 w-44 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl">
                            <button
                              type="button"
                              onClick={() => {
                                setOpenMenuId(null);
                                onArchive(client.id);
                              }}
                              className="block w-full px-4 py-3 text-left text-sm font-semibold text-[#0f172a] hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                              disabled={saving || client.status === "archived"}
                            >
                              Archive
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setOpenMenuId(null);
                                onDelete(client.id, client.status);
                              }}
                              className="block w-full px-4 py-3 text-left text-sm font-semibold text-[#b91c1c] hover:bg-[#fff1f2] disabled:cursor-not-allowed disabled:opacity-60"
                              disabled={saving}
                            >
                              Delete
                            </button>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  };

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

        <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Clients</div>
            <div className="mt-2 text-2xl font-semibold text-[#0f172a]">{stats.totalClients}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Brands</div>
            <div className="mt-2 text-2xl font-semibold text-[#0f172a]">{stats.totalBrands}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Multi-brand clients</div>
            <div className="mt-2 text-2xl font-semibold text-[#0f172a]">{stats.multi}</div>
          </div>
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
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-[#0f172a]">Clients</h2>
            <p className="mt-2 text-sm text-[#4c576f]">Search by client or brand name.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="min-w-[240px] rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm"
              placeholder="Search…"
              disabled={loading}
            />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)}
              className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-[#0f172a] shadow"
              disabled={loading}
            >
              <option value="all">All statuses</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="archived">Archived</option>
            </select>
            <button
              type="button"
              onClick={() => setMultiBrandOnly((v) => !v)}
              className={[
                "rounded-2xl px-4 py-3 text-sm font-semibold shadow transition",
                multiBrandOnly ? "bg-[#0a6fd6] text-white" : "bg-white text-[#0f172a]",
              ].join(" ")}
              disabled={loading}
            >
              Multi-brand
            </button>
          </div>
        </div>

        {loading ? (
          <p className="mt-4 text-sm text-[#4c576f]">Loading…</p>
        ) : activeClients.length === 0 && archivedClients.length === 0 ? (
          <p className="mt-4 text-sm text-[#4c576f]">No clients found.</p>
        ) : (
          <>
            {activeClients.length > 0 ? <ClientsTable items={activeClients} /> : null}

            {archivedClients.length > 0 ? (
              <div className="mt-6">
                <button
                  type="button"
                  onClick={() => setShowArchived((v) => !v)}
                  className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0f172a] shadow transition hover:shadow-lg"
                >
                  {showArchived ? "Hide" : "Show"} archived ({archivedClients.length})
                </button>
                {showArchived ? <ClientsTable items={archivedClients} /> : null}
              </div>
            ) : null}
          </>
        )}
      </div>
    </main>
  );
}
