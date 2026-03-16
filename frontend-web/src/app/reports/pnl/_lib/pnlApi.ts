/**
 * P&L API client — types and fetch helpers for the Monthly P&L report.
 */

// ── Types ────────────────────────────────────────────────────────────

export type PnlProfile = {
  id: string;
  client_id: string;
  marketplace_code: string;
  currency_code: string;
  status: string;
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type PnlLineItem = {
  key: string;
  label: string;
  category: string;
  is_derived: boolean;
  months: Record<string, string>; // month ISO → amount string
};

export type PnlWarning = {
  type: string;
  message: string;
  months: string[];
};

export type PnlReport = {
  profile: PnlProfile;
  months: string[];
  line_items: PnlLineItem[];
  warnings: PnlWarning[];
};

export type PnlFilterMode = "ytd" | "last_3" | "last_6" | "last_12" | "range";

// ── Helpers ──────────────────────────────────────────────────────────

const getBackendUrl = (): string => {
  const url = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (!url) throw new Error("NEXT_PUBLIC_BACKEND_URL is not configured");
  return url.replace(/\/+$/, "");
};

const parseErrorDetail = async (response: Response): Promise<string> => {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    if (typeof body?.message === "string") return body.message;
    return JSON.stringify(body);
  } catch {
    return response.statusText || `HTTP ${response.status}`;
  }
};

// ── API calls ────────────────────────────────────────────────────────

export async function listPnlProfiles(
  token: string,
  clientId: string,
): Promise<PnlProfile[]> {
  const query = new URLSearchParams({ client_id: clientId });
  const response = await fetch(
    `${getBackendUrl()}/admin/pnl/profiles?${query.toString()}`,
    { method: "GET", headers: { Authorization: `Bearer ${token}` } },
  );
  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new Error(detail);
  }
  const data = await response.json();
  return (data?.profiles ?? []) as PnlProfile[];
}

export async function getPnlReport(
  token: string,
  profileId: string,
  filterMode: PnlFilterMode = "ytd",
  startMonth?: string,
  endMonth?: string,
): Promise<PnlReport> {
  const params = new URLSearchParams({ filter_mode: filterMode });
  if (startMonth) params.set("start_month", startMonth);
  if (endMonth) params.set("end_month", endMonth);

  const response = await fetch(
    `${getBackendUrl()}/admin/pnl/profiles/${profileId}/report?${params.toString()}`,
    { method: "GET", headers: { Authorization: `Bearer ${token}` } },
  );
  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new Error(detail);
  }
  const data = await response.json();
  return {
    profile: data.profile as PnlProfile,
    months: (data.months ?? []) as string[],
    line_items: (data.line_items ?? []) as PnlLineItem[],
    warnings: (data.warnings ?? []) as PnlWarning[],
  };
}
