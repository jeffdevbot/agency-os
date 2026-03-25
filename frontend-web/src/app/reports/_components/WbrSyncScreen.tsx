"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { useResolvedWbrProfile } from "../_lib/useResolvedWbrProfile";
import { useWbrSync } from "../_lib/useWbrSync";
import { updateWbrProfile } from "../wbr/_lib/wbrApi";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";

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

const formatDateLabel = (value: string): string => {
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "short",
    day: "2-digit",
  }).format(parsed);
};

const formatDateRangeLabel = (dateFrom: string, dateTo: string): string => {
  if (dateFrom === dateTo) return formatDateLabel(dateFrom);
  return `${formatDateLabel(dateFrom)} to ${formatDateLabel(dateTo)}`;
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
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [toggleSaving, setToggleSaving] = useState(false);
  const [toggleMessage, setToggleMessage] = useState<string | null>(null);
  const [toggleError, setToggleError] = useState<string | null>(null);

  const handleToggleNightlySync = useCallback(async () => {
    if (!resolved.profile?.id) return;
    setToggleSaving(true);
    setToggleError(null);
    setToggleMessage(null);
    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.access_token) {
        throw new Error("Please sign in again.");
      }
      const nextEnabled = !resolved.profile.sp_api_auto_sync_enabled;
      await updateWbrProfile(session.access_token, resolved.profile.id, {
        sp_api_auto_sync_enabled: nextEnabled,
      });
      await resolved.loadRoute();
      setToggleMessage(nextEnabled ? "Nightly SP-API sync enabled." : "Nightly SP-API sync disabled.");
    } catch (error) {
      setToggleError(error instanceof Error ? error.message : "Failed to update nightly SP-API sync");
    } finally {
      setToggleSaving(false);
    }
  }, [resolved, supabase]);

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
          {resolved.summary.client.name} {resolved.profile.marketplace_code} SP-API Sync
        </h1>
        <p className="mt-2 text-sm text-[#4c576f]">
          Backfill business data via Windsor.ai and control the nightly trailing-window refresh for this profile.
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
            href={`/reports/${clientSlug}/${normalizedMarketplace}/wbr/sync`}
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            Sync Sources
          </Link>
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
            Save a Windsor account id in Settings before running SP-API sync.
          </p>
        ) : null}

        {toggleError ? (
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {toggleError}
          </p>
        ) : null}

        {sync.errorMessage ? (
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {sync.errorMessage}
          </p>
        ) : null}

        {toggleMessage ? (
          <p className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            {toggleMessage}
          </p>
        ) : null}

        {sync.successMessage ? (
          <p className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            {sync.successMessage}
          </p>
        ) : null}

        <div className="mt-6 rounded-2xl border border-slate-200 bg-[#f8fbff] p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-[#0f172a]">Coverage Check</p>
              <p className="mt-1 text-sm text-[#4c576f]">
                {sync.coverage
                  ? `${sync.coverage.window_label}: ${sync.coverage.window_start} to ${sync.coverage.window_end}`
                  : "Recent SP-API coverage and missing date ranges for this profile."}
              </p>
            </div>
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <div className="rounded-2xl border border-slate-200 bg-white p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Covered Days</p>
              <p className="mt-2 text-2xl font-semibold text-[#0f172a]">{sync.coverage?.covered_day_count ?? 0}</p>
            </div>
            <div className="rounded-2xl border border-sky-200 bg-sky-50/70 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-sky-800">In Flight</p>
              <p className="mt-2 text-2xl font-semibold text-sky-900">{sync.coverage?.in_flight_day_count ?? 0}</p>
            </div>
            <div className="rounded-2xl border border-amber-200 bg-amber-50/70 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-[#92400e]">Missing Days</p>
              <p className="mt-2 text-2xl font-semibold text-[#92400e]">{sync.coverage?.missing_day_count ?? 0}</p>
            </div>
          </div>

          {sync.loadingRuns ? (
            <p className="mt-4 text-sm text-[#64748b]">Loading coverage…</p>
          ) : sync.coverage && sync.coverage.missing_ranges.length > 0 ? (
            <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50/70 p-4">
              <p className="text-sm font-semibold text-[#92400e]">Missing SP-API date ranges</p>
              <p className="mt-1 text-sm text-[#78350f]">
                This gap check is intentionally bounded so it stays actionable instead of listing years of history.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {sync.coverage.missing_ranges.slice(0, 8).map((range) => (
                  <span
                    key={`${range.date_from}:${range.date_to}`}
                    className="inline-flex rounded-full border border-amber-200 bg-white px-3 py-1 text-xs font-medium text-[#78350f]"
                  >
                    {formatDateRangeLabel(range.date_from, range.date_to)}
                  </span>
                ))}
                {sync.coverage.missing_ranges.length > 8 ? (
                  <span className="inline-flex rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-[#4c576f]">
                    +{sync.coverage.missing_ranges.length - 8} more
                  </span>
                ) : null}
              </div>
            </div>
          ) : sync.coverage ? (
            <p className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
              No missing dates inside the current SP-API coverage window.
            </p>
          ) : null}

          {!sync.loadingRuns && sync.coverage && sync.coverage.in_flight_ranges.length > 0 ? (
            <div className="mt-4 rounded-2xl border border-sky-200 bg-sky-50/70 p-4">
              <p className="text-sm font-semibold text-sky-900">Runs still processing</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {sync.coverage.in_flight_ranges.map((range) => (
                  <span
                    key={`${range.date_from}:${range.date_to}`}
                    className="inline-flex rounded-full border border-sky-200 bg-white px-3 py-1 text-xs font-medium text-sky-900"
                  >
                    {formatDateRangeLabel(range.date_from, range.date_to)}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-sm font-semibold text-[#0f172a]">Historical Backfill</p>
            <p className="mt-1 text-sm text-[#4c576f]">
              Run business-data sync across a custom range. The backend processes this in chunked date windows.
            </p>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <label className="text-sm">
                <span className="mb-1 block font-semibold text-[#0f172a]">Start Date</span>
                <input
                  type="date"
                  value={sync.backfillStartDate}
                  max={sync.todayIso}
                  onChange={(event) => sync.setBackfillStartDate(event.target.value)}
                  className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
                />
              </label>
              <label className="text-sm">
                <span className="mb-1 block font-semibold text-[#0f172a]">End Date</span>
                <input
                  type="date"
                  value={sync.backfillEndDate}
                  max={sync.todayIso}
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
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-[#0f172a]">Nightly Refresh</p>
              <span
                className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${
                  resolved.profile.sp_api_auto_sync_enabled
                    ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                    : "border-slate-200 bg-slate-50 text-slate-700"
                }`}
              >
                {resolved.profile.sp_api_auto_sync_enabled ? "Enabled" : "Disabled"}
              </span>
            </div>
            <p className="mt-1 text-sm text-[#4c576f]">
              When enabled, `worker-sync` rewrites the trailing {resolved.profile.daily_rewrite_days}-day SP-API window every night to catch late business-data changes.
            </p>
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                onClick={() => void handleToggleNightlySync()}
                disabled={
                  (!resolved.profile.windsor_account_id && !resolved.profile.sp_api_auto_sync_enabled) ||
                  toggleSaving ||
                  sync.runningBackfill ||
                  sync.runningDailyRefresh
                }
                className="rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-[#b7cbea]"
              >
                {toggleSaving
                  ? "Saving..."
                  : resolved.profile.sp_api_auto_sync_enabled
                    ? "Disable Nightly Sync"
                    : "Enable Nightly Sync"}
              </button>
              <button
                onClick={() => void sync.handleRunDailyRefresh()}
                disabled={!resolved.profile.windsor_account_id || toggleSaving || sync.runningBackfill || sync.runningDailyRefresh}
                className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
              >
                {sync.runningDailyRefresh ? "Running Manual Refresh..." : "Run Manual Refresh"}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <p className="text-sm font-semibold text-[#0f172a]">Recent Business Data Runs</p>
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
                    No SP-API sync runs yet.
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

      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <p className="text-sm font-semibold text-[#0f172a]">Section 3 Sync Runs (Inventory + Returns)</p>
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-[#f7faff]">
              <tr className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">
                <th className="px-3 py-2">Started</th>
                <th className="px-3 py-2">Source</th>
                <th className="px-3 py-2">Job</th>
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
                    Loading...
                  </td>
                </tr>
              ) : sync.section3Runs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-3 py-4 text-[#64748b]">
                    No Section 3 sync runs yet.
                  </td>
                </tr>
              ) : (
                sync.section3Runs.map((run) => (
                  <tr key={run.id} className="hover:bg-slate-50">
                    <td className="px-3 py-2 text-[#0f172a]">{formatTimestamp(run.started_at ?? run.created_at)}</td>
                    <td className="px-3 py-2 text-[#0f172a]">{run.source_type.replace("windsor_", "")}</td>
                    <td className="px-3 py-2 text-[#0f172a]">{run.job_type}</td>
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
