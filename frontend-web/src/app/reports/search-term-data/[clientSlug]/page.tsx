import { redirect } from "next/navigation";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import SearchTermDataScreen from "../../_components/SearchTermDataScreen";

type PageProps = {
  params: Promise<{
    clientSlug: string;
  }>;
};

export default async function SearchTermDataPage({ params }: PageProps) {
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

  return <SearchTermDataScreen clientSlug={clientSlug} />;
}
