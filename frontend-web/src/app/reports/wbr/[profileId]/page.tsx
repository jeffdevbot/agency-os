import WbrProfileWorkspace from "./WbrProfileWorkspace";

type WbrProfilePageProps = {
  params: Promise<{
    profileId: string;
  }>;
};

export default async function WbrProfilePage({ params }: WbrProfilePageProps) {
  const { profileId } = await params;

  return <WbrProfileWorkspace profileId={profileId} />;
}
