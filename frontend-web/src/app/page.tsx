"use client";

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

  return (
    <main className="flex min-h-screen flex-col items-center px-4 py-10 text-[#0f172a]">
      <header className="w-full max-w-4xl">
        <div className="flex items-center justify-between py-4">
          <div className="brand-logo">
            Ecom<span>labs</span>
          </div>
          <span className="text-sm font-medium text-[#4c576f]">
            Internal Access
          </span>
        </div>
        <div className="mt-6 max-w-2xl">
          <p className="text-sm font-semibold uppercase tracking-[0.5em] text-[#0a6fd6]">
            Agency OS
          </p>
          <h1 className="mt-4 text-4xl font-semibold leading-tight text-[#0a1f44]">
            One login for Ngram, Operator, Composer, and Creative Brief.
          </h1>
          <p className="mt-3 text-base text-[#4c576f]">
            Sign in with your Google Workspace account to access every internal
            workflow in a single Render-hosted console.
          </p>
        </div>
      </header>

      <section className="mt-10 w-full max-w-4xl">
        <div className="elevation-card mx-auto w-full max-w-lg rounded-3xl p-8">
          {authLoading ? (
            <p className="text-center text-sm text-[#4c576f]">
              Checking session…
            </p>
          ) : session ? (
            <div className="space-y-6">
              <div className="rounded-2xl bg-[#f4f7fc] p-5">
                <p className="text-xs uppercase tracking-[0.4em] text-[#0a6fd6]">
                  Signed in as
                </p>
                <p className="mt-3 text-2xl font-semibold text-[#0a1f44]">
                  {friendlyName}
                </p>
                <p className="text-sm text-[#4c576f]">
                  Your session unlocks the secure dashboard and Supabase-backed
                  APIs.
                </p>
              </div>
              <button
                onClick={handleSignOut}
                className="action-muted flex w-full items-center justify-center rounded-2xl py-3 text-base font-semibold"
                disabled={buttonLoading}
              >
                {buttonLoading ? "Signing out…" : "Sign out"}
              </button>
            </div>
          ) : (
            <div className="space-y-6">
              <p className="text-sm text-[#4c576f]">
                Use the Google SSO button below. OAuth is routed through
                Supabase, so ensure the new Render URL plus localhost are listed
                in the Supabase redirect settings.
              </p>
              <button
                onClick={handleSignIn}
                className="action-primary flex w-full items-center justify-center rounded-2xl py-3 text-base font-semibold"
                disabled={buttonLoading}
              >
                {buttonLoading ? "Redirecting…" : "Continue with Google"}
              </button>
              <p className="text-center text-xs text-[#4c576f]">
                Only Ecomlabs Google Workspace accounts are permitted.
              </p>
            </div>
          )}

          {errorMessage && (
            <p className="mt-6 rounded-2xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
              {errorMessage}
            </p>
          )}
        </div>
      </section>
    </main>
  );
}
