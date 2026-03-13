import ResolvedWbrSettingsRoute from "../../../../_components/ResolvedWbrSettingsRoute";

type PageProps = {
  params: Promise<{
    clientSlug: string;
    marketplaceCode: string;
  }>;
};

export default async function ClientMarketplaceWbrSettingsPage({ params }: PageProps) {
  const { clientSlug, marketplaceCode } = await params;
  return (
    <ResolvedWbrSettingsRoute clientSlug={clientSlug} marketplaceCode={marketplaceCode} />
  );
}
