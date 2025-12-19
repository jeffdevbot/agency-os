import Link from "next/link";
import { createSupabaseServiceClient } from "@/lib/supabase/serverClient";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type SearchParams = Record<string, string | string[] | undefined>;

type ClickupSyncRow = {
  entity_type: string;
  last_sync_at: string;
  last_sync_success: boolean;
  last_sync_error: string | null;
};

type AppErrorEvent = {
  id: string;
  occurred_at: string;
  tool: string | null;
  severity: string;
  message: string;
  route: string | null;
  method: string | null;
  status_code: number | null;
  request_id: string | null;
  user_id: string | null;
  user_email: string | null;
};

type ProfileRow = {
  id: string;
  email: string;
  full_name: string | null;
  display_name: string | null;
  is_admin: boolean;
  role: string;
  allowed_tools: string[];
  employment_status: string;
  bench_status: string;
  clickup_user_id: string | null;
  slack_user_id: string | null;
  updated_at: string;
};

const getParam = (params: SearchParams | undefined, key: string): string | undefined => {
  const raw = params?.[key];
  if (!raw) return undefined;
  return Array.isArray(raw) ? raw[0] : raw;
};

const sanitizeSearchQuery = (value: string): string => {
  // Keep this conservative because it becomes part of a PostgREST filter string.
  return value
    .trim()
    .replace(/\s+/g, " ")
    .replace(/[(),]/g, " ")
    .replace(/\s+/g, " ")
    .slice(0, 120);
};

const Card = (props: { title: string; children: React.ReactNode; right?: React.ReactNode }) => (
  <section className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
    <div className="flex flex-wrap items-baseline justify-between gap-3">
      <h2 className="text-lg font-semibold text-[#0f172a]">{props.title}</h2>
      {props.right ? <div className="text-sm text-[#4c576f]">{props.right}</div> : null}
    </div>
    <div className="mt-5">{props.children}</div>
  </section>
);

const Stat = (props: { label: string; value: React.ReactNode; hint?: string }) => (
  <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
    <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{props.label}</div>
    <div className="mt-2 text-2xl font-semibold text-[#0f172a]">{props.value}</div>
    {props.hint ? <div className="mt-1 text-xs text-slate-500">{props.hint}</div> : null}
  </div>
);

const formatDateTime = (value: string | null | undefined): string => {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString();
};

const pct = (num: number, den: number): string => {
  if (den <= 0) return "—";
  return `${Math.round((num / den) * 100)}%`;
};

