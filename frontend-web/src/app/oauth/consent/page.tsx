import { Suspense } from "react";
import { OAuthConsentClient } from "./OAuthConsentClient";

export const dynamic = "force-dynamic";
export const revalidate = 0;

function LoadingFallback() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,#f4f7ff,transparent_35%),linear-gradient(180deg,#f7f9fc_0%,#edf2fb_100%)] px-4 py-10 text-slate-900">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-3xl items-center justify-center">
        <section className="w-full overflow-hidden rounded-[28px] border border-slate-200/80 bg-white shadow-[0_24px_80px_rgba(15,23,42,0.10)]">
          <div className="border-b border-slate-200 bg-slate-950 px-8 py-6 text-white">
            <p className="text-sm font-medium uppercase tracking-[0.24em] text-slate-300">
              Ecomlabs Tools
            </p>
            <h1 className="mt-3 text-3xl font-semibold">OAuth access request</h1>
          </div>
          <div className="space-y-3 px-8 py-8">
            <p className="text-base font-semibold text-slate-900">
              Loading authorization details…
            </p>
            <p className="text-sm text-slate-600">
              Checking your Supabase session and retrieving the consent request.
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}

export default function OAuthConsentPage() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <OAuthConsentClient />
    </Suspense>
  );
}
