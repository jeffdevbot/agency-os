"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { AuthChangeEvent, Session } from "@supabase/supabase-js";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";

type ConsentStatus =
  | "loading"
  | "sign_in_required"
  | "ready"
  | "redirecting"
  | "error";

type AuthorizationDetails = {
  authorization_id: string;
  redirect_uri?: string;
  client: {
    client_id: string;
    client_name: string;
    client_uri: string;
    logo_uri: string;
  };
  user: {
    id: string;
    email: string;
  };
  scope: string;
};

const SCOPE_LABELS: Record<string, string> = {
  openid: "Confirm your identity",
  email: "Share your email address",
  profile: "Share your basic profile",
  phone: "Share your phone number",
};

function buildConsentUrl(authorizationId: string) {
  if (typeof window === "undefined") {
    return undefined;
  }

  const url = new URL("/oauth/consent", window.location.origin);
  url.searchParams.set("authorization_id", authorizationId);
  return url.toString();
}

function parseScopes(scopeValue: string) {
  return scopeValue
    .split(" ")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function OAuthConsentClient() {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<ConsentStatus>("loading");
  const [details, setDetails] = useState<AuthorizationDetails | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const authorizationId = searchParams.get("authorization_id");
  const missingAuthorizationId = !authorizationId;

  useEffect(() => {
    if (missingAuthorizationId) {
      return;
    }

    let cancelled = false;

    const loadConsentDetails = async (session: Session | null) => {
      if (cancelled) {
        return;
      }

      if (!session) {
        setDetails(null);
        setStatus("sign_in_required");
        return;
      }

      setStatus("loading");
      setErrorMessage(null);

      const { data, error } = await supabase.auth.oauth.getAuthorizationDetails(
        authorizationId
      );

      if (cancelled) {
        return;
      }

      if (error) {
        setDetails(null);
        if (error.name === "AuthSessionMissingError") {
          setStatus("sign_in_required");
          return;
        }
        setStatus("error");
        setErrorMessage(error.message);
        return;
      }

      if (!data) {
        setDetails(null);
        setStatus("error");
        setErrorMessage("Authorization details were not returned by Supabase.");
        return;
      }

      setDetails(data as AuthorizationDetails);
      setStatus("ready");
    };

    supabase.auth
      .getSession()
      .then(({ data }: { data: { session: Session | null } }) =>
        loadConsentDetails(data.session)
      )
      .catch((error: unknown) => {
        const message =
          error instanceof Error ? error.message : "Failed to check auth session.";
        setStatus("error");
        setErrorMessage(message);
      });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(
      (_event: AuthChangeEvent, session: Session | null) => {
        void loadConsentDetails(session);
      }
    );

    return () => {
      cancelled = true;
      subscription.unsubscribe();
    };
  }, [authorizationId, missingAuthorizationId, supabase]);

  const handleGoogleSignIn = async () => {
    if (missingAuthorizationId || !authorizationId) {
      setStatus("error");
      setErrorMessage("Missing authorization_id in the consent request.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: buildConsentUrl(authorizationId),
      },
    });

    if (error) {
      setIsSubmitting(false);
      setStatus("error");
      setErrorMessage(error.message);
    }
  };

  const handleDecision = async (decision: "approve" | "deny") => {
    if (missingAuthorizationId || !authorizationId) {
      setStatus("error");
      setErrorMessage("Missing authorization_id in the consent request.");
      return;
    }

    setIsSubmitting(true);
    setStatus("redirecting");
    setErrorMessage(null);

    const response =
      decision === "approve"
        ? await supabase.auth.oauth.approveAuthorization(authorizationId)
        : await supabase.auth.oauth.denyAuthorization(authorizationId);

    if (response.error) {
      setIsSubmitting(false);
      setStatus("error");
      setErrorMessage(response.error.message);
    }
  };

  const requestedScopes = parseScopes(details?.scope ?? "");

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,#f4f7ff,transparent_35%),linear-gradient(180deg,#f7f9fc_0%,#edf2fb_100%)] px-4 py-10 text-slate-900">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-3xl items-center justify-center">
        <section className="w-full overflow-hidden rounded-[28px] border border-slate-200/80 bg-white shadow-[0_24px_80px_rgba(15,23,42,0.10)]">
          <div className="border-b border-slate-200 bg-slate-950 px-8 py-6 text-white">
            <p className="text-sm font-medium uppercase tracking-[0.24em] text-slate-300">
              Agency OS
            </p>
            <h1 className="mt-3 text-3xl font-semibold">
              OAuth access request
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-300">
              Review what this MCP client is asking to access before continuing.
            </p>
          </div>

          <div className="space-y-6 px-8 py-8">
            {status === "loading" ? (
              <div className="space-y-3 rounded-3xl border border-slate-200 bg-slate-50 px-6 py-8 text-center">
                <p className="text-base font-semibold text-slate-900">
                  Loading authorization details…
                </p>
                <p className="text-sm text-slate-600">
                  Checking your Supabase session and retrieving the consent request.
                </p>
              </div>
            ) : null}

            {missingAuthorizationId ? (
              <div className="space-y-3 rounded-3xl border border-rose-200 bg-rose-50 px-6 py-5">
                <p className="text-sm font-semibold text-rose-900">
                  Authorization failed
                </p>
                <p className="text-sm leading-6 text-rose-800">
                  Missing authorization_id in the consent request.
                </p>
              </div>
            ) : null}

            {status === "sign_in_required" ? (
              <div className="space-y-5 rounded-3xl border border-slate-200 bg-slate-50 px-6 py-8">
                <div className="space-y-2">
                  <h2 className="text-xl font-semibold text-slate-900">
                    Sign in to continue
                  </h2>
                  <p className="text-sm leading-6 text-slate-600">
                    Claude is requesting access through Agency OS. Sign in with your
                    Ecomlabs account first, then you&apos;ll return here to approve or
                    deny the request.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleGoogleSignIn}
                  disabled={isSubmitting}
                  className="inline-flex items-center justify-center rounded-2xl bg-[#0a6fd6] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#085eb5] disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {isSubmitting ? "Redirecting to Google…" : "Sign in with Google"}
                </button>
              </div>
            ) : null}

            {status === "ready" && details ? (
              <div className="space-y-6">
                <div className="grid gap-4 rounded-3xl border border-slate-200 bg-slate-50 p-6 md:grid-cols-[1.6fr,1fr]">
                  <div className="space-y-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                      Client
                    </p>
                    <div className="space-y-1">
                      <h2 className="text-2xl font-semibold text-slate-950">
                        {details.client.client_name}
                      </h2>
                      <p className="text-sm text-slate-600">
                        This client wants to connect to the private Agency OS MCP
                        integration.
                      </p>
                    </div>
                    {details.client.client_uri ? (
                      <a
                        href={details.client.client_uri}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex text-sm font-medium text-[#0a6fd6] hover:text-[#085eb5]"
                      >
                        {details.client.client_uri}
                      </a>
                    ) : null}
                  </div>

                  <div className="space-y-2 rounded-2xl bg-white p-4 shadow-sm">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                      Signed in as
                    </p>
                    <p className="text-sm font-medium text-slate-900">
                      {details.user.email}
                    </p>
                    <p className="break-all font-mono text-xs text-slate-500">
                      {details.user.id}
                    </p>
                  </div>
                </div>

                <div className="space-y-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                    Requested permissions
                  </p>
                  <div className="grid gap-3">
                    {requestedScopes.length > 0 ? (
                      requestedScopes.map((scope) => (
                        <div
                          key={scope}
                          className="rounded-2xl border border-slate-200 px-4 py-4"
                        >
                          <p className="text-sm font-semibold text-slate-900">
                            {scope}
                          </p>
                          <p className="mt-1 text-sm text-slate-600">
                            {SCOPE_LABELS[scope] ??
                              "Grant this MCP client the requested OAuth scope."}
                          </p>
                        </div>
                      ))
                    ) : (
                      <div className="rounded-2xl border border-slate-200 px-4 py-4 text-sm text-slate-600">
                        No scopes were listed on the authorization request.
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex flex-col gap-3 border-t border-slate-200 pt-2 sm:flex-row">
                  <button
                    type="button"
                    onClick={() => void handleDecision("approve")}
                    disabled={isSubmitting}
                    className="inline-flex items-center justify-center rounded-2xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    {isSubmitting ? "Submitting…" : "Approve access"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleDecision("deny")}
                    disabled={isSubmitting}
                    className="inline-flex items-center justify-center rounded-2xl border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    Deny
                  </button>
                </div>
              </div>
            ) : null}

            {status === "redirecting" ? (
              <div className="rounded-3xl border border-blue-200 bg-blue-50 px-6 py-5 text-sm text-blue-900">
                Redirecting back to the OAuth client…
              </div>
            ) : null}

            {status === "error" && errorMessage ? (
              <div className="space-y-3 rounded-3xl border border-rose-200 bg-rose-50 px-6 py-5">
                <p className="text-sm font-semibold text-rose-900">
                  Authorization failed
                </p>
                <p className="text-sm leading-6 text-rose-800">{errorMessage}</p>
              </div>
            ) : null}

            <div className="border-t border-slate-200 pt-5 text-sm text-slate-500">
              Need to leave this flow? Return to the{" "}
              <Link href="/" className="font-medium text-[#0a6fd6] hover:text-[#085eb5]">
                Agency OS dashboard
              </Link>
              .
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
