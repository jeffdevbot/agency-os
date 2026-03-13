"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import { getWbrProfile } from "../wbr/_lib/wbrApi";
import {
  findClientById,
  loadActiveClients,
  slugifyClientName,
} from "../_lib/reportClientData";

type Props = {
  profileId: string;
};

export default function ProfileIdRedirector({ profileId }: Props) {
  const router = useRouter();
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const resolveRoute = useCallback(async () => {
    setErrorMessage(null);

    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session?.access_token) {
        throw new Error("Please sign in again.");
      }

      const profile = await getWbrProfile(session.access_token, profileId);
      const clients = await loadActiveClients();
      const client = findClientById(clients, profile.client_id);

      if (!client) {
        throw new Error("Unable to resolve client route for this WBR profile.");
      }

      const clientSlug = slugifyClientName(client.name);
      router.replace(
        `/reports/${clientSlug}/${profile.marketplace_code.toLowerCase()}/wbr/settings`
      );
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to resolve WBR route");
    }
  }, [profileId, router, supabase]);

  useEffect(() => {
    void resolveRoute();
  }, [resolveRoute]);

  return (
    <main className="space-y-4">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-2xl font-semibold text-[#0f172a]">Redirecting WBR Route</h1>
        <p className="mt-2 text-sm text-[#4c576f]">
          Resolving the new client and marketplace route for this legacy profile link.
        </p>
        {errorMessage ? (
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {errorMessage}
          </p>
        ) : null}
      </div>
    </main>
  );
}
