import Link from "next/link";

export default function WbrPage() {
  return (
    <main className="space-y-4">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-2xl font-semibold text-[#0f172a]">Weekly Business Reports</h1>
        <p className="mt-2 text-sm text-[#4c576f]">
          Choose an existing WBR once configured, or run setup for a new client onboarding flow.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/reports/wbr/setup"
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            Setup New WBR
          </Link>
          <Link
            href="/reports"
            className="rounded-2xl bg-[#e8eefc] px-4 py-3 text-sm font-semibold text-[#0f172a] transition hover:bg-[#d7e1fb]"
          >
            Back to Reports
          </Link>
        </div>

        <div className="mt-8 rounded-2xl border border-[#c7d8f5] bg-[#f7faff] p-5">
          <p className="text-sm font-semibold text-[#0f172a]">Current status</p>
          <p className="mt-1 text-sm text-[#4c576f]">
            WBR renderer UI is next. For now, use setup to define the client intake details and Windsor account scope.
          </p>
        </div>
      </div>
    </main>
  );
}
