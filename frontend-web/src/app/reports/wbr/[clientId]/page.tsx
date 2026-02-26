import WbrClientWorkspace from "./WbrClientWorkspace";

type WbrClientPageProps = {
  params: Promise<{
    clientId: string;
  }>;
};

export default async function WbrClientPage({ params }: WbrClientPageProps) {
  const { clientId } = await params;

  return <WbrClientWorkspace clientId={clientId} />;
}
