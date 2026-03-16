import PnlReportScreen from "../../../_components/PnlReportScreen";

type PageProps = {
  params: Promise<{
    clientSlug: string;
    marketplaceCode: string;
  }>;
};

export default async function ClientMarketplacePnlPage({ params }: PageProps) {
  const { clientSlug, marketplaceCode } = await params;
  return <PnlReportScreen clientSlug={clientSlug} marketplaceCode={marketplaceCode} />;
}
