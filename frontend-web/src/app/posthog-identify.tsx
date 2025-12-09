"use client";

import { useEffect } from "react";
import posthog from "posthog-js";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";

export function PosthogIdentify() {
  useEffect(() => {
    const run = async () => {
      const supabase = getBrowserSupabaseClient();
      const { data } = await supabase.auth.getSession();
      const user = data.session?.user;
      if (!user || !posthog.__loaded) return;

      const displayName =
        (user.user_metadata && (user.user_metadata.full_name || user.user_metadata.name)) ||
        user.email ||
        user.id;

      posthog.identify(user.id, {
        email: user.email,
        name: displayName,
      });
    };
    run();
  }, []);

  return null;
}
