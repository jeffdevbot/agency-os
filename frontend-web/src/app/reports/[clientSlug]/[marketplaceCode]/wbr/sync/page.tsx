import WbrSyncOverviewScreen from "../../../../_components/WbrSyncOverviewScreen";

type PageProps = {
  params: Promise<{
    clientSlug: string;
    marketplaceCode: string;
  }>;
};

export default async function ClientMarketplaceWbrSyncPage({ params }: PageProps) {
  const { clientSlug, marketplaceCode } = await params;
  return <WbrSyncOverviewScreen clientSlug={clientSlug} marketplaceCode={marketplaceCode} />;
}
