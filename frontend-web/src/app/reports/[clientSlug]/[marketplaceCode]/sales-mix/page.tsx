import SalesMixScreen from "../../../_components/SalesMixScreen";

type PageProps = {
  params: Promise<{
    clientSlug: string;
    marketplaceCode: string;
  }>;
};

export default async function ClientMarketplaceSalesMixPage({ params }: PageProps) {
  const { clientSlug, marketplaceCode } = await params;
  return <SalesMixScreen clientSlug={clientSlug} marketplaceCode={marketplaceCode} />;
}
