import { createBrowserClient } from "@supabase/ssr";

type BrowserSupabaseClient = ReturnType<typeof createBrowserClient>;

let client: BrowserSupabaseClient | null = null;

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl) {
  throw new Error("Missing required environment variable: NEXT_PUBLIC_SUPABASE_URL");
}
if (!supabaseAnonKey) {
  throw new Error("Missing required environment variable: NEXT_PUBLIC_SUPABASE_ANON_KEY");
}

export const getBrowserSupabaseClient = (): BrowserSupabaseClient => {
  if (!client) {
    client = createBrowserClient(supabaseUrl, supabaseAnonKey);
  }

  return client;
};
