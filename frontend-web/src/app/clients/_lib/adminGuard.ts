import "server-only";

import { redirect } from "next/navigation";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";

export const requireAdminUser = async () => {
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
    redirect("/");
  }

  return { user, supabase };
};
