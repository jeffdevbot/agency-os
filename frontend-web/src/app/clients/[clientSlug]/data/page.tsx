import AppBreadcrumbs from "@/components/nav/AppBreadcrumbs";
import ClientDataConnectionsOrchestrator from "@/app/clients/_components/data-connections/ClientDataConnectionsOrchestrator";
import ClientDataStatusDashboard from "@/app/clients/_components/ClientDataStatusDashboard";
import ReportApiAccessScreen from "@/app/reports/_components/ReportApiAccessScreen";
import { requireAdminUser } from "../../_lib/adminGuard";
import { resolveClientBySlug } from "../../_lib/resolveClientBySlug";

type PageProps = {
  params: Promise<{
    clientSlug: string;
  }>;
};

export default async function ClientDataPage({ params }: PageProps) {
  const { supabase } = await requireAdminUser();
  const { clientSlug } = await params;
  const client = await resolveClientBySlug(supabase, clientSlug);

  return (
    <main className="min-h-screen bg-gradient-to-br from-[#eaf2ff] via-[#dce8ff] to-[#cddcf8]">
      <AppBreadcrumbs
        items={[
          { label: "Clients", href: "/clients" },
          { label: client.name, href: `/clients/${clientSlug}` },
          { label: "Data" },
        ]}
      />
      <div className="mx-auto max-w-6xl space-y-6 px-4 py-10">
        <ClientDataConnectionsOrchestrator clientId={client.id} clientSlug={clientSlug} />
        <ClientDataStatusDashboard clientId={client.id} supabase={supabase} />
        <details
          id="advanced-connection-details"
          className="rounded-3xl border border-white/80 bg-white/80 p-5 shadow-sm backdrop-blur"
        >
          <summary className="cursor-pointer text-sm font-semibold text-slate-700 marker:text-slate-400">
            Advanced connection details (legacy)
          </summary>
          <div className="mt-5">
            <ReportApiAccessScreen clientSlug={clientSlug} />
          </div>
        </details>
      </div>
    </main>
  );
}
