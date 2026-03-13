import WbrSyncStub from "../../../../_components/WbrSyncStub";

type PageProps = {
  params: Promise<{
    clientSlug: string;
    marketplaceCode: string;
  }>;
};

export default async function ClientMarketplaceWbrSyncPage({ params }: PageProps) {
  const { clientSlug, marketplaceCode } = await params;
  return <WbrSyncStub clientSlug={clientSlug} marketplaceCode={marketplaceCode} />;
}
