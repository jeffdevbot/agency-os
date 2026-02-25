import Link from "next/link";

export default function ReportsHomePage() {
  return (
    <main className="space-y-4">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-2xl font-semibold text-[#0f172a]">Reports</h1>
        <p className="mt-2 text-sm text-[#4c576f]">
          Central workspace for recurring client reporting. Start with WBR and expand to additional report types.
        </p>

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <Link
            href="/reports/wbr"
            className="rounded-2xl border border-slate-200 bg-white p-5 shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            <p className="text-lg font-semibold text-[#0f172a]">WBR</p>
            <p className="mt-1 text-sm text-[#4c576f]">
              Open Weekly Business Reports and drill into current client outputs.
            </p>
            <p className="mt-4 text-sm font-semibold text-[#0a6fd6]">Open WBR</p>
          </Link>

          <Link
            href="/reports/wbr/setup"
            className="rounded-2xl border border-slate-200 bg-white p-5 shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            <p className="text-lg font-semibold text-[#0f172a]">Setup New WBR</p>
            <p className="mt-1 text-sm text-[#4c576f]">
              Start onboarding for a new client, then wire Windsor account-level ingestion.
            </p>
            <p className="mt-4 text-sm font-semibold text-[#0a6fd6]">Start Setup</p>
          </Link>
        </div>
      </div>
    </main>
  );
}
