import type {
  TeamHoursClient,
  TeamHoursDailyPoint,
  TeamHoursDailySegment,
  TeamHoursMember,
  TeamHoursSeries,
  TeamHoursSummary,
  TeamHoursUnmappedSpace,
  TeamHoursUnmappedUser,
} from "@/lib/api/admin/teamHours";

export type TeamHoursExportViewMode = "team_members" | "clients";

type CsvScalar = string | number | boolean | null | undefined;
type CsvRow = Record<string, CsvScalar>;

type TeamHoursCsvInput = {
  viewMode: TeamHoursExportViewMode;
  startDate: string;
  endDate: string;
  summary: TeamHoursSummary;
  teamMembers: TeamHoursMember[];
  clients: TeamHoursClient[];
  unmappedUsers: TeamHoursUnmappedUser[];
  unmappedSpaces: TeamHoursUnmappedSpace[];
};

const CSV_HEADERS = [
  "row_type",
  "view_mode",
  "range_start_date",
  "range_end_date",
  "entity_id",
  "parent_entity_id",
  "date",
  "name",
  "email",
  "status",
  "timezone_name",
  "hours",
  "mapped_hours",
  "unmapped_hours",
  "unattributed_hours",
  "entry_count",
  "active_day_count",
  "brand_count",
  "series_count",
  "client_id",
  "client_name",
  "brand_id",
  "brand_name",
  "team_member_profile_id",
  "team_member_name",
  "team_member_email",
  "clickup_user_id",
  "space_id",
  "space_name",
  "list_id",
  "list_name",
  "link_status",
  "employment_status",
  "mapped",
  "unique_users",
  "running_entries",
  "team_member_count",
  "team_members_with_hours",
  "client_count",
  "clients_with_hours",
  "detail",
] as const;

