import ClientReportsHub from "../_components/ClientReportsHub";

type PageProps = {
  params: Promise<{
    clientSlug: string;
  }>;
};

export default async function ClientReportsPage({ params }: PageProps) {
  const { clientSlug } = await params;
  return <ClientReportsHub clientSlug={clientSlug} />;
}
