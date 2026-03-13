import WbrRouteShell from "../../../_components/WbrRouteShell";

type PageProps = {
  params: Promise<{
    clientSlug: string;
    marketplaceCode: string;
  }>;
};

export default async function ClientMarketplaceWbrPage({ params }: PageProps) {
  const { clientSlug, marketplaceCode } = await params;
  return <WbrRouteShell clientSlug={clientSlug} marketplaceCode={marketplaceCode} />;
}
