"use client";

import Link from "next/link";
import { useDeferredValue, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import {
  getTeamHoursReport,
  type TeamHoursClient,
  type TeamHoursDailySegment,
  type TeamHoursMember,
  type TeamHoursReport,
  type TeamHoursSeries,
  type TeamHoursSummary,
  type TeamHoursUnmappedSpace,
  type TeamHoursUnmappedUser,
} from "@/lib/api/admin/teamHours";

const DAY_MS = 24 * 60 * 60 * 1000;
const CHART_COLORS = [
  "#0a6fd6",
  "#0f766e",
  "#f59e0b",
  "#7c3aed",
  "#ef4444",
  "#0891b2",
  "#84cc16",
  "#f97316",
  "#14b8a6",
  "#64748b",
  "#ec4899",
  "#8b5cf6",
];

type ViewMode = "team_members" | "clients";

type ChartRow = {
  date: string;
  label: string;
  total_hours: number;
  __segments: TeamHoursDailySegment[];
  [key: string]: string | number | TeamHoursDailySegment[];
};

const formatDateInput = (date: Date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const defaultDateRange = () => {
  const end = new Date();
  const start = new Date(end.getTime() - 29 * DAY_MS);
  return {
    startDate: formatDateInput(start),
    endDate: formatDateInput(end),
  };
};

const formatHours = (value: number) => `${value.toFixed(2)}h`;

const formatShortDate = (value: string) => {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
  }).format(date);
};

const formatLongDate = (value: string) => {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
};

const startOfDayMs = (value: string) => new Date(`${value}T00:00:00`).getTime();

const endOfDayMs = (value: string) => new Date(`${value}T23:59:59.999`).getTime();

const safeColor = (index: number) => CHART_COLORS[index % CHART_COLORS.length];

const matchesSearch = (
  query: string,
  values: Array<string | number | null | undefined>,
) => {
  if (!query) return true;
  return values.some((value) =>
    String(value ?? "").toLowerCase().includes(query),
  );
};

function SummaryCard({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "default" | "warn";
}) {
  const classes =
    tone === "warn"
      ? "border-amber-200 bg-amber-50 text-amber-950"
      : "border-slate-200 bg-white text-slate-950";
  return (
    <div className={`rounded-3xl border p-5 shadow-sm ${classes}`}>
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
      {hint ? <p className="mt-2 text-sm text-slate-500">{hint}</p> : null}
    </div>
  );
}

function LinkStatusBadge({ status }: { status: TeamHoursMember["link_status"] }) {
  if (status === "linked") {
    return <span className="inline-flex rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-800">Linked</span>;
  }
  if (status === "ambiguous") {
    return <span className="inline-flex rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-800">Duplicate ClickUp ID</span>;
  }
  return <span className="inline-flex rounded-full bg-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-700">Needs ClickUp ID</span>;
}

function ClientStatusBadge({ status }: { status: string }) {
  if (status === "archived") {
    return <span className="inline-flex rounded-full bg-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-700">Archived</span>;
  }
  if (status === "inactive") {
    return <span className="inline-flex rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-800">Inactive</span>;
  }
  return <span className="inline-flex rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-800">Active</span>;
}

