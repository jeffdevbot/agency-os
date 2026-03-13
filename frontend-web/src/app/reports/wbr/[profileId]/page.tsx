import ProfileIdRedirector from "../../_components/ProfileIdRedirector";

type WbrProfilePageProps = {
  params: Promise<{
    profileId: string;
  }>;
};

export default async function WbrProfilePage({ params }: WbrProfilePageProps) {
  const { profileId } = await params;

  return <ProfileIdRedirector profileId={profileId} />;
}
