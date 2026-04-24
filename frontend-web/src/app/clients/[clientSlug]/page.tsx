import AppBreadcrumbs from "@/components/nav/AppBreadcrumbs";
import ClientOverviewTiles from "../_components/ClientOverviewTiles";
import { requireAdminUser } from "../_lib/adminGuard";
import { resolveClientBySlug } from "../_lib/resolveClientBySlug";

type PageProps = {
  params: Promise<{
    clientSlug: string;
  }>;
};

export default async function ClientOverviewPage({ params }: PageProps) {
  const { supabase } = await requireAdminUser();
  const { clientSlug } = await params;
  const client = await resolveClientBySlug(supabase, clientSlug);

  return (
    <main className="min-h-screen bg-gradient-to-br from-[#eaf2ff] via-[#dce8ff] to-[#cddcf8]">
      <AppBreadcrumbs
        items={[{ label: "Clients", href: "/clients" }, { label: client.name }]}
      />
      <div className="mx-auto max-w-6xl space-y-6 px-4 py-10">
        <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[#0a6fd6]">
                Client Hub
              </p>
              <h1 className="mt-2 text-2xl font-semibold text-[#0f172a]">
                {client.name}
              </h1>
              <p className="mt-2 text-sm text-[#4c576f]">
                Choose the setup area for this client.
              </p>
            </div>
          </div>
        </div>

        <ClientOverviewTiles clientSlug={clientSlug} clientId={client.id} />
      </div>
    </main>
  );
}