export default async function CommandCenterAdminPage(props: { searchParams?: SearchParams }) {
  const toolFilter = getParam(props.searchParams, "tool")?.trim() || "";
  const qRaw = getParam(props.searchParams, "q")?.trim() || "";
  const q = sanitizeSearchQuery(qRaw);
  const userId = getParam(props.searchParams, "user")?.trim() || "";

  const supabase = createSupabaseServiceClient();

  // eslint-disable-next-line react-hooks/purity
  const now = Date.now();
  const since24h = new Date(now - 24 * 60 * 60 * 1000).toISOString();
  const since7d = new Date(now - 7 * 24 * 60 * 60 * 1000).toISOString();
  const queuedOlderThan15m = new Date(now - 15 * 60 * 1000).toISOString();

  const [
    scribeRecentJobs,
    scribeStaleQueuedCount,
    debriefStatusRows,
    clickupSyncRows,
    usageCounts,
    recentErrors,
    profileMatches,
    selectedProfile,
    selectedUserErrors,
  ] = await Promise.all([
    supabase
      .from("scribe_generation_jobs")
      .select("status, created_at")
      .gte("created_at", since24h),
    supabase
      .from("scribe_generation_jobs")
      .select("id", { count: "exact", head: true })
      .eq("status", "queued")
      .lt("created_at", queuedOlderThan15m),
    supabase.from("debrief_meeting_notes").select("status").neq("status", "dismissed"),
    supabase.from("clickup_sync_status").select("entity_type, last_sync_at, last_sync_success, last_sync_error"),
    Promise.all(
      ["ngram", "npat", "root", "adscope"].map(async (tool) => {
        const total = await supabase
          .from("usage_events")
          .select("id", { count: "exact", head: true })
          .gte("occurred_at", since7d)
          .eq("tool", tool);
        const errors = await supabase
          .from("usage_events")
          .select("id", { count: "exact", head: true })
          .gte("occurred_at", since7d)
          .eq("tool", tool)
          .eq("status", "error");
        return { tool, total: total.count ?? 0, errors: errors.count ?? 0 };
      }),
    ),
    toolFilter
      ? supabase
          .from("app_error_events")
          .select("id, occurred_at, tool, severity, message, route, method, status_code, request_id, user_id, user_email")
          .gte("occurred_at", since7d)
          .eq("tool", toolFilter)
          .order("occurred_at", { ascending: false })
          .limit(50)
      : supabase
          .from("app_error_events")
          .select("id, occurred_at, tool, severity, message, route, method, status_code, request_id, user_id, user_email")
          .gte("occurred_at", since7d)
          .order("occurred_at", { ascending: false })
          .limit(50),
    q
      ? supabase
          .from("profiles")
          .select(
            "id, email, full_name, display_name, is_admin, role, allowed_tools, employment_status, bench_status, clickup_user_id, slack_user_id, updated_at",
          )
          .or(`email.ilike.%${q}%,display_name.ilike.%${q}%,full_name.ilike.%${q}%`)
          .order("updated_at", { ascending: false })
          .limit(10)
      : Promise.resolve({ data: [] as ProfileRow[], error: null }),
    userId
      ? supabase
          .from("profiles")
          .select(
            "id, email, full_name, display_name, is_admin, role, allowed_tools, employment_status, bench_status, clickup_user_id, slack_user_id, updated_at",
          )
          .eq("id", userId)
          .single()
      : Promise.resolve({ data: null as ProfileRow | null, error: null }),
    userId
      ? supabase
          .from("app_error_events")
          .select("id, occurred_at, tool, severity, message, route, method, status_code, request_id, user_id, user_email")
          .gte("occurred_at", since7d)
          .eq("user_id", userId)
          .order("occurred_at", { ascending: false })
          .limit(30)
      : Promise.resolve({ data: [] as AppErrorEvent[], error: null }),
  ]);

  const scribeJobsByStatus = new Map<string, number>();
  for (const row of scribeRecentJobs.data ?? []) {
    const status = (row as { status?: string }).status ?? "unknown";
    scribeJobsByStatus.set(status, (scribeJobsByStatus.get(status) ?? 0) + 1);
  }

  const debriefByStatus = new Map<string, number>();
  for (const row of debriefStatusRows.data ?? []) {
    const status = (row as { status?: string }).status ?? "unknown";
    debriefByStatus.set(status, (debriefByStatus.get(status) ?? 0) + 1);
  }

  const clickupRows = (clickupSyncRows.data ?? []) as ClickupSyncRow[];
  const clickupFailures = clickupRows.filter((r) => !r.last_sync_success);

  const errorsData = (recentErrors.data ?? []) as AppErrorEvent[];
  const selectedErrorsData = (selectedUserErrors.data ?? []) as AppErrorEvent[];
  const profileMatchesData = (profileMatches.data ?? []) as ProfileRow[];
  const profileSearchError =
    q && profileMatches.error ? (profileMatches.error as unknown as { message?: string }).message : null;
  const selectedProfileError =
    userId && selectedProfile.error ? (selectedProfile.error as unknown as { message?: string }).message : null;

  const toolOptions = ["", "scribe", "debrief", "adscope", "ngram", "npat", "root", "clickup"];

  return (
    <main className="space-y-6">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <div className="flex flex-wrap items-baseline justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-[#0f172a]">Admin</h1>
            <p className="mt-2 text-sm text-[#4c576f]">
              System overview, recent errors, and user lookup. Read-only.
            </p>
          </div>
          <Link href="/command-center" className="text-sm font-semibold text-[#0a6fd6] hover:underline">
            Back to Command Center
          </Link>
        </div>
      </div>

      <Card title="System Overview" right={<span>Last 24h / Last 7d</span>}>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Stat
            label="Scribe Jobs (24h)"
            value={
              <div className="text-base font-semibold text-[#0f172a]">
                queued {scribeJobsByStatus.get("queued") ?? 0} · running {scribeJobsByStatus.get("running") ?? 0} ·
                succeeded {scribeJobsByStatus.get("succeeded") ?? 0} · failed {scribeJobsByStatus.get("failed") ?? 0}
              </div>
            }
            hint={`Queued >15m: ${scribeStaleQueuedCount.count ?? 0}`}
          />
          <Stat
            label="Debrief Backlog"
            value={
              <div className="text-base font-semibold text-[#0f172a]">
                pending {debriefByStatus.get("pending") ?? 0} · processing {debriefByStatus.get("processing") ?? 0} ·
                ready {debriefByStatus.get("ready") ?? 0} · failed {debriefByStatus.get("failed") ?? 0}
              </div>
            }
            hint="Excludes dismissed"
          />
          <Stat
            label="ClickUp Sync"
            value={
              <div className="text-base font-semibold text-[#0f172a]">
                {clickupFailures.length === 0 ? "Healthy" : `${clickupFailures.length} failing`}
              </div>
            }
            hint={
              clickupFailures.length > 0
                ? `Most recent failure: ${formatDateTime(clickupFailures[0]?.last_sync_at)}`
                : clickupRows.length > 0
                  ? `Last sync: ${formatDateTime(clickupRows[0]?.last_sync_at)}`
                  : "No sync rows"
            }
          />
        </div>

        <div className="mt-5 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Backend Tool Runs (7d)</div>
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-4">
            {usageCounts.map((row) => (
              <div key={row.tool} className="rounded-xl border border-slate-200 px-3 py-2">
                <div className="text-sm font-semibold text-[#0f172a]">{row.tool}</div>
                <div className="mt-1 text-xs text-slate-600">
                  runs: {row.total} · errors: {row.errors} · success: {pct(row.total - row.errors, row.total)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </Card>

      <Card
        title="Recent Errors"
        right={
          <form method="get" className="flex items-center gap-2">
            <label className="text-xs font-semibold text-slate-500" htmlFor="tool">
              Tool
            </label>
            <select
              id="tool"
              name="tool"
              defaultValue={toolFilter}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm"
            >
              {toolOptions.map((t) => (
                <option key={t || "all"} value={t}>
                  {t ? t : "All"}
                </option>
              ))}
            </select>
            {q ? <input type="hidden" name="q" value={q} /> : null}
            {userId ? <input type="hidden" name="user" value={userId} /> : null}
            <button
              type="submit"
              className="rounded-xl bg-[#0a6fd6] px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-[#075bb1]"
            >
              Filter
            </button>
          </form>
        }
      >
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-600">
              <tr>
                <th className="px-4 py-3">Time</th>
                <th className="px-4 py-3">Tool</th>
                <th className="px-4 py-3">Route</th>
                <th className="px-4 py-3">Message</th>
                <th className="px-4 py-3">User</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {errorsData.length === 0 ? (
                <tr>
                  <td className="px-4 py-6 text-slate-500" colSpan={5}>
                    No errors recorded in the last 7 days.
                  </td>
                </tr>
              ) : (
                errorsData.map((e) => (
                  <tr key={e.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 text-slate-600">{formatDateTime(e.occurred_at)}</td>
                    <td className="px-4 py-3 text-slate-700">{e.tool ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-700">
                      <div className="font-mono text-xs text-slate-600">
                        {(e.method ?? "").toUpperCase()} {e.route ?? "—"}
                      </div>
                      <div className="text-xs text-slate-500">
                        {e.status_code ? `HTTP ${e.status_code}` : ""}{" "}
                        {e.request_id ? `· ${e.request_id}` : ""}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-700">{e.message}</td>
                    <td className="px-4 py-3 text-slate-700">
                      {e.user_email && e.user_id ? (
                        <Link
                          className="text-[#0a6fd6] hover:underline"
                          href={`/command-center/admin?user=${encodeURIComponent(e.user_id ?? "")}`}
                        >
                          {e.user_email}
                        </Link>
                      ) : e.user_email ? e.user_email : "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <div className="mt-3 text-xs text-slate-500">Showing last 7 days · max 50 rows</div>
      </Card>

      <Card title="User Lookup">
        <form method="get" className="flex flex-wrap items-end gap-3">
          <div className="min-w-[260px] flex-1">
            <label className="text-xs font-semibold text-slate-500" htmlFor="q">
              Search by email or name
            </label>
            <input
              id="q"
              name="q"
              defaultValue={q}
              placeholder="e.g. jeff@… or Jeff"
              className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 shadow-sm"
            />
          </div>
          {toolFilter ? <input type="hidden" name="tool" value={toolFilter} /> : null}
          <button
            type="submit"
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            Search
          </button>
        </form>

        {profileSearchError ? (
          <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            User search error: {profileSearchError}
          </div>
        ) : q ? (
          <div className="mt-4 text-sm text-slate-600">
            Results for “{q}”: {profileMatchesData.length}
          </div>
        ) : (
          <div className="mt-4 text-sm text-slate-600">Search to find a user, then click to view details.</div>
        )}

        {profileMatchesData.length > 0 ? (
          <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2">
            {profileMatchesData.map((p) => (
              <Link
                key={p.id}
                href={`/command-center/admin?user=${encodeURIComponent(p.id)}${toolFilter ? `&tool=${encodeURIComponent(toolFilter)}` : ""}`}
                className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg"
              >
                <div className="text-sm font-semibold text-[#0f172a]">{p.email}</div>
                <div className="mt-1 text-xs text-slate-600">
                  {p.display_name || p.full_name || "—"} · {p.is_admin ? "admin" : p.role} · {p.employment_status} ·{" "}
                  {p.bench_status}
                </div>
              </Link>
            ))}
          </div>
        ) : null}

        {selectedProfile.data ? (
          <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-[#0f172a]">{selectedProfile.data.email}</div>
                <div className="mt-1 text-xs text-slate-600">
                  {selectedProfile.data.display_name || selectedProfile.data.full_name || "—"} ·{" "}
                  {selectedProfile.data.is_admin ? "admin" : selectedProfile.data.role} ·{" "}
                  {selectedProfile.data.employment_status} · {selectedProfile.data.bench_status}
                </div>
              </div>
              <div className="text-xs text-slate-500">Updated: {formatDateTime(selectedProfile.data.updated_at)}</div>
            </div>

            <div className="mt-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Recent Errors (7d)</div>
              <div className="mt-3 space-y-2">
                {selectedErrorsData.length === 0 ? (
                  <div className="text-sm text-slate-600">No errors recorded for this user.</div>
                ) : (
                  selectedErrorsData.map((e) => (
                    <div key={e.id} className="rounded-xl border border-slate-200 px-3 py-2">
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <div className="text-xs text-slate-500">
                          {formatDateTime(e.occurred_at)} · {e.tool ?? "—"} · {(e.method ?? "").toUpperCase()}{" "}
                          {e.route ?? "—"}
                        </div>
                        <div className="text-xs text-slate-500">{e.status_code ? `HTTP ${e.status_code}` : ""}</div>
                      </div>
                      <div className="mt-1 text-sm text-slate-700">{e.message}</div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        ) : selectedProfileError ? (
          <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            User details error: {selectedProfileError}
          </div>
        ) : null}
      </Card>
    </main>
  );
}
