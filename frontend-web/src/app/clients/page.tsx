import Link from "next/link";
import AppBreadcrumbs from "@/components/nav/AppBreadcrumbs";
import { requireAdminUser } from "./_lib/adminGuard";
import { slugifyClientName } from "../reports/_lib/reportClientData";

type ClientRow = {
  id: string;
  name: string;
  status: string;
};

export default async function ClientsPage() {
  const { supabase } = await requireAdminUser();

  const { data, error } = await supabase
    .from("agency_clients")
    .select("id, name, status")
    .eq("status", "active")
    .order("name", { ascending: true });

  const clients = (data ?? []) as ClientRow[];

  return (
    <main className="min-h-screen bg-gradient-to-br from-[#eaf2ff] via-[#dce8ff] to-[#cddcf8]">
      <AppBreadcrumbs items={[{ label: "Clients" }]} />
      <div className="mx-auto max-w-6xl space-y-6 px-4 py-10">
        <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[#0a6fd6]">
                Admin
              </p>
              <h1 className="mt-2 text-2xl font-semibold text-[#0f172a]">
                Clients
              </h1>
              <p className="mt-2 text-sm text-[#4c576f]">
                Select a client to open reports, data access, or team setup.
              </p>
            </div>
          </div>

          {error ? (
            <p className="mt-6 rounded-2xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
              Unable to load clients.
            </p>
          ) : null}
        </div>

        <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          <h2 className="text-lg font-semibold text-[#0f172a]">
            Active Clients
          </h2>
          {clients.length === 0 ? (
            <p className="mt-4 text-sm text-[#4c576f]">No active clients found.</p>
          ) : (
            <div className="mt-4 overflow-x-auto rounded-2xl border border-slate-200 bg-white">
              <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                <thead className="bg-[#f7faff]">
                  <tr className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">
                    <th className="px-4 py-3">Client</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 bg-white">
                  {clients.map((client) => {
                    const clientSlug = slugifyClientName(client.name);
                    return (
                      <tr key={client.id} className="hover:bg-slate-50">
                        <td className="px-4 py-4">
                          <div className="font-semibold text-[#0f172a]">
                            {client.name}
                          </div>
                          <div className="mt-1">
                            <span className="inline-flex rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-800">
                              Active
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-4 text-right">
                          <Link
                            href={`/clients/${clientSlug}`}
                            className="rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-[#0a6fd6] shadow transition hover:shadow-lg"
                          >
                            Open
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
