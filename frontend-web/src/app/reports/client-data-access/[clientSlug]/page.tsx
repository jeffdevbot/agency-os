import { redirect } from "next/navigation";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import ReportApiAccessScreen from "../../_components/ReportApiAccessScreen";

type PageProps = {
  params: Promise<{
    clientSlug: string;
  }>;
};

export default async function ClientDataAccessDetailPage({ params }: PageProps) {
  const { clientSlug } = await params;
  const supabase = await createSupabaseRouteClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/");
  }

  const { data, error } = await supabase
    .from("profiles")
    .select("is_admin")
    .eq("id", user.id)
    .single();

  if (error || !data?.is_admin) {
    redirect("/reports");
  }

  return <ReportApiAccessScreen clientSlug={clientSlug} />;
}
