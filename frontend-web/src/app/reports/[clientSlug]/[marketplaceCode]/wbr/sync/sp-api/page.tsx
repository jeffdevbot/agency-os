import WbrSyncScreen from "../../../../../_components/WbrSyncScreen";

type PageProps = {
  params: Promise<{
    clientSlug: string;
    marketplaceCode: string;
  }>;
};

export default async function ClientMarketplaceWbrSpApiSyncPage({ params }: PageProps) {
  const { clientSlug, marketplaceCode } = await params;
  return <WbrSyncScreen clientSlug={clientSlug} marketplaceCode={marketplaceCode} />;
}