const escapeCsv = (value: CsvScalar): string => {
  const text = value === null || value === undefined ? "" : String(value);
  if (/[",\n\r]/.test(text)) {
    return `"${text.replace(/"/g, "\"\"")}"`;
  }
  return text;
};

const toCsv = (rows: CsvRow[]): string => {
  const headerLine = CSV_HEADERS.join(",");
  const bodyLines = rows.map((row) =>
    CSV_HEADERS.map((header) => escapeCsv(row[header])).join(","),
  );
  return [headerLine, ...bodyLines].join("\n");
};

const baseRow = (
  input: Pick<TeamHoursCsvInput, "viewMode" | "startDate" | "endDate">,
  rowType: string,
  overrides: CsvRow = {},
): CsvRow => ({
  row_type: rowType,
  view_mode: input.viewMode,
  range_start_date: input.startDate,
  range_end_date: input.endDate,
  ...overrides,
});

const pushDailyRows = (
  rows: CsvRow[],
  input: Pick<TeamHoursCsvInput, "viewMode" | "startDate" | "endDate">,
  parentEntityId: string,
  daily: TeamHoursDailyPoint[],
  context: {
    rowType: string;
    segmentRowType: string;
    name: string;
    timezoneName: string | null;
    clientId?: string | null;
    clientName?: string | null;
    teamMemberProfileId?: string | null;
    teamMemberName?: string | null;
    teamMemberEmail?: string | null;
    clickupUserId?: string | null;
  },
) => {
  for (const day of daily) {
    const dayEntityId = `${parentEntityId}:${day.date}`;
    rows.push(
      baseRow(input, context.rowType, {
        entity_id: dayEntityId,
        parent_entity_id: parentEntityId,
        date: day.date,
        name: context.name,
        timezone_name: context.timezoneName,
        hours: day.total_hours,
        entry_count: day.segments.length,
        client_id: context.clientId,
        client_name: context.clientName,
        team_member_profile_id: context.teamMemberProfileId,
        team_member_name: context.teamMemberName,
        team_member_email: context.teamMemberEmail,
        clickup_user_id: context.clickupUserId,
        detail: `${day.segments.length} segments`,
      }),
    );

    for (const segment of day.segments) {
      rows.push(
        baseRow(input, context.segmentRowType, {
          entity_id: `${dayEntityId}:${segment.key}`,
          parent_entity_id: dayEntityId,
          date: day.date,
          name: segment.label,
          hours: segment.hours,
          client_id: segment.client_id,
          client_name: segment.client_name,
          brand_id: segment.brand_id,
          brand_name: segment.brand_name,
          team_member_profile_id: segment.team_member_profile_id,
          team_member_name: segment.team_member_name,
          team_member_email: segment.team_member_email,
          clickup_user_id: segment.clickup_user_id,
          mapped: segment.mapped,
        }),
      );
    }
  }
};

const pushSeriesRows = (
  rows: CsvRow[],
  input: Pick<TeamHoursCsvInput, "viewMode" | "startDate" | "endDate">,
  parentEntityId: string,
  rowType: string,
  seriesRows: TeamHoursSeries[],
  context: {
    teamMemberProfileId?: string | null;
    teamMemberName?: string | null;
    teamMemberEmail?: string | null;
    clickupUserId?: string | null;
    clientId?: string | null;
    clientName?: string | null;
  },
) => {
  for (const series of seriesRows) {
    rows.push(
      baseRow(input, rowType, {
        entity_id: `${parentEntityId}:${series.key}`,
        parent_entity_id: parentEntityId,
        name: series.label,
        hours: series.total_hours,
        client_id: series.client_id ?? context.clientId,
        client_name: series.client_name ?? context.clientName,
        brand_id: series.brand_id,
        brand_name: series.brand_name,
        team_member_profile_id:
          series.team_member_profile_id ?? context.teamMemberProfileId,
        team_member_name: series.team_member_name ?? context.teamMemberName,
        team_member_email: series.team_member_email ?? context.teamMemberEmail,
        clickup_user_id: series.clickup_user_id ?? context.clickupUserId,
        space_id: series.space_id,
        space_name: series.space_name,
        list_id: series.list_id,
        list_name: series.list_name,
        mapped: series.mapped,
      }),
    );
  }
};

export const buildTeamHoursCsv = (input: TeamHoursCsvInput): string => {
  const rows: CsvRow[] = [];

  rows.push(
    baseRow(input, "summary", {
      name: input.viewMode === "team_members" ? "Team Members" : "Clients",
      hours: input.summary.total_hours,
      mapped_hours: input.summary.mapped_hours,
      unmapped_hours: input.summary.unmapped_hours,
      unattributed_hours: input.summary.unattributed_hours,
      entry_count: input.summary.entry_count,
      unique_users: input.summary.unique_users,
      running_entries: input.summary.running_entries,
      team_member_count: input.summary.team_member_count,
      team_members_with_hours: input.summary.team_members_with_hours,
      client_count: input.summary.client_count,
      clients_with_hours: input.summary.clients_with_hours,
    }),
  );

  if (input.viewMode === "team_members") {
    for (const member of input.teamMembers) {
      rows.push(
        baseRow(input, "team_member", {
          entity_id: member.entity_id,
          name: member.team_member_name,
          email: member.team_member_email,
          timezone_name: member.timezone_name,
          hours: member.total_hours,
          mapped_hours: member.mapped_hours,
          unmapped_hours: member.unmapped_hours,
          entry_count: member.entry_count,
          active_day_count: member.active_day_count,
          series_count: member.series.length,
          team_member_profile_id: member.team_member_profile_id,
          team_member_name: member.team_member_name,
          team_member_email: member.team_member_email,
          clickup_user_id: member.clickup_user_id,
          link_status: member.link_status,
          employment_status: member.employment_status,
        }),
      );

      pushSeriesRows(rows, input, member.entity_id, "team_member_series", member.series, {
        teamMemberProfileId: member.team_member_profile_id,
        teamMemberName: member.team_member_name,
        teamMemberEmail: member.team_member_email,
        clickupUserId: member.clickup_user_id,
      });

      pushDailyRows(rows, input, member.entity_id, member.daily, {
        rowType: "team_member_daily",
        segmentRowType: "team_member_daily_segment",
        name: member.team_member_name,
        timezoneName: member.timezone_name,
        teamMemberProfileId: member.team_member_profile_id,
        teamMemberName: member.team_member_name,
        teamMemberEmail: member.team_member_email,
        clickupUserId: member.clickup_user_id,
      });
    }
  } else {
    for (const client of input.clients) {
      rows.push(
        baseRow(input, "client", {
          entity_id: client.entity_id,
          name: client.client_name,
          status: client.status,
          timezone_name: client.timezone_name,
          hours: client.total_hours,
          entry_count: client.entry_count,
          active_day_count: client.active_day_count,
          brand_count: client.brand_count,
          series_count: client.series.length,
          client_id: client.client_id,
          client_name: client.client_name,
        }),
      );

      pushSeriesRows(rows, input, client.entity_id, "client_series", client.series, {
        clientId: client.client_id,
        clientName: client.client_name,
      });

      pushDailyRows(rows, input, client.entity_id, client.daily, {
        rowType: "client_daily",
        segmentRowType: "client_daily_segment",
        name: client.client_name,
        timezoneName: client.timezone_name,
        clientId: client.client_id,
        clientName: client.client_name,
      });
    }
  }

  for (const user of input.unmappedUsers) {
    rows.push(
      baseRow(input, "unmapped_user", {
        name: user.clickup_username ?? "Unlinked ClickUp User",
        email: user.clickup_user_email,
        hours: user.total_hours,
        clickup_user_id: user.clickup_user_id,
        detail: "No matching Command Center profile",
      }),
    );
  }

  for (const space of input.unmappedSpaces) {
    rows.push(
      baseRow(input, "unmapped_space", {
        name: space.space_name,
        hours: space.total_hours,
        space_id: space.space_id,
        space_name: space.space_name,
        list_id: space.list_id,
        list_name: space.list_name,
        detail: "No matching Command Center client/brand mapping",
      }),
    );
  }

  return toCsv(rows);
};

const slugify = (value: string) =>
  value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "team-hours";

export const buildTeamHoursCsvFilename = (
  viewMode: TeamHoursExportViewMode,
  startDate: string,
  endDate: string,
): string => {
  const prefix =
    viewMode === "team_members" ? "team-hours-team-members" : "team-hours-clients";
  return `${slugify(prefix)}_${startDate}_to_${endDate}.csv`;
};

export const downloadTeamHoursCsv = (filename: string, csv: string) => {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};
