import AppBreadcrumbs from "@/components/nav/AppBreadcrumbs";
import ClientReportsHub from "@/app/reports/_components/ClientReportsHub";
import { requireAdminUser } from "../../_lib/adminGuard";
import { resolveClientBySlug } from "../../_lib/resolveClientBySlug";

type PageProps = {
  params: Promise<{
    clientSlug: string;
  }>;
};

export default async function ClientReportsPage({ params }: PageProps) {
  const { supabase } = await requireAdminUser();
  const { clientSlug } = await params;
  const client = await resolveClientBySlug(supabase, clientSlug);

  return (
    <main className="min-h-screen bg-gradient-to-br from-[#eaf2ff] via-[#dce8ff] to-[#cddcf8]">
      <AppBreadcrumbs
        items={[
          { label: "Clients", href: "/clients" },
          { label: client.name, href: `/clients/${clientSlug}` },
          { label: "Reports" },
        ]}
      />
      <div className="mx-auto w-full max-w-[1560px] px-4 py-5 xl:px-4 xl:py-7">
        <ClientReportsHub clientSlug={clientSlug} />
      </div>
    </main>
  );
}
