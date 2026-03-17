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

export type CreatePnlProfileRequest = {
  clientId: string;
  marketplaceCode: string;
  currencyCode?: string;
  notes?: string | null;
};

export type PnlImportMonth = {
  id: string;
  import_id: string | null;
  entry_month: string;
  import_status: string;
  is_active: boolean;
  raw_row_count: number;
  ledger_row_count: number;
  mapped_amount: string;
  unmapped_amount: string;
};

export type PnlImport = {
  id: string;
  profile_id: string;
  source_type: string;
  source_filename: string | null;
  import_status: string;
  row_count: number;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  raw_meta?: Record<string, unknown> | null;
};

export type PnlUploadResult = {
  import: PnlImport;
  months: PnlImportMonth[];
};

export type PnlImportSummary = {
  import: PnlImport;
  months: PnlImportMonth[];
};

export type PnlSkuCogs = {
  sku: string;
  unit_cost: string | null;
  months: Record<string, number>;
  total_units: number;
  missing_cost: boolean;
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
  skus?: string[];
};

export type PnlReport = {
  profile: PnlProfile;
  months: string[];
  line_items: PnlLineItem[];
  warnings: PnlWarning[];
};

export type PnlFilterMode = "ytd" | "last_3" | "last_6" | "last_12" | "last_year" | "range";

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

export async function listPnlImports(
  token: string,
  profileId: string,
): Promise<PnlImport[]> {
  const response = await fetch(`${getBackendUrl()}/admin/pnl/profiles/${profileId}/imports`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new Error(detail);
  }
  const data = await response.json();
  return (data?.imports ?? []) as PnlImport[];
}

export async function listPnlImportMonths(
  token: string,
  profileId: string,
): Promise<PnlImportMonth[]> {
  const response = await fetch(
    `${getBackendUrl()}/admin/pnl/profiles/${profileId}/import-months`,
    {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
    },
  );
  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new Error(detail);
  }
  const data = await response.json();
  return (data?.months ?? []) as PnlImportMonth[];
}

export async function createPnlProfile(
  token: string,
  request: CreatePnlProfileRequest,
): Promise<PnlProfile> {
  const response = await fetch(
    `${getBackendUrl()}/admin/pnl/profiles`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        client_id: request.clientId,
        marketplace_code: request.marketplaceCode,
        currency_code: request.currencyCode ?? "USD",
        notes: request.notes ?? null,
      }),
    },
  );

  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new Error(detail);
  }

  const data = await response.json();
  return data.profile as PnlProfile;
}

export async function uploadPnlTransactionReport(
  token: string,
  profileId: string,
  file: File,
): Promise<PnlUploadResult> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(
    `${getBackendUrl()}/admin/pnl/profiles/${profileId}/transaction-upload`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    },
  );

  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new Error(detail);
  }

  const data = await response.json();
  return {
    import: data.import as PnlImport,
    months: (data.months ?? []) as PnlImportMonth[],
  };
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

export async function getPnlImportSummary(
  token: string,
  profileId: string,
  importId: string,
): Promise<PnlImportSummary> {
  const response = await fetch(
    `${getBackendUrl()}/admin/pnl/profiles/${profileId}/imports/${importId}`,
    {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
    },
  );
  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new Error(detail);
  }
  const data = await response.json();
  return {
    import: data.import as PnlImport,
    months: (data.months ?? []) as PnlImportMonth[],
  };
}

export async function listPnlSkuCogs(
  token: string,
  profileId: string,
  startMonth: string,
  endMonth: string,
): Promise<PnlSkuCogs[]> {
  const params = new URLSearchParams({
    start_month: startMonth,
    end_month: endMonth,
  });
  const response = await fetch(
    `${getBackendUrl()}/admin/pnl/profiles/${profileId}/cogs-skus?${params.toString()}`,
    {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
    },
  );
  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new Error(detail);
  }
  const data = await response.json();
  return (data?.skus ?? []) as PnlSkuCogs[];
}

export async function savePnlSkuCogs(
  token: string,
  profileId: string,
  entries: Array<{ sku: string; unit_cost: string | null }>,
): Promise<void> {
  const response = await fetch(
    `${getBackendUrl()}/admin/pnl/profiles/${profileId}/cogs-skus`,
    {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ entries }),
    },
  );
  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new Error(detail);
  }
}
