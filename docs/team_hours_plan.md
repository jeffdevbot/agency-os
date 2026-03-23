# Team Hours v1 Plan

_Drafted: 2026-03-23 (ET)_

## Purpose

Define the thin-slice implementation plan for `Team Hours`, an admin-only
Command Center surface for slicing ClickUp time entries by team member and
client/space.

This is intentionally an internal reporting feature, not a broad ClickUp
analytics platform.

## Product decision

### Name

Use `Team Hours`.

Reason:

1. clearer than `Hours Report`
2. narrow enough for the first slice
3. leaves room for later expansion into utilization/profitability without
   forcing that framing now

### Home

Put it under `Command Center` as a new admin-only page.

Suggested route:

- `/command-center/hours`

### Access

Use the current admin gate only.

Current reality:

1. platform access control is effectively `profiles.is_admin`
2. Command Center pages and APIs already use that gate
3. there is not currently a separate `super_admin` permission model

Recommendation:

1. keep `Team Hours` admin-only in v1
2. do not introduce `super_admin` yet
3. if a narrower permission is needed later, add it deliberately rather than
   inventing it for this first slice

## Why now

This is already the top `now` item in `docs/opportunity_backlog.md`.

Why it is a good next slice:

1. direct internal ops value
2. strong fit with Command Center
3. existing ClickUp, brand, and team-member mapping foundations already exist
4. can ship useful reporting without solving perfect attribution

## Current repo fit

Existing relevant foundations:

1. ClickUp API wrapper:
   - `backend-core/app/services/clickup.py`
2. Existing ClickUp router:
   - `backend-core/app/routers/clickup.py`
3. Command Center auth gate:
   - `frontend-web/src/lib/command-center/auth.ts`
4. Command Center home page:
   - `frontend-web/src/app/command-center/page.tsx`
5. Existing ClickUp/brand admin page:
   - `frontend-web/src/app/command-center/clickup-spaces/page.tsx`
6. Team profiles already store `clickup_user_id`
7. Brands already store `clickup_space_id` and `clickup_list_id`

Important gap:

1. current ClickUp integration supports task/space/list flows
2. there is no current time-entry reporting path

## Official ClickUp API shape

Primary source docs:

1. Get time entries within a date range:
   - `GET /api/v2/team/{team_Id}/time_entries`
2. Get Authorized Workspaces:
   - `GET /api/v2/team`
3. Get Spaces:
   - `GET /api/v2/team/{team_id}/space`
4. Date formatting guide:
   - timestamps use Unix time in milliseconds
5. Rate limits:
   - commonly `100 requests/minute` on Free/Unlimited/Business plans

Key implications from the docs:

1. ClickUp still uses the legacy term `team_id` in the API, but it means
   Workspace ID.
2. `GET /team/{team_Id}/time_entries` is the correct non-legacy endpoint for
   time entries.
3. By default that endpoint returns the authenticated user's recent time
   entries only.
4. To fetch time entries for other users, the request must include the
   `assignee` query parameter.
5. `assignee` supports comma-separated user IDs.
6. Only Workspace owners/admins can retrieve time entries for other users.
7. Only one location filter can be used at a time:
   `space_id`, `folder_id`, `list_id`, or `task_id`.
8. The response can include:
   - task metadata
   - task location
   - task tags
   - task URL
9. `include_location_names=true` returns list/folder/space names alongside the
   IDs.
10. `include_task_tags=true` returns task tags for future slicing, even if v1
    does not expose them yet.

## API-driven implementation recommendation

### Workspace/member resolution

Do not hardcode report scoping from local mappings alone.

Recommended sequence:

1. use configured ClickUp token + workspace/team id from the existing backend
   service
2. optionally validate the configured workspace via `GET /v2/team`
3. use the authorized workspace payload to obtain workspace members
4. collect ClickUp `user.id` values from that payload

Why:

1. the time-entry endpoint requires explicit `assignee` values to read hours
   for users other than the token owner
2. using workspace-member IDs lets us include users who are not yet linked to
   `profiles.clickup_user_id`
3. that is how we preserve visibility despite Command Center drift

### Time-entry fetch strategy

Recommended v1 fetch:

1. fetch by date range, not by space
2. pass all authorized workspace member IDs in `assignee`
3. pass:
   - `start_date`
   - `end_date`
   - `include_location_names=true`
   - `include_task_tags=true`
4. aggregate locally by:
   - ClickUp user
   - space
   - client / brand mapping

Why this shape:

1. the endpoint allows only one location filter at a time
2. querying per space would create unnecessary request fanout
3. the response already contains `task_location.space_id` and optional names
4. local aggregation is simpler and more tolerant of incomplete mappings

### Suggested internal normalized row shape

Each fetched time entry should be normalized into something like:

```ts
type TeamHoursEntry = {
  timeEntryId: string;
  workspaceId: string;
  clickupUserId: string | null;
  clickupUsername: string | null;
  clickupUserEmail: string | null;
  isBillable: boolean | null;
  startMs: number | null;
  endMs: number | null;
  durationMs: number;
  description: string | null;
  taskId: string | null;
  taskCustomId: string | null;
  taskName: string | null;
  taskUrl: string | null;
  spaceId: string | null;
  spaceName: string | null;
  folderId: string | null;
  folderName: string | null;
  listId: string | null;
  listName: string | null;
  taskTags: string[];
};
```

Then enrich that row with Agency OS mapping fields:

```ts
type TeamHoursEnrichedEntry = TeamHoursEntry & {
  teamMemberProfileId: string | null;
  teamMemberName: string | null;
  teamMemberEmail: string | null;
  teamMemberMapped: boolean;
  brandId: string | null;
  brandName: string | null;
  clientId: string | null;
  clientName: string | null;
  spaceMapped: boolean;
};
```

## Drift handling

This feature must be graceful under imperfect mappings.

### Missing team-member mapping

If a time entry user does not map to `profiles.clickup_user_id`:

1. keep the row
2. label the person as `Unlinked ClickUp User`
3. still show the raw ClickUp user name / email / ID when available
4. mark the row as unmapped in the API response

### Missing brand/space mapping

If `task_location.space_id` does not map to a Command Center brand:

1. keep the row
2. label it as `Unlinked Space`
3. still show raw ClickUp `space_id` and `space_name`
4. do not guess a client from partial text matching in v1

### Missing task/location entirely

Some time entries may not be attached to a task/location.

For those:

1. keep the row
2. label it as `No linked task/location`
3. exclude it from client/brand rollups unless/until a deterministic mapping
   rule is added later
4. still include it in user totals and an `unattributed` bucket

## v1 product shape

### Page behavior

Admin-only page in Command Center with:

1. date range picker
2. summary cards:
   - total hours
   - mapped hours
   - unmapped hours
   - unique team members
3. primary table grouped by team member
4. expandable or secondary breakdown by:
   - client
   - brand
   - space
5. explicit unmapped sections:
   - unlinked users
   - unlinked spaces
   - unattributed/no-task time
6. CSV export

### v1 filters

1. date range
2. team member
3. client
4. mapped-only vs all

### Not in v1

1. profitability / blended labor cost math
2. utilization %
3. tag analytics UI
4. task-level drilldown as the main surface
5. mutation workflows

## Backend slice

### New service methods

Add to `backend-core/app/services/clickup.py`:

1. `get_authorized_workspaces()`
2. `get_time_entries(...)`
3. optional helper to batch assignee lists if needed

The current service already has:

1. token handling
2. base URL
3. retries/backoff
4. rate-limiting

That makes it the right place to extend.

### New report service

Suggested new module:

- `backend-core/app/services/clickup_team_hours.py`

Responsibilities:

1. fetch raw ClickUp time entries
2. fetch/memoize Command Center mappings
3. normalize and enrich rows
4. aggregate into API-friendly report payloads

Keep this separate from the generic ClickUp transport client.

### Suggested backend route

Add an admin-only endpoint under the Next.js Command Center API surface first:

- `frontend-web/src/app/api/command-center/hours/route.ts`

Why Next API first:

1. matches the existing Command Center auth pattern
2. keeps the admin-only gate consistent with current Command Center routes
3. can proxy to backend-core if needed later, but does not force a new public
   backend route immediately

Alternative:

1. add a FastAPI backend route if the payload becomes large or reused elsewhere
2. keep the Next route as the authenticated admin proxy

## Frontend slice

Suggested new page:

- `frontend-web/src/app/command-center/hours/page.tsx`

Suggested home-page nav addition:

- add `Team Hours` card to `frontend-web/src/app/command-center/page.tsx`

Suggested initial UI sections:

1. header with date range and export
2. summary band
3. hours by team member table
4. hours by client/brand table
5. unmapped cleanup table

## Suggested response shape

```ts
type TeamHoursReportResponse = {
  dateRange: {
    startDateMs: number;
    endDateMs: number;
  };
  summary: {
    totalHours: number;
    mappedHours: number;
    unmappedHours: number;
    unattributedHours: number;
    uniqueUsers: number;
  };
  byTeamMember: Array<{
    clickupUserId: string | null;
    teamMemberProfileId: string | null;
    teamMemberName: string;
    mapped: boolean;
    totalHours: number;
    mappedHours: number;
    unmappedHours: number;
    clients: Array<{
      clientId: string | null;
      clientName: string;
      brandId: string | null;
      brandName: string | null;
      spaceId: string | null;
      spaceName: string | null;
      mapped: boolean;
      totalHours: number;
    }>;
  }>;
  unmappedUsers: Array<{
    clickupUserId: string | null;
    clickupUsername: string | null;
    clickupUserEmail: string | null;
    totalHours: number;
  }>;
  unmappedSpaces: Array<{
    spaceId: string | null;
    spaceName: string | null;
    totalHours: number;
  }>;
};
```

## Testing

### Backend

1. unit tests for ClickUp time-entry normalization
2. tests for team-member mapping via `profiles.clickup_user_id`
3. tests for space-to-brand/client mapping
4. tests for unmapped-user and unmapped-space buckets
5. tests for time entries without a task/location

### Frontend

1. auth gate test for admin-only access
2. page rendering test for mapped and unmapped sections
3. Command Center nav test for the new `Team Hours` link

## Main risks

1. ClickUp time-entry quality depends on disciplined logging behavior
2. some time may not be task-linked, which limits attribution
3. some spaces/users will drift from Command Center mappings
4. large date windows could increase payload size

## Recommendation

Build `Team Hours` now as:

1. admin-only
2. Command Center-hosted
3. date-range-based
4. tolerant of unmapped users/spaces
5. read-only reporting first

Do not expand into utilization, labor-rate math, or broad ClickUp analytics
until this thin slice proves useful.
