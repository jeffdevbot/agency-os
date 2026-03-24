"use client";

import Link from "next/link";
import { useDeferredValue, useEffect, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import {
  getTeamHoursReport,
  type TeamHoursClientSummary,
  type TeamHoursMember,
  type TeamHoursReport,
  type TeamHoursSummary,
  type TeamHoursSpaceSummary,
  type TeamHoursUnmappedSpace,
  type TeamHoursUnmappedUser,
} from "@/lib/api/admin/teamHours";

const DAY_MS = 24 * 60 * 60 * 1000;

type MappingFilter = "all" | "mapped" | "unlinked";
type ViewMode = "all" | "clients" | "spaces" | "members" | "drift";

const formatDateInput = (date: Date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const formatHours = (value: number) => `${value.toFixed(2)}h`;

const roundHours = (value: number) => Math.round(value * 100) / 100;

const passesMappingFilter = (mapped: boolean, filter: MappingFilter) => {
  if (filter === "mapped") return mapped;
  if (filter === "unlinked") return !mapped;
  return true;
};

const matchesSearch = (
  query: string,
  values: Array<string | number | null | undefined>,
) => {
  if (!query) return true;
  return values.some((value) =>
    String(value ?? "").toLowerCase().includes(query),
  );
};

const csvEscape = (value: string | number | boolean | null | undefined) => {
  const text = String(value ?? "");
  if (text.includes(",") || text.includes('"') || text.includes("\n")) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
};

const downloadCsv = (
  filename: string,
  headers: string[],
  rows: Array<Array<string | number | boolean | null | undefined>>,
) => {
  const csv = [headers.map(csvEscape).join(","), ...rows.map((row) => row.map(csvEscape).join(","))].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

const formatDateLabel = (value: string) => {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
  }).format(date);
};

const startOfDayMs = (value: string) => new Date(`${value}T00:00:00`).getTime();

const endOfDayMs = (value: string) => new Date(`${value}T23:59:59.999`).getTime();

const defaultDateRange = () => {
  const end = new Date();
  const start = new Date(end.getTime() - 29 * DAY_MS);
  return {
    startDate: formatDateInput(start),
    endDate: formatDateInput(end),
  };
};

type SummaryCardProps = {
  label: string;
  value: string;
  tone?: "default" | "warn";
};

function ClientNameLink({
  clientId,
  clientName,
  className = "",
}: {
  clientId: string | null;
  clientName: string;
  className?: string;
}) {
  if (!clientId) {
    return <span className={className}>{clientName}</span>;
  }

  return (
    <Link
      href={`/command-center/clients/${clientId}`}
      className={`${className} text-[#0a6fd6] underline decoration-[#0a6fd6]/30 underline-offset-4 transition hover:text-[#0859ad] hover:decoration-[#0859ad]`}
    >
      {clientName}
    </Link>
  );
}

function TeamMemberNameLink({
  teamMemberProfileId,
  teamMemberName,
  className = "",
}: {
  teamMemberProfileId: string | null;
  teamMemberName: string;
  className?: string;
}) {
  if (!teamMemberProfileId) {
    return <span className={className}>{teamMemberName}</span>;
  }

  return (
    <Link
      href={`/command-center/team/${teamMemberProfileId}`}
      className={`${className} text-[#0a6fd6] underline decoration-[#0a6fd6]/30 underline-offset-4 transition hover:text-[#0859ad] hover:decoration-[#0859ad]`}
    >
      {teamMemberName}
    </Link>
  );
}

function SummaryCard({ label, value, tone = "default" }: SummaryCardProps) {
  const toneClass =
    tone === "warn"
      ? "border-amber-200 bg-amber-50 text-amber-900"
      : "border-slate-200 bg-white text-slate-900";

  return (
    <div className={`rounded-2xl border p-4 shadow-sm ${toneClass}`}>
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </div>
  );
}

function TeamMemberTable({ members }: { members: TeamHoursMember[] }) {
  if (members.length === 0) {
    return (
      <div className="rounded-3xl border border-dashed border-slate-300 bg-white/80 p-6 text-sm text-slate-500">
        No ClickUp time entries were returned for this date range.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-3xl bg-white shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
      <div className="border-b border-slate-200 px-6 py-4">
        <h2 className="text-lg font-semibold text-slate-900">By Team Member</h2>
        <p className="mt-1 text-sm text-slate-500">
          Profile linking and client attribution are tracked separately, so an unlinked ClickUp user can still have attributed client hours.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50">
            <tr className="text-left text-slate-500">
              <th className="px-6 py-3 font-medium">Team Member</th>
              <th className="px-4 py-3 font-medium">Profile</th>
              <th className="px-4 py-3 font-medium">Total</th>
              <th className="px-4 py-3 font-medium">Mapped</th>
              <th className="px-4 py-3 font-medium">Unmapped</th>
              <th className="px-6 py-3 font-medium">Client / Brand Breakdown</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {members.map((member) => (
              <tr key={`${member.team_member_profile_id ?? "clickup"}:${member.clickup_user_id ?? "unknown"}`}>
                <td className="px-6 py-4 align-top">
                  <div className="font-semibold text-slate-900">
                    <TeamMemberNameLink
                      teamMemberProfileId={member.team_member_profile_id}
                      teamMemberName={member.team_member_name}
                      className="font-semibold text-slate-900"
                    />
                  </div>
                  <div className="text-xs text-slate-500">{member.team_member_email ?? member.clickup_user_id ?? "No email"}</div>
                  {member.clickup_user_id ? (
                    <div className="text-xs text-slate-400">ClickUp ID: {member.clickup_user_id}</div>
                  ) : null}
                </td>
                <td className="px-4 py-4 align-top">
                  <span
                    className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${
                      member.mapped ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {member.mapped ? "Linked" : "Unlinked"}
                  </span>
                </td>
                <td className="px-4 py-4 align-top font-semibold text-slate-900">{formatHours(member.total_hours)}</td>
                <td className="px-4 py-4 align-top text-slate-700">{formatHours(member.mapped_hours)}</td>
                <td className="px-4 py-4 align-top text-slate-700">{formatHours(member.unmapped_hours)}</td>
                <td className="px-6 py-4 align-top">
                  <div className="space-y-2">
                    {member.clients.map((client) => (
                      <div
                        key={`${client.client_id ?? "unmapped"}:${client.brand_id ?? "brand"}:${client.space_id ?? "space"}:${client.list_id ?? "list"}`}
                        className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <ClientNameLink
                            clientId={client.client_id}
                            clientName={client.client_name}
                            className="font-semibold text-slate-900"
                          />
                          {client.brand_name ? (
                            <span className="text-slate-600">{client.brand_name}</span>
                          ) : null}
                          <span
                            className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                              client.mapped ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
                            }`}
                          >
                            {client.mapped ? "Mapped" : "Unlinked"}
                          </span>
                          <span className="ml-auto font-semibold text-slate-900">{formatHours(client.total_hours)}</span>
                        </div>
                        <div className="mt-1 text-xs text-slate-500">
                          Space: {client.space_name ?? client.space_id ?? "Unknown"} | List: {client.list_name ?? client.list_id ?? "Unknown"}
                        </div>
                      </div>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ClientSummaryTable({ rows }: { rows: TeamHoursClientSummary[] }) {
  return (
    <section className="overflow-hidden rounded-3xl bg-white shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
      <div className="border-b border-slate-200 px-6 py-4">
        <h2 className="text-lg font-semibold text-slate-900">By Client / Brand</h2>
        <p className="mt-1 text-sm text-slate-500">
          Client-first slice of hours so you can see where team time concentrated across mapped and unmapped work.
        </p>
      </div>
      {rows.length === 0 ? (
        <div className="px-6 py-5 text-sm text-slate-500">
          No client rows match the current slice.
        </div>
      ) : (
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50">
            <tr className="text-left text-slate-500">
              <th className="px-6 py-3 font-medium">Client</th>
              <th className="px-4 py-3 font-medium">Brand</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Hours</th>
              <th className="px-4 py-3 font-medium">People</th>
              <th className="px-4 py-3 font-medium">Spaces</th>
              <th className="px-4 py-3 font-medium">Entries</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((row) => (
              <tr key={`${row.client_id ?? "unmapped"}:${row.brand_id ?? "brand"}`}>
                <td className="px-6 py-4 font-semibold text-slate-900">
                  <ClientNameLink
                    clientId={row.client_id}
                    clientName={row.client_name}
                    className="font-semibold text-slate-900"
                  />
                </td>
                <td className="px-4 py-4 text-slate-600">{row.brand_name ?? "—"}</td>
                <td className="px-4 py-4">
                  <span
                    className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${
                      row.mapped ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {row.mapped ? "Mapped" : "Unlinked"}
                  </span>
                </td>
                <td className="px-4 py-4 font-semibold text-slate-900">{formatHours(row.total_hours)}</td>
                <td className="px-4 py-4 text-slate-600">{row.team_member_count}</td>
                <td className="px-4 py-4 text-slate-600">{row.space_count}</td>
                <td className="px-4 py-4 text-slate-600">{row.entry_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      )}
    </section>
  );
}

function SpaceSummaryTable({ rows }: { rows: TeamHoursSpaceSummary[] }) {
  return (
    <section className="overflow-hidden rounded-3xl bg-white shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
      <div className="border-b border-slate-200 px-6 py-4">
        <h2 className="text-lg font-semibold text-slate-900">By Space</h2>
        <p className="mt-1 text-sm text-slate-500">
          Space-first slice of hours so ClickUp structure drift is visible without losing the associated time.
        </p>
      </div>
      {rows.length === 0 ? (
        <div className="px-6 py-5 text-sm text-slate-500">
          No space rows match the current slice.
        </div>
      ) : (
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50">
            <tr className="text-left text-slate-500">
              <th className="px-6 py-3 font-medium">Space</th>
              <th className="px-4 py-3 font-medium">List</th>
              <th className="px-4 py-3 font-medium">Client / Brand</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Hours</th>
              <th className="px-4 py-3 font-medium">People</th>
              <th className="px-4 py-3 font-medium">Entries</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((row) => (
              <tr key={`${row.space_id ?? "space"}:${row.list_id ?? "list"}`}>
                <td className="px-6 py-4 font-semibold text-slate-900">{row.space_name}</td>
                <td className="px-4 py-4 text-slate-600">{row.list_name ?? row.list_id ?? "—"}</td>
                <td className="px-4 py-4 text-slate-600">
                  <ClientNameLink
                    clientId={row.client_id}
                    clientName={row.client_name}
                    className="font-medium text-slate-700"
                  />
                  {row.brand_name ? ` / ${row.brand_name}` : ""}
                </td>
                <td className="px-4 py-4">
                  <span
                    className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${
                      row.mapped ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {row.mapped ? "Mapped" : "Unlinked"}
                  </span>
                </td>
                <td className="px-4 py-4 font-semibold text-slate-900">{formatHours(row.total_hours)}</td>
                <td className="px-4 py-4 text-slate-600">{row.team_member_count}</td>
                <td className="px-4 py-4 text-slate-600">{row.entry_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      )}
    </section>
  );
}

function DriftTable({
  title,
  description,
  rows,
  emptyMessage,
}: {
  title: string;
  description: string;
  rows: Array<{ key: string; name: string; detail: string; hours: number }>;
  emptyMessage: string;
}) {
  return (
    <section className="overflow-hidden rounded-3xl bg-white shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
      <div className="border-b border-slate-200 px-6 py-4">
        <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        <p className="mt-1 text-sm text-slate-500">{description}</p>
      </div>
      {rows.length === 0 ? (
        <div className="px-6 py-5 text-sm text-slate-500">{emptyMessage}</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr className="text-left text-slate-500">
                <th className="px-6 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Detail</th>
                <th className="px-4 py-3 font-medium">Hours</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row) => (
                <tr key={row.key}>
                  <td className="px-6 py-4 font-semibold text-slate-900">{row.name}</td>
                  <td className="px-4 py-4 text-slate-600">{row.detail}</td>
                  <td className="px-4 py-4 font-semibold text-slate-900">{formatHours(row.hours)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

const unmappedUserRows = (users: TeamHoursUnmappedUser[]) =>
  users.map((user) => ({
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
  }));

const unmappedSpaceRows = (spaces: TeamHoursUnmappedSpace[]) =>
  spaces.map((space) => ({
    key: space.space_id ?? space.list_id ?? "unknown-space",
    name: space.space_name,
    detail: `space_id=${space.space_id ?? "—"} | list_id=${space.list_id ?? "—"}`,
    hours: space.total_hours,
  }));

export default function CommandCenterHoursPage() {
  const defaults = defaultDateRange();
  const [token, setToken] = useState<string | null>(null);
  const [startDate, setStartDate] = useState(defaults.startDate);
  const [endDate, setEndDate] = useState(defaults.endDate);
  const [searchQuery, setSearchQuery] = useState("");
  const [mappingFilter, setMappingFilter] = useState<MappingFilter>("all");
  const [viewMode, setViewMode] = useState<ViewMode>("all");
  const [report, setReport] = useState<TeamHoursReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
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
  const filteredMembers: TeamHoursMember[] = [];
  for (const member of report?.by_team_member ?? []) {
    const memberMatches = matchesSearch(deferredSearchQuery, [
      member.team_member_name,
      member.team_member_email,
      member.clickup_user_id,
    ]);
    const visibleClients = member.clients.filter((client) => {
      if (!passesMappingFilter(client.mapped, mappingFilter)) return false;
      if (memberMatches) return true;
      return matchesSearch(deferredSearchQuery, [
        client.client_name,
        client.brand_name,
        client.space_name,
        client.list_name,
      ]);
    });
    if (visibleClients.length === 0) continue;

    const totalHours = roundHours(
      visibleClients.reduce((sum, client) => sum + client.total_hours, 0),
    );
    const mappedHours = roundHours(
      visibleClients.reduce(
        (sum, client) => sum + (client.mapped ? client.total_hours : 0),
        0,
      ),
    );

    filteredMembers.push({
      ...member,
      mapped: member.mapped,
      total_hours: totalHours,
      mapped_hours: mappedHours,
      unmapped_hours: roundHours(totalHours - mappedHours),
      clients: visibleClients,
    });
  }

  const filteredClientRows = (report?.by_client ?? []).filter(
    (row) =>
      passesMappingFilter(row.mapped, mappingFilter) &&
      matchesSearch(deferredSearchQuery, [
        row.client_name,
        row.brand_name,
      ]),
  );
  const filteredSpaceRows = (report?.by_space ?? []).filter(
    (row) =>
      passesMappingFilter(row.mapped, mappingFilter) &&
      matchesSearch(deferredSearchQuery, [
        row.space_name,
        row.list_name,
        row.client_name,
        row.brand_name,
      ]),
  );
  const filteredUnmappedUsers =
    mappingFilter === "mapped"
      ? []
      : (report?.unmapped_users ?? []).filter((row) =>
          matchesSearch(deferredSearchQuery, [
            row.clickup_username,
            row.clickup_user_email,
            row.clickup_user_id,
          ]),
        );
  const filteredUnmappedSpaces =
    mappingFilter === "mapped"
      ? []
      : (report?.unmapped_spaces ?? []).filter((row) =>
          matchesSearch(deferredSearchQuery, [
            row.space_name,
            row.list_name,
            row.space_id,
            row.list_id,
          ]),
        );
  const visibleSliceHours = roundHours(
    filteredMembers.reduce((sum, member) => sum + member.total_hours, 0),
  );
  const filtersActive = deferredSearchQuery.length > 0 || mappingFilter !== "all";

  const exportMemberBreakdown = () => {
    if (!report) return;
    downloadCsv(
      `team-hours-members-${startDate}-to-${endDate}.csv`,
      [
        "team_member_name",
        "team_member_email",
        "profile_linked",
        "team_total_hours",
        "client_name",
        "brand_name",
        "space_name",
        "list_name",
        "bucket_mapped",
        "bucket_total_hours",
      ],
      filteredMembers.flatMap((member) =>
        member.clients.map((client) => [
          member.team_member_name,
          member.team_member_email,
          member.mapped,
          member.total_hours,
          client.client_name,
          client.brand_name,
          client.space_name,
          client.list_name,
          client.mapped,
          client.total_hours,
        ]),
      ),
    );
  };

  const exportClientSummary = () => {
    if (!report) return;
    downloadCsv(
      `team-hours-clients-${startDate}-to-${endDate}.csv`,
      ["client_name", "brand_name", "mapped", "total_hours", "team_member_count", "space_count", "entry_count"],
      filteredClientRows.map((row) => [
        row.client_name,
        row.brand_name,
        row.mapped,
        row.total_hours,
        row.team_member_count,
        row.space_count,
        row.entry_count,
      ]),
    );
  };

  const exportSpaceSummary = () => {
    if (!report) return;
    downloadCsv(
      `team-hours-spaces-${startDate}-to-${endDate}.csv`,
      ["space_name", "list_name", "client_name", "brand_name", "mapped", "total_hours", "team_member_count", "entry_count"],
      filteredSpaceRows.map((row) => [
        row.space_name,
        row.list_name,
        row.client_name,
        row.brand_name,
        row.mapped,
        row.total_hours,
        row.team_member_count,
        row.entry_count,
      ]),
    );
  };

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
              ClickUp time-entry rollup for the team, with mapped and unmapped hours kept separate so Command Center drift is visible.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              {report ? `${formatDateLabel(startDate)} to ${formatDateLabel(endDate)}` : "Select a date range"}
            </div>
            <button
              type="button"
              onClick={exportMemberBreakdown}
              disabled={!report}
              className="rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-700 shadow-sm transition hover:-translate-y-0.5 hover:shadow disabled:cursor-not-allowed disabled:opacity-50"
            >
              Export Member CSV
            </button>
            <button
              type="button"
              onClick={exportClientSummary}
              disabled={!report}
              className="rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-700 shadow-sm transition hover:-translate-y-0.5 hover:shadow disabled:cursor-not-allowed disabled:opacity-50"
            >
              Export Client CSV
            </button>
            <button
              type="button"
              onClick={exportSpaceSummary}
              disabled={!report}
              className="rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-700 shadow-sm transition hover:-translate-y-0.5 hover:shadow disabled:cursor-not-allowed disabled:opacity-50"
            >
              Export Space CSV
            </button>
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
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Coverage</p>
            <p className="mt-2 text-sm text-slate-700">
              Pulls workspace members first, then queries ClickUp time entries for the selected range.
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Drift Handling</p>
            <p className="mt-2 text-sm text-slate-700">
              Unlinked users and spaces stay in the report so you can clean them up later in Command Center.
            </p>
          </div>
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <label className="space-y-2 xl:col-span-2">
            <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Search</span>
            <input
              type="text"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search team member, client, brand, space, list, or ClickUp id"
              className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900"
            />
          </label>
          <label className="space-y-2">
            <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Attribution Filter</span>
            <select
              value={mappingFilter}
              onChange={(event) => setMappingFilter(event.target.value as MappingFilter)}
              className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900"
            >
              <option value="all">All Hours</option>
              <option value="mapped">Attributed Only</option>
              <option value="unlinked">Unattributed Only</option>
            </select>
          </label>
          <label className="space-y-2">
            <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Focus View</span>
            <select
              value={viewMode}
              onChange={(event) => setViewMode(event.target.value as ViewMode)}
              className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900"
            >
              <option value="all">All Sections</option>
              <option value="clients">Clients Only</option>
              <option value="spaces">Spaces Only</option>
              <option value="members">Team Members Only</option>
              <option value="drift">Drift Only</option>
            </select>
          </label>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => {
              setSearchQuery("");
              setMappingFilter("all");
              setViewMode("all");
            }}
            className="rounded-2xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:-translate-y-0.5 hover:shadow"
          >
            Clear Filters
          </button>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-600">
            Visible slice: {formatHours(visibleSliceHours)} across {filteredMembers.length} people
          </div>
          {filtersActive ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900">
              Filtered view active
            </div>
          ) : null}
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
            <SummaryCard label="Mapped Hours" value={formatHours(summary.mapped_hours)} />
            <SummaryCard label="Unmapped Hours" value={formatHours(summary.unmapped_hours)} tone="warn" />
            <SummaryCard label="Active People" value={String(summary.unique_users)} />
            <SummaryCard label="Time Entries" value={String(summary.entry_count)} />
            <SummaryCard label="Unattributed Hours" value={formatHours(summary.unattributed_hours)} tone="warn" />
            <SummaryCard label="Running Entries" value={String(summary.running_entries)} tone={summary.running_entries > 0 ? "warn" : "default"} />
          </section>

          {filtersActive ? (
            <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <SummaryCard label="Visible Hours" value={formatHours(visibleSliceHours)} />
              <SummaryCard label="Visible People" value={String(filteredMembers.length)} />
              <SummaryCard label="Visible Clients" value={String(filteredClientRows.length)} />
              <SummaryCard label="Visible Spaces" value={String(filteredSpaceRows.length)} />
            </section>
          ) : null}

          {viewMode === "all" ? (
            <div className="grid gap-6 xl:grid-cols-2">
              <ClientSummaryTable rows={filteredClientRows} />
              <SpaceSummaryTable rows={filteredSpaceRows} />
            </div>
          ) : null}

          {viewMode === "clients" ? (
            <ClientSummaryTable rows={filteredClientRows} />
          ) : null}

          {viewMode === "spaces" ? (
            <SpaceSummaryTable rows={filteredSpaceRows} />
          ) : null}

          {(viewMode === "all" || viewMode === "members") ? (
            <TeamMemberTable members={filteredMembers} />
          ) : null}

          {(viewMode === "all" || viewMode === "drift") ? (
            <div className="grid gap-6 xl:grid-cols-2">
              <DriftTable
                title="Unlinked ClickUp Users"
                description="These users logged time but do not resolve cleanly to a single Command Center profile."
                rows={unmappedUserRows(filteredUnmappedUsers)}
                emptyMessage="All visible time-entry users map cleanly to Command Center profiles."
              />
              <DriftTable
                title="Unlinked Spaces"
                description="These entries did not resolve cleanly to a single brand via ClickUp list or space mapping."
                rows={unmappedSpaceRows(filteredUnmappedSpaces)}
                emptyMessage="All visible hours map cleanly to a brand."
              />
            </div>
          ) : null}
        </>
      ) : null}
    </main>
  );
}
