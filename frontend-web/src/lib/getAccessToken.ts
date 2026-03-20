import { getBrowserSupabaseClient } from "./supabaseClient";

/**
 * Get the current Supabase access token, retrying once after a short delay
 * if the session isn't ready yet (common on initial page load).
 */
export async function getAccessToken(): Promise<string> {
  const supabase = getBrowserSupabaseClient();

  for (let attempt = 1; attempt <= 2; attempt += 1) {
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (session?.access_token) {
      return session.access_token;
    }

    if (attempt === 1) {
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }

  throw new Error("Please sign in again.");
}