function ChartTooltip({
  active,
  payload,
  label,
  colorByKey,
}: {
  active?: boolean;
  payload?: Array<{ payload: ChartRow }>;
  label?: string;
  colorByKey: Map<string, string>;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;

  return (
    <div className="min-w-[240px] rounded-2xl border border-slate-200 bg-white p-4 shadow-xl">
      <p className="text-sm font-semibold text-slate-900">{formatLongDate(label ?? row.date)}</p>
      <p className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-500">Total {formatHours(row.total_hours)}</p>
      <div className="mt-3 space-y-2">
        {row.__segments.length === 0 ? (
          <p className="text-sm text-slate-500">No hours logged.</p>
        ) : (
          row.__segments.map((segment) => (
            <div key={segment.key} className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span
                    className="mt-1 h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: colorByKey.get(segment.key) ?? "#64748b" }}
                  />
                  <p className="truncate text-sm font-medium text-slate-800">{segment.label}</p>
                </div>
                {segment.brand_name ? (
                  <p className="pl-4 text-xs text-slate-500">{segment.brand_name}</p>
                ) : null}
              </div>
              <p className="text-sm font-semibold text-slate-900">{formatHours(segment.hours)}</p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function SeriesBreakdown({
  title,
  rows,
  colorByKey,
  emptyMessage,
}: {
  title: string;
  rows: TeamHoursSeries[];
  colorByKey: Map<string, string>;
  emptyMessage: string;
}) {
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">{title}</h3>
      {rows.length === 0 ? (
        <p className="mt-4 text-sm text-slate-500">{emptyMessage}</p>
      ) : (
        <div className="mt-4 space-y-3">
          {rows.map((row) => (
            <div key={row.key} className="flex items-start justify-between gap-4 rounded-2xl bg-slate-50 px-4 py-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: colorByKey.get(row.key) ?? "#64748b" }}
                  />
                  <p className="truncate font-medium text-slate-900">{row.label}</p>
                </div>
                {row.team_member_email ? (
                  <p className="pl-4 text-xs text-slate-500">{row.team_member_email}</p>
                ) : null}
                {row.client_name && row.brand_name ? (
                  <p className="pl-4 text-xs text-slate-500">{row.client_name} / {row.brand_name}</p>
                ) : null}
                {row.client_name && !row.brand_name && row.label !== row.client_name ? (
                  <p className="pl-4 text-xs text-slate-500">{row.client_name}</p>
                ) : null}
              </div>
              <p className="text-sm font-semibold text-slate-900">{formatHours(row.total_hours)}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DriftCard({
  title,
  rows,
  emptyMessage,
}: {
  title: string;
  rows: Array<{ key: string; name: string; detail: string; hours: number }>;
  emptyMessage: string;
}) {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      {rows.length === 0 ? (
        <p className="mt-4 text-sm text-slate-500">{emptyMessage}</p>
      ) : (
        <div className="mt-4 space-y-3">
          {rows.map((row) => (
            <div key={row.key} className="flex items-start justify-between gap-4 rounded-2xl bg-slate-50 px-4 py-3">
              <div className="min-w-0">
                <p className="font-medium text-slate-900">{row.name}</p>
                <p className="truncate text-sm text-slate-500">{row.detail}</p>
              </div>
              <p className="text-sm font-semibold text-slate-900">{formatHours(row.hours)}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export default function CommandCenterHoursPage() {
  const defaults = defaultDateRange();
  const [token, setToken] = useState<string | null>(null);
  const [startDate, setStartDate] = useState(defaults.startDate);
  const [endDate, setEndDate] = useState(defaults.endDate);
  const [viewMode, setViewMode] = useState<ViewMode>("team_members");
  const [searchQuery, setSearchQuery] = useState("");
  const [report, setReport] = useState<TeamHoursReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [selectedMemberId, setSelectedMemberId] = useState<string | null>(null);
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null);
  const deferredSearchQuery = useDeferredValue(searchQuery.trim().toLowerCase());

  useEffect(() => {
    const supabase = getBrowserSupabaseClient();
    supabase.auth.getSession().then(({ data }: { data: { session: { access_token: string } | null } }) => {
      setToken(data.session?.access_token ?? null);
    });
  }, []);

  useEffect(() => {
    if (!token) return;

    const startDateMs = startOfDayMs(startDate);
    const endDateMs = endOfDayMs(endDate);
    if (Number.isNaN(startDateMs) || Number.isNaN(endDateMs)) {
      setReport(null);
      setLoading(false);
      setErrorMessage("Choose a valid start and end date.");
      return;
    }
    if (startDateMs > endDateMs) {
      setReport(null);
      setLoading(false);
      setErrorMessage("Start date must be on or before end date.");
      return;
    }

    let cancelled = false;
    setLoading(true);
    setErrorMessage(null);

    getTeamHoursReport(token, { startDateMs, endDateMs })
      .then((data) => {
        if (cancelled) return;
        setReport(data);
        setLoading(false);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setReport(null);
        setLoading(false);
        setErrorMessage(error instanceof Error ? error.message : "Unable to load Team Hours");
      });

    return () => {
      cancelled = true;
    };
  }, [token, startDate, endDate]);

  const summary: TeamHoursSummary | null = report?.summary ?? null;

  const filteredMembers = useMemo(() => {
    return (report?.team_members ?? []).filter((member) =>
      matchesSearch(deferredSearchQuery, [
        member.team_member_name,
        member.team_member_email,
        member.clickup_user_id,
        member.link_status,
      ]),
    );
  }, [deferredSearchQuery, report?.team_members]);

  const filteredClients = useMemo(() => {
    return (report?.clients ?? []).filter((client) =>
      matchesSearch(deferredSearchQuery, [
        client.client_name,
        client.status,
      ]),
    );
  }, [deferredSearchQuery, report?.clients]);

  useEffect(() => {
    if (viewMode !== "team_members") return;
    if (filteredMembers.length === 0) {
      setSelectedMemberId(null);
      return;
    }
    const stillVisible = filteredMembers.some((member) => member.entity_id === selectedMemberId);
    if (stillVisible) return;
    setSelectedMemberId(
      filteredMembers.find((member) => member.total_hours > 0)?.entity_id ?? filteredMembers[0].entity_id,
    );
  }, [filteredMembers, selectedMemberId, viewMode]);

  useEffect(() => {
    if (viewMode !== "clients") return;
    if (filteredClients.length === 0) {
      setSelectedClientId(null);
      return;
    }
    const stillVisible = filteredClients.some((client) => client.entity_id === selectedClientId);
    if (stillVisible) return;
    setSelectedClientId(
      filteredClients.find((client) => client.total_hours > 0)?.entity_id ?? filteredClients[0].entity_id,
    );
  }, [filteredClients, selectedClientId, viewMode]);

  const selectedMember = useMemo(
    () => filteredMembers.find((member) => member.entity_id === selectedMemberId) ?? null,
    [filteredMembers, selectedMemberId],
  );
  const selectedClient = useMemo(
    () => filteredClients.find((client) => client.entity_id === selectedClientId) ?? null,
    [filteredClients, selectedClientId],
  );

  const selectedEntity = viewMode === "team_members" ? selectedMember : selectedClient;
  const chartSeries = selectedEntity?.series ?? [];

  const colorByKey = useMemo(() => {
    return new Map(chartSeries.map((series, index) => [series.key, safeColor(index)]));
  }, [chartSeries]);

  const chartData = useMemo(() => {
    if (!report || !selectedEntity) return [];
    const dailyMap = new Map(selectedEntity.daily.map((day) => [day.date, day]));
    return report.date_range.days.map((date) => {
      const row: ChartRow = {
        date,
        label: formatShortDate(date),
        total_hours: 0,
        __segments: [],
      };
      for (const series of chartSeries) {
        row[series.key] = 0;
      }
      const day = dailyMap.get(date);
      if (!day) return row;
      row.total_hours = day.total_hours;
      row.__segments = day.segments;
      for (const segment of day.segments) {
        row[segment.key] = segment.hours;
      }
      return row;
    });
  }, [chartSeries, report, selectedEntity]);

  const hasChartHours = chartData.some((row) => row.total_hours > 0);

  const unmappedUserRows = useMemo(
    () =>
      (report?.unmapped_users ?? []).map((user: TeamHoursUnmappedUser) => ({
        key: user.clickup_user_id ?? user.clickup_username ?? "unknown-user",
        name: user.clickup_username ?? "Unlinked ClickUp User",
        detail:
          user.clickup_user_email && user.clickup_user_id
            ? `${user.clickup_user_email} | ClickUp ID: ${user.clickup_user_id}`
            : user.clickup_user_email
              ? user.clickup_user_email
              : user.clickup_user_id
                ? `ClickUp ID: ${user.clickup_user_id}`
                : "No email or ClickUp user id",
        hours: user.total_hours,
      })),
    [report?.unmapped_users],
  );

  const unmappedSpaceRows = useMemo(
    () =>
      (report?.unmapped_spaces ?? []).map((space: TeamHoursUnmappedSpace) => ({
        key: space.space_id ?? space.list_id ?? "unknown-space",
        name: space.space_name,
        detail: `space_id=${space.space_id ?? "—"} | list_id=${space.list_id ?? "—"}`,
        hours: space.total_hours,
      })),
    [report?.unmapped_spaces],
  );

  return (
    <main className="space-y-6">
      <section className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Link href="/command-center" className="text-sm font-semibold text-[#0a6fd6]">
              Back to Command Center
            </Link>
            <h1 className="mt-3 text-3xl font-semibold text-slate-900">Team Hours</h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-600">
              Review who is logging time and where it lands. Team-member view stacks daily hours by client or brand. Client view stacks daily hours by team member, with brand splits preserved when they matter.
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
            {report ? `${formatLongDate(startDate)} to ${formatLongDate(endDate)}` : "Select a date range"}
          </div>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <label className="space-y-2">
            <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Start Date</span>
            <input
              type="date"
              value={startDate}
              onChange={(event) => setStartDate(event.target.value)}
              className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900"
            />
          </label>
          <label className="space-y-2">
            <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">End Date</span>
            <input
              type="date"
              value={endDate}
              onChange={(event) => setEndDate(event.target.value)}
              className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900"
            />
          </label>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-2">
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setViewMode("team_members")}
                className={`rounded-2xl px-4 py-3 text-sm font-semibold transition ${
                  viewMode === "team_members"
                    ? "bg-[#0a6fd6] text-white shadow"
                    : "bg-white text-slate-700"
                }`}
              >
                Team Members
              </button>
              <button
                type="button"
                onClick={() => setViewMode("clients")}
                className={`rounded-2xl px-4 py-3 text-sm font-semibold transition ${
                  viewMode === "clients"
                    ? "bg-[#0a6fd6] text-white shadow"
                    : "bg-white text-slate-700"
                }`}
              >
                Clients
              </button>
            </div>
          </div>
          <label className="space-y-2">
            <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Search {viewMode === "team_members" ? "Team Members" : "Clients"}
            </span>
            <input
              type="text"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder={viewMode === "team_members" ? "Search name, email, or ClickUp ID" : "Search client name"}
              className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900"
            />
          </label>
        </div>
      </section>

      {errorMessage ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {errorMessage}
        </div>
      ) : null}

      {loading ? (
        <div className="rounded-3xl border border-dashed border-slate-300 bg-white/80 p-8 text-sm text-slate-500">
          Loading Team Hours…
        </div>
      ) : null}

      {!loading && summary ? (
        <>
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <SummaryCard label="Total Hours" value={formatHours(summary.total_hours)} />
            <SummaryCard
              label="Team Logging"
              value={`${summary.team_members_with_hours}/${summary.team_member_count}`}
              hint="People with any logged hours in range"
            />
            <SummaryCard
              label="Client Coverage"
              value={`${summary.clients_with_hours}/${summary.client_count}`}
              hint="Clients with any logged hours in range"
            />
            <SummaryCard
              label="Unattributed Hours"
              value={formatHours(summary.unattributed_hours)}
              hint="Hours on spaces that still need client mapping"
              tone="warn"
            />
          </section>

          <section className="grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
            <aside className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-end justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                    {viewMode === "team_members" ? "Team Members" : "Clients"}
                  </p>
                  <h2 className="mt-2 text-xl font-semibold text-slate-900">
                    {viewMode === "team_members" ? filteredMembers.length : filteredClients.length} visible
                  </h2>
                </div>
                <div className="text-sm text-slate-500">
                  {viewMode === "team_members"
                    ? `${summary.team_member_count} total`
                    : `${summary.client_count} total`}
                </div>
              </div>

              <div className="mt-4 max-h-[820px] space-y-3 overflow-y-auto pr-1">
                {viewMode === "team_members" ? (
                  filteredMembers.length === 0 ? (
                    <div className="rounded-2xl border border-dashed border-slate-300 px-4 py-6 text-sm text-slate-500">
                      No team members match the current search.
                    </div>
                  ) : (
                    filteredMembers.map((member) => {
                      const selected = member.entity_id === selectedMemberId;
                      return (
                        <button
                          key={member.entity_id}
                          type="button"
                          onClick={() => setSelectedMemberId(member.entity_id)}
                          className={`w-full rounded-3xl border px-4 py-4 text-left transition ${
                            selected
                              ? "border-[#0a6fd6] bg-[#f3f8ff] shadow"
                              : "border-slate-200 bg-slate-50 hover:border-slate-300 hover:bg-white"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="truncate font-semibold text-slate-900">{member.team_member_name}</p>
                              <p className="truncate text-sm text-slate-500">
                                {member.team_member_email ?? member.clickup_user_id ?? "No email or ClickUp ID"}
                              </p>
                            </div>
                            <p className="whitespace-nowrap text-sm font-semibold text-slate-900">{formatHours(member.total_hours)}</p>
                          </div>
                          <div className="mt-3 flex flex-wrap items-center gap-2">
                            <LinkStatusBadge status={member.link_status} />
                            <span className="text-xs text-slate-500">{member.active_day_count} active days</span>
                            <span className="text-xs text-slate-500">{member.entry_count} entries</span>
                          </div>
                        </button>
                      );
                    })
                  )
                ) : filteredClients.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-slate-300 px-4 py-6 text-sm text-slate-500">
                    No clients match the current search.
                  </div>
                ) : (
                  filteredClients.map((client) => {
                    const selected = client.entity_id === selectedClientId;
                    return (
                      <button
                        key={client.entity_id}
                        type="button"
                        onClick={() => setSelectedClientId(client.entity_id)}
                        className={`w-full rounded-3xl border px-4 py-4 text-left transition ${
                          selected
                            ? "border-[#0a6fd6] bg-[#f3f8ff] shadow"
                            : "border-slate-200 bg-slate-50 hover:border-slate-300 hover:bg-white"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="truncate font-semibold text-slate-900">{client.client_name}</p>
                            <p className="truncate text-sm text-slate-500">{client.brand_count} brands</p>
                          </div>
                          <p className="whitespace-nowrap text-sm font-semibold text-slate-900">{formatHours(client.total_hours)}</p>
                        </div>
                        <div className="mt-3 flex flex-wrap items-center gap-2">
                          <ClientStatusBadge status={client.status} />
                          <span className="text-xs text-slate-500">{client.active_day_count} active days</span>
                          <span className="text-xs text-slate-500">{client.entry_count} entries</span>
                        </div>
                      </button>
                    );
                  })
                )}
              </div>
            </aside>

            <section className="space-y-6">
              {!selectedEntity ? (
                <div className="rounded-3xl border border-dashed border-slate-300 bg-white p-8 text-sm text-slate-500">
                  Choose a {viewMode === "team_members" ? "team member" : "client"} to inspect daily hours.
                </div>
              ) : (
                <>
                  <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                          {viewMode === "team_members" ? "Selected Team Member" : "Selected Client"}
                        </p>
                        <h2 className="mt-2 text-2xl font-semibold text-slate-900">
                          {viewMode === "team_members"
                            ? selectedMember?.team_member_name
                            : selectedClient?.client_name}
                        </h2>
                        <p className="mt-2 text-sm text-slate-500">
                          {viewMode === "team_members"
                            ? selectedMember?.team_member_email ?? selectedMember?.clickup_user_id ?? "No email or ClickUp ID"
                            : `${selectedClient?.brand_count ?? 0} brands tracked under this client`}
                        </p>
                      </div>

                      <div className="flex flex-wrap items-center gap-2">
                        {viewMode === "team_members" && selectedMember ? (
                          <>
                            <LinkStatusBadge status={selectedMember.link_status} />
                            {selectedMember.team_member_profile_id ? (
                              <Link
                                href={`/command-center/team/${selectedMember.team_member_profile_id}`}
                                className="rounded-2xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:-translate-y-0.5 hover:shadow"
                              >
                                Open Team Profile
                              </Link>
                            ) : null}
                          </>
                        ) : null}
                        {viewMode === "clients" && selectedClient ? (
                          <>
                            <ClientStatusBadge status={selectedClient.status} />
                            <Link
                              href={`/command-center/clients/${selectedClient.client_id}`}
                              className="rounded-2xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:-translate-y-0.5 hover:shadow"
                            >
                              Open Client
                            </Link>
                          </>
                        ) : null}
                      </div>
                    </div>

                    <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                      <SummaryCard label="Total" value={formatHours(selectedEntity.total_hours)} />
                      <SummaryCard label="Active Days" value={String(selectedEntity.active_day_count)} />
                      <SummaryCard label="Entries" value={String(selectedEntity.entry_count)} />
                      {viewMode === "team_members" && selectedMember ? (
                        <SummaryCard
                          label="Unattributed"
                          value={formatHours(selectedMember.unmapped_hours)}
                          hint={`${formatHours(selectedMember.mapped_hours)} attributed`}
                          tone={selectedMember.unmapped_hours > 0 ? "warn" : "default"}
                        />
                      ) : (
                        <SummaryCard
                          label="Series"
                          value={String(selectedEntity.series.length)}
                          hint="Distinct stacked segments in chart"
                        />
                      )}
                    </div>
                  </div>

                  <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                    <div className="flex flex-wrap items-end justify-between gap-4">
                      <div>
                        <h3 className="text-lg font-semibold text-slate-900">Daily Hours</h3>
                        <p className="mt-1 text-sm text-slate-500">
                          {viewMode === "team_members"
                            ? "Each day stacks hours by client or brand."
                            : "Each day stacks hours by team member, splitting brands when the same person worked multiple brands under the client."}
                        </p>
                      </div>
                      <div className="text-sm text-slate-500">
                        Hover any day to inspect the stacked amounts.
                      </div>
                    </div>

                    <div className="mt-6 h-[420px]">
                      {!hasChartHours ? (
                        <div className="flex h-full items-center justify-center rounded-3xl border border-dashed border-slate-300 bg-slate-50 text-sm text-slate-500">
                          No hours logged for this selection in the current date range.
                        </div>
                      ) : (
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={chartData} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                            <XAxis dataKey="label" tick={{ fontSize: 12 }} stroke="#64748b" minTickGap={16} />
                            <YAxis tick={{ fontSize: 12 }} stroke="#64748b" />
                            <Tooltip content={<ChartTooltip colorByKey={colorByKey} />} />
                            {chartSeries.map((series, index) => (
                              <Bar
                                key={series.key}
                                dataKey={series.key}
                                stackId="hours"
                                fill={safeColor(index)}
                                radius={[6, 6, 0, 0]}
                              />
                            ))}
                          </BarChart>
                        </ResponsiveContainer>
                      )}
                    </div>
                  </div>

                  <SeriesBreakdown
                    title={viewMode === "team_members" ? "Clients / Brands in Range" : "People / Brands in Range"}
                    rows={selectedEntity.series}
                    colorByKey={colorByKey}
                    emptyMessage="No stacked series for this selection yet."
                  />
                </>
              )}
            </section>
          </section>

          <section className="grid gap-6 xl:grid-cols-2">
            <DriftCard
              title="Unlinked ClickUp Users"
              rows={unmappedUserRows}
              emptyMessage="All visible ClickUp users resolve cleanly to Command Center profiles."
            />
            <DriftCard
              title="Unmapped Spaces"
              rows={unmappedSpaceRows}
              emptyMessage="All visible hours map cleanly to a client."
            />
          </section>
        </>
      ) : null}
    </main>
  );
}
