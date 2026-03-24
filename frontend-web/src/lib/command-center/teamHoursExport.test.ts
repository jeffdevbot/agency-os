import { describe, expect, it } from "vitest";

import {
  buildTeamHoursCsv,
  buildTeamHoursCsvFilename,
} from "./teamHoursExport";

describe("teamHoursExport", () => {
  it("builds a team-member CSV with summary, nested rows, and unmapped rows", () => {
    const csv = buildTeamHoursCsv({
      viewMode: "team_members",
      startDate: "2026-03-01",
      endDate: "2026-03-31",
      summary: {
        total_hours: 8.5,
        mapped_hours: 7.5,
        unmapped_hours: 1,
        unattributed_hours: 1,
        unique_users: 2,
        entry_count: 5,
        running_entries: 0,
        team_member_count: 2,
        team_members_with_hours: 1,
        client_count: 1,
        clients_with_hours: 1,
      },
      teamMembers: [
        {
          entity_id: "profile:alice",
          clickup_user_id: "101",
          team_member_profile_id: "alice",
          team_member_name: "Alice",
          team_member_email: "alice@agency.test",
          employment_status: "active",
          link_status: "linked",
          timezone_name: "America/Toronto",
          total_hours: 8.5,
          mapped_hours: 7.5,
          unmapped_hours: 1,
          entry_count: 5,
          active_day_count: 2,
          day_range: ["2026-03-10", "2026-03-11"],
          series: [
            {
              key: "client-1|brand-1|space-1|list-1",
              label: "Client A • Brand A",
              total_hours: 7.5,
              client_id: "client-1",
              client_name: "Client A",
              brand_id: "brand-1",
              brand_name: "Brand A",
              mapped: true,
              space_id: "space-1",
              space_name: "Space A",
              list_id: "list-1",
              list_name: "List A",
            },
          ],
          daily: [
            {
              date: "2026-03-10",
              total_hours: 4.5,
              segments: [
                {
                  key: "client-1|brand-1|space-1|list-1",
                  label: "Client A • Brand A",
                  hours: 4.5,
                  duration_ms: 16200000,
                  client_id: "client-1",
                  client_name: "Client A",
                  brand_id: "brand-1",
                  brand_name: "Brand A",
                  mapped: true,
                },
              ],
            },
          ],
        },
      ],
      clients: [],
      unmappedUsers: [
        {
          clickup_user_id: "202",
          clickup_username: "Bob CU",
          clickup_user_email: "bob@clickup.test",
          total_hours: 1,
        },
      ],
      unmappedSpaces: [
        {
          space_id: "space-x",
          space_name: "Unlinked Space",
          list_id: "list-x",
          list_name: "Unlinked List",
          total_hours: 1,
        },
      ],
    });

    const lines = csv.split("\n");

    expect(lines[0]).toContain("row_type,view_mode,range_start_date,range_end_date");
    expect(csv).toContain("summary,team_members,2026-03-01,2026-03-31");
    expect(csv).toContain("team_member,team_members,2026-03-01,2026-03-31,profile:alice");
    expect(csv).toContain("team_member_series,team_members,2026-03-01,2026-03-31");
    expect(csv).toContain("team_member_daily_segment,team_members,2026-03-01,2026-03-31");
    expect(csv).toContain("unmapped_user,team_members,2026-03-01,2026-03-31");
    expect(csv).toContain("unmapped_space,team_members,2026-03-01,2026-03-31");
    expect(csv).toContain("No matching Command Center profile");
  });

  it("builds stable export filenames for the current view and date range", () => {
    expect(
      buildTeamHoursCsvFilename("team_members", "2026-03-01", "2026-03-31"),
    ).toBe("team-hours-team-members_2026-03-01_to_2026-03-31.csv");
    expect(
      buildTeamHoursCsvFilename("clients", "2026-03-01", "2026-03-31"),
    ).toBe("team-hours-clients_2026-03-01_to_2026-03-31.csv");
  });
});
