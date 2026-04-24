import "server-only";

import { redirect } from "next/navigation";
import type { SupabaseRouteClient } from "@/lib/supabase/serverClient";
import { slugifyClientName } from "@/app/reports/_lib/reportClientData";

type ResolvedClient = {
  id: string;
  name: string;
};

export const resolveClientBySlug = async (
  supabase: SupabaseRouteClient,
  slug: string,
): Promise<ResolvedClient> => {
  const { data, error } = await supabase
    .from("agency_clients")
    .select("id, name")
    .eq("status", "active")
    .order("name", { ascending: true });

  if (error) {
    redirect("/clients");
  }

  const client =
    data?.find((candidate) => slugifyClientName(candidate.name) === slug) ?? null;

  if (!client) {
    redirect("/clients");
  }

  return client;
};
