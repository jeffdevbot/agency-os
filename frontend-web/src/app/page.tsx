"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { type Session } from "@supabase/supabase-js";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";

export default function Home() {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [buttonLoading, setButtonLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setAuthLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
      setAuthLoading(false);
      setButtonLoading(false);
    });

    return () => {
      subscription.unsubscribe();
    };
  }, [supabase]);

  const handleSignIn = useCallback(async () => {
    setButtonLoading(true);
    setErrorMessage(null);

    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo:
          typeof window !== "undefined" ? window.location.origin : undefined,
      },
    });

    if (error) {
      setErrorMessage(error.message);
      setButtonLoading(false);
    }
  }, [supabase]);

  const handleSignOut = useCallback(async () => {
    setButtonLoading(true);
    const { error } = await supabase.auth.signOut();
    if (error) {
      setErrorMessage(error.message);
    }
    setButtonLoading(false);
  }, [supabase]);

  const friendlyName =
    session?.user.user_metadata.full_name ||
    session?.user.user_metadata.name ||
    session?.user.email;
  const firstName = friendlyName?.split(" ")[0];

  return (
    <main className="flex min-h-screen flex-col bg-gradient-to-br from-[#eaf2ff] via-[#dce8ff] to-[#cddcf8]">
      <div className="flex w-full flex-col items-center gap-2 px-6 py-8 text-sm font-semibold text-[#1f2937]">
        <div className="text-2xl font-bold tracking-tight">
          <span className="text-[#0f172a]">Ecom</span>
          <span className="text-[#0a6fd6]">labs</span>
        </div>
        <span className="text-xs uppercase tracking-[0.4em] text-[#4c576f]">
          Internal Access
        </span>
      </div>

      <div className="flex flex-1 items-center justify-center px-4 pb-16">
        <div className="w-full max-w-md space-y-4 text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.5em] text-[#4c576f]">
            Agency OS
          </p>
          <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
            {authLoading ? (
              <div className="flex min-h-[220px] flex-col items-center justify-center space-y-3 text-sm text-[#4c576f]">
                <span className="text-base font-semibold text-[#0f172a]">
                  Checking session…
                </span>
                <span className="text-xs">
                  Hold tight while we verify your Supabase auth token.
                </span>
              </div>
            ) : session ? (
            <div className="space-y-6">
              <div className="space-y-1">
                <p className="text-3xl font-semibold text-[#0f172a]">
                  Hello {firstName ?? "there"} 👋
                </p>
                <p className="text-sm text-[#4c576f]">
                  You&apos;re signed in to Agency OS as {friendlyName}.
                </p>
              </div>

              <div className="grid gap-4 rounded-3xl bg-[#f7f8ff] p-5">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[#94a3b8]">
                    Tools
                  </p>
                  <p className="text-base font-semibold text-[#0f172a]">
                    N-Gram Processor
                  </p>
                  <p className="text-sm text-[#4c576f]">
                    Upload Amazon search term reports to generate Monogram, Bigram, and
                    Trigram insights.
                  </p>
                </div>
                <Link
                  href="/ngram"
                  className="flex items-center justify-between rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
                >
                  Open tool<span aria-hidden="true">→</span>
                </Link>
              </div>

              <button
                onClick={handleSignOut}
                className="w-full rounded-2xl bg-[#e8eefc] px-4 py-3 text-sm font-semibold text-[#0f172a] transition hover:bg-[#d7e1fb]"
                disabled={buttonLoading}
              >
                {buttonLoading ? "Signing out…" : "Sign out"}
              </button>
            </div>
            ) : (
              <div className="space-y-6 text-left">
                <div className="space-y-2">
                  <p className="text-3xl font-semibold text-[#0f172a]">
                    Welcome
                  </p>
                  <p className="text-sm text-[#4c576f]">
                    Sign in with your Ecomlabs Google account to continue.
                  </p>
                </div>
                <button
                  onClick={handleSignIn}
                  className="w-full rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab]"
                  disabled={buttonLoading}
                >
                  {buttonLoading ? "Redirecting…" : "Continue with Google"}
                </button>
                <p className="text-xs text-[#94a3b8]">
                  Ecomlabs Google Workspace accounts only.
                </p>
              </div>
            )}

            {errorMessage && (
              <p className="mt-6 rounded-2xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
                {errorMessage}
              </p>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
