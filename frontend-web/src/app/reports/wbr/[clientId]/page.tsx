import Link from "next/link";

type WbrClientPageProps = {
  params: Promise<{
    clientId: string;
  }>;
};

export default async function WbrClientPage({ params }: WbrClientPageProps) {
  const { clientId } = await params;

  return (
    <main className="space-y-4">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-2xl font-semibold text-[#0f172a]">WBR Client Workspace</h1>
        <p className="mt-2 text-sm text-[#4c576f]">Client ID: {clientId}</p>

        <div className="mt-6 rounded-2xl border border-[#c7d8f5] bg-[#f7faff] p-5">
          <p className="text-sm font-semibold text-[#0f172a]">Next implementation step</p>
          <p className="mt-1 text-sm text-[#4c576f]">
            Add client-specific WBR configuration details here (marketplace accounts, Windsor query params, and
            grouping mappings), then trigger ingest jobs.
          </p>
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/reports/wbr/setup"
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            Back to Setup
          </Link>
          <Link
            href="/reports/wbr"
            className="rounded-2xl bg-[#e8eefc] px-4 py-3 text-sm font-semibold text-[#0f172a] transition hover:bg-[#d7e1fb]"
          >
            Back to WBR
          </Link>
        </div>
      </div>
    </main>
  );
}
