"use client";

import Link from "next/link";

type Props = {
  clientSlug: string;
  marketplaceCode: string;
};

export default function WbrSyncStub({ clientSlug, marketplaceCode }: Props) {
  return (
    <main className="space-y-4">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-2xl font-semibold text-[#0f172a]">WBR Sync</h1>
        <p className="mt-2 text-sm text-[#4c576f]">
          Historical backfill and daily sync controls will live here. This route exists now so the navigation model is stable before the sync engine lands.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href={`/reports/${clientSlug}/${marketplaceCode}/wbr`}
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            Back to WBR
          </Link>
          <Link
            href={`/reports/${clientSlug}/${marketplaceCode}/wbr/settings`}
            className="rounded-2xl bg-[#e8eefc] px-4 py-3 text-sm font-semibold text-[#0f172a] transition hover:bg-[#d7e1fb]"
          >
            Open Settings
          </Link>
        </div>

        <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-5">
          <p className="text-sm font-semibold text-[#0f172a]">Planned Controls</p>
          <ul className="mt-2 list-disc pl-5 text-sm text-[#4c576f]">
            <li>Backfill from a chosen start date in 7-day chunks</li>
            <li>Run history and current chunk status</li>
            <li>Daily sync status and rewrite window visibility</li>
          </ul>
        </div>
      </div>
    </main>
  );
}
