"use client";

import Link from "next/link";
import { useResolvedWbrProfile } from "../_lib/useResolvedWbrProfile";
import { useWbrSync } from "../_lib/useWbrSync";

type Props = {
  clientSlug: string;
  marketplaceCode: string;
};

const formatTimestamp = (value: string | null): string => {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "numeric",
    minute: "2-digit",
  }).format(parsed);
};

const statusClasses = {
  running: "border-sky-200 bg-sky-50 text-sky-800",
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  error: "border-rose-200 bg-rose-50 text-rose-800",
};

export default function WbrSyncScreen({ clientSlug, marketplaceCode }: Props) {
  const resolved = useResolvedWbrProfile(clientSlug, marketplaceCode);
  const sync = useWbrSync(resolved.profile);
  const normalizedMarketplace = marketplaceCode.toLowerCase();

  if (resolved.loading) {
    return (
      <main className="space-y-4">
        <div className="rounded-3xl bg-white/95 p-8 text-sm text-[#64748b] shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          Loading WBR sync...
        </div>
      </main>
    );
  }

  if (!resolved.profile || !resolved.summary) {
    return (
      <main className="space-y-4">
        <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          <h1 className="text-2xl font-semibold text-[#0f172a]">WBR Sync</h1>
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {resolved.errorMessage ?? "Unable to resolve WBR profile"}
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="space-y-4">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-2xl font-semibold text-[#0f172a]">
          {resolved.summary.client.name} {resolved.profile.marketplace_code} WBR Sync
        </h1>
        <p className="mt-2 text-sm text-[#4c576f]">
          Backfill Windsor business data in chunks or run the daily rewrite window refresh for this profile.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            onClick={() => void sync.loadRuns(true)}
            disabled={sync.loadingRuns || sync.refreshingRuns || sync.runningBackfill || sync.runningDailyRefresh}
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
          >
            {sync.refreshingRuns ? "Refreshing..." : "Refresh Runs"}
          </button>
          <Link
            href={`/reports/${clientSlug}/${normalizedMarketplace}/wbr`}
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            Back to WBR
          </Link>
          <Link
            href={`/reports/${clientSlug}/${normalizedMarketplace}/wbr/settings`}
            className="rounded-2xl bg-[#e8eefc] px-4 py-3 text-sm font-semibold text-[#0f172a] transition hover:bg-[#d7e1fb]"
          >
            Settings
          </Link>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Windsor Account</p>
            <p className="mt-2 text-sm font-semibold text-[#0f172a]">
              {resolved.profile.windsor_account_id ?? "—"}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Week Start</p>
            <p className="mt-2 text-sm font-semibold text-[#0f172a] capitalize">{resolved.profile.week_start_day}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Daily Rewrite Days</p>
            <p className="mt-2 text-sm font-semibold text-[#0f172a]">{resolved.profile.daily_rewrite_days}</p>
          </div>
        </div>

        {!resolved.profile.windsor_account_id ? (
          <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            Save a Windsor account id in Settings before running Section 1 sync.
          </p>
        ) : null}

        {sync.errorMessage ? (
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {sync.errorMessage}
          </p>
        ) : null}

        {sync.successMessage ? (
          <p className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            {sync.successMessage}
          </p>
        ) : null}

        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-sm font-semibold text-[#0f172a]">Historical Backfill</p>
            <p className="mt-1 text-sm text-[#4c576f]">
              Run Windsor business sync across a custom range. The backend processes this in chunked date windows.
            </p>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <label className="text-sm">
                <span className="mb-1 block font-semibold text-[#0f172a]">Start Date</span>
                <input
                  type="date"
                  value={sync.backfillStartDate}
                  onChange={(event) => sync.setBackfillStartDate(event.target.value)}
                  className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
                />
              </label>
              <label className="text-sm">
                <span className="mb-1 block font-semibold text-[#0f172a]">End Date</span>
                <input
                  type="date"
                  value={sync.backfillEndDate}
                  onChange={(event) => sync.setBackfillEndDate(event.target.value)}
                  className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
                />
              </label>
              <label className="text-sm">
                <span className="mb-1 block font-semibold text-[#0f172a]">Chunk Days</span>
                <input
                  type="number"
                  min={1}
                  max={31}
                  value={sync.chunkDays}
                  onChange={(event) => sync.setChunkDays(event.target.value)}
                  className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
                />
              </label>
            </div>
            <button
              onClick={() => void sync.handleRunBackfill()}
              disabled={!resolved.profile.windsor_account_id || sync.runningBackfill || sync.runningDailyRefresh}
              className="mt-4 rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-[#b7cbea]"
            >
              {sync.runningBackfill ? "Running Backfill..." : "Run Backfill"}
            </button>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-sm font-semibold text-[#0f172a]">Daily Refresh</p>
            <p className="mt-1 text-sm text-[#4c576f]">
              Rewrite the profile&apos;s trailing {resolved.profile.daily_rewrite_days}-day Windsor window to catch late business-data changes.
            </p>
            <button
              onClick={() => void sync.handleRunDailyRefresh()}
              disabled={!resolved.profile.windsor_account_id || sync.runningBackfill || sync.runningDailyRefresh}
              className="mt-4 rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-[#b7cbea]"
            >
              {sync.runningDailyRefresh ? "Running Daily Refresh..." : "Run Daily Refresh"}
            </button>
          </div>
        </div>
      </div>

      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <p className="text-sm font-semibold text-[#0f172a]">Recent Runs</p>
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-[#f7faff]">
              <tr className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">
                <th className="px-3 py-2">Started</th>
                <th className="px-3 py-2">Job</th>
                <th className="px-3 py-2">Window</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Rows Fetched</th>
                <th className="px-3 py-2">Rows Loaded</th>
                <th className="px-3 py-2">Error</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white">
              {sync.loadingRuns ? (
                <tr>
                  <td colSpan={7} className="px-3 py-4 text-[#64748b]">
                    Loading sync runs...
                  </td>
                </tr>
              ) : sync.runs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-3 py-4 text-[#64748b]">
                    No Windsor business sync runs yet.
                  </td>
                </tr>
              ) : (
                sync.runs.map((run) => (
                  <tr key={run.id} className="hover:bg-slate-50">
                    <td className="px-3 py-2 text-[#0f172a]">{formatTimestamp(run.started_at)}</td>
                    <td className="px-3 py-2 text-[#0f172a]">{run.job_type}</td>
                    <td className="px-3 py-2 text-[#4c576f]">
                      {run.date_from ?? "—"} to {run.date_to ?? "—"}
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={`inline-flex rounded-full border px-2 py-1 text-xs font-semibold ${statusClasses[run.status]}`}
                      >
                        {run.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-[#0f172a]">{run.rows_fetched}</td>
                    <td className="px-3 py-2 text-[#0f172a]">{run.rows_loaded}</td>
                    <td className="px-3 py-2 text-[#64748b]">{run.error_message ?? "—"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
