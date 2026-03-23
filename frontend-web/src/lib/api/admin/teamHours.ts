export type TeamHoursSummary = {
  total_hours: number;
  mapped_hours: number;
  unmapped_hours: number;
  unattributed_hours: number;
  unique_users: number;
  entry_count: number;
  running_entries: number;
};

export type TeamHoursClientBucket = {
  client_id: string | null;
  client_name: string;
  brand_id: string | null;
  brand_name: string | null;
  space_id: string | null;
  space_name: string | null;
  list_id: string | null;
  list_name: string | null;
  mapped: boolean;
  total_hours: number;
};

export type TeamHoursMember = {
  clickup_user_id: string | null;
  team_member_profile_id: string | null;
  team_member_name: string;
  team_member_email: string | null;
  mapped: boolean;
  total_hours: number;
  mapped_hours: number;
  unmapped_hours: number;
  clients: TeamHoursClientBucket[];
};

export type TeamHoursUnmappedUser = {
  clickup_user_id: string | null;
  clickup_username: string | null;
  clickup_user_email: string | null;
  total_hours: number;
};

export type TeamHoursUnmappedSpace = {
  space_id: string | null;
  space_name: string;
  list_id: string | null;
  list_name: string | null;
  total_hours: number;
};

export type TeamHoursClientSummary = {
  client_id: string | null;
  client_name: string;
  brand_id: string | null;
  brand_name: string | null;
  mapped: boolean;
  team_member_count: number;
  space_count: number;
  entry_count: number;
  total_hours: number;
};

export type TeamHoursSpaceSummary = {
  space_id: string | null;
  space_name: string;
  list_id: string | null;
  list_name: string | null;
  client_id: string | null;
  client_name: string;
  brand_id: string | null;
  brand_name: string | null;
  mapped: boolean;
  team_member_count: number;
  entry_count: number;
  total_hours: number;
};

export type TeamHoursReport = {
  date_range: {
    start_date_ms: number;
    end_date_ms: number;
  };
  summary: TeamHoursSummary;
  by_team_member: TeamHoursMember[];
  by_client: TeamHoursClientSummary[];
  by_space: TeamHoursSpaceSummary[];
  unmapped_users: TeamHoursUnmappedUser[];
  unmapped_spaces: TeamHoursUnmappedSpace[];
};

const getBackendUrl = (): string => {
  const url = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (!url) {
    throw new Error("NEXT_PUBLIC_BACKEND_URL is not configured");
  }
  return url;
};

const parseErrorDetail = async (response: Response): Promise<string> => {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    if (typeof body?.message === "string") return body.message;
    if (typeof body?.error?.message === "string") return body.error.message;
    return JSON.stringify(body);
  } catch {
    return response.statusText || `HTTP ${response.status}`;
  }
};

export const getTeamHoursReport = async (
  token: string,
  params: { startDateMs: number; endDateMs: number },
): Promise<TeamHoursReport> => {
  const url = new URL(`${getBackendUrl()}/admin/team-hours`);
  url.searchParams.set("start_date_ms", String(params.startDateMs));
  url.searchParams.set("end_date_ms", String(params.endDateMs));

  const response = await fetch(url.toString(), {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new Error(`Failed to load Team Hours (${response.status}): ${detail}`);
  }

  return (await response.json()) as TeamHoursReport;
};
