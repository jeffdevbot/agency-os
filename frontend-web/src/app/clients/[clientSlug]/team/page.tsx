import AppBreadcrumbs from "@/components/nav/AppBreadcrumbs";
import ClientTeamWorkspace from "@/app/clients/_components/ClientTeamWorkspace";
import { requireAdminUser } from "../../_lib/adminGuard";
import { resolveClientBySlug } from "../../_lib/resolveClientBySlug";

type PageProps = {
  params: Promise<{
    clientSlug: string;
  }>;
};

export default async function ClientTeamPage({ params }: PageProps) {
  const { supabase } = await requireAdminUser();
  const { clientSlug } = await params;
  const client = await resolveClientBySlug(supabase, clientSlug);

  return (
    <main className="min-h-screen bg-gradient-to-br from-[#eaf2ff] via-[#dce8ff] to-[#cddcf8]">
      <AppBreadcrumbs
        items={[
          { label: "Clients", href: "/clients" },
          { label: client.name, href: `/clients/${clientSlug}` },
          { label: "Team" },
        ]}
      />
      <div className="mx-auto max-w-6xl space-y-6 px-4 py-10">
        <ClientTeamWorkspace clientId={client.id} />
      </div>
    </main>
  );
}
