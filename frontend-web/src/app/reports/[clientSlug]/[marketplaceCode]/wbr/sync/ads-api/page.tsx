import WbrAdsSyncScreen from "../../../../../_components/WbrAdsSyncScreen";

type PageProps = {
  params: Promise<{
    clientSlug: string;
    marketplaceCode: string;
  }>;
};

export default async function ClientMarketplaceWbrAdsApiSyncPage({ params }: PageProps) {
  const { clientSlug, marketplaceCode } = await params;
  return <WbrAdsSyncScreen clientSlug={clientSlug} marketplaceCode={marketplaceCode} />;
}
