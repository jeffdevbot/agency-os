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

export type PnlOtherExpenseType = {
  key: string;
  label: string;
  enabled: boolean;
};

export type PnlOtherExpenseMonth = {
  entry_month: string;
  values: Record<string, string | null>;
};

export type PnlOtherExpenses = {
  expense_types: PnlOtherExpenseType[];
  months: PnlOtherExpenseMonth[];
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

export type ExportPnlWorkbookResult = {
  blob: Blob;
  filename: string;
};

export type PnlWindsorActiveImport = {
  import_month_id: string;
  import_id: string;
  source_type: string;
  source_filename: string | null;
  import_status: string;
  created_at: string | null;
  finished_at: string | null;
};

export type PnlWindsorBucketDelta = {
  bucket: string;
  csv_amount: string;
  windsor_amount: string;
  delta_amount: string;
};

export type PnlWindsorMarketplaceTotal = {
  marketplace_name: string;
  row_count: number;
  amount: string;
};

export type PnlWindsorComboSummary = {
  transaction_type: string;
  amount_type: string;
  amount_description: string;
  classification: string;
  bucket: string | null;
  reason: string | null;
  row_count: number;
  amount: string;
};

export type PnlWindsorCompare = {
  profile: Pick<PnlProfile, "id" | "client_id" | "marketplace_code" | "currency_code">;
  entry_month: string;
  date_from: string;
  date_to: string;
  windsor_account_id: string;
  csv_baseline: {
    active_imports: PnlWindsorActiveImport[];
    bucket_totals: Record<string, string>;
  };
  windsor: {
    row_count: number;
    mapped_row_count: number;
    ignored_row_count: number;
    unmapped_row_count: number;
    ignored_amount: string;
    unmapped_amount: string;
    bucket_totals: Record<string, string>;
    marketplace_totals: PnlWindsorMarketplaceTotal[];
    mapped_bucket_drilldowns: Array<{
      bucket: string;
      combo_totals: PnlWindsorComboSummary[];
      marketplace_totals: PnlWindsorMarketplaceTotal[];
    }>;
    top_unmapped_combos: PnlWindsorComboSummary[];
    top_ignored_combos: PnlWindsorComboSummary[];
  };
  comparison: {
    bucket_deltas: PnlWindsorBucketDelta[];
  };
};

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

const parseAttachmentFilename = (response: Response, fallback: string): string => {
  const disposition = response.headers.get("content-disposition") || "";
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }

  const basicMatch = disposition.match(/filename="?([^"]+)"?/i);
  return basicMatch?.[1] || fallback;
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

export async function exportPnlWorkbook(
  token: string,
  profileId: string,
  options?: {
    filterMode?: PnlFilterMode;
    startMonth?: string;
    endMonth?: string;
    showTotals?: boolean;
  },
): Promise<ExportPnlWorkbookResult> {
  const params = new URLSearchParams({
    filter_mode: options?.filterMode ?? "ytd",
    show_totals: String(options?.showTotals ?? true),
  });
  if (options?.startMonth) params.set("start_month", options.startMonth);
  if (options?.endMonth) params.set("end_month", options.endMonth);

  const response = await fetch(
    `${getBackendUrl()}/admin/pnl/profiles/${profileId}/export.xlsx?${params.toString()}`,
    {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
    },
  );
  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new Error(detail);
  }

  return {
    blob: await response.blob(),
    filename: parseAttachmentFilename(response, "amazon-pnl.xlsx"),
  };
}

export async function getPnlWindsorCompare(
  token: string,
  profileId: string,
  entryMonth: string,
): Promise<PnlWindsorCompare> {
  const params = new URLSearchParams({ entry_month: entryMonth });
  const response = await fetch(
    `${getBackendUrl()}/admin/pnl/profiles/${profileId}/windsor-compare?${params.toString()}`,
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
    profile: data.profile as PnlWindsorCompare["profile"],
    entry_month: String(data.entry_month ?? ""),
    date_from: String(data.date_from ?? ""),
    date_to: String(data.date_to ?? ""),
    windsor_account_id: String(data.windsor_account_id ?? ""),
    csv_baseline: {
      active_imports: (data?.csv_baseline?.active_imports ?? []) as PnlWindsorActiveImport[],
      bucket_totals: (data?.csv_baseline?.bucket_totals ?? {}) as Record<string, string>,
    },
    windsor: {
      row_count: Number(data?.windsor?.row_count ?? 0),
      mapped_row_count: Number(data?.windsor?.mapped_row_count ?? 0),
      ignored_row_count: Number(data?.windsor?.ignored_row_count ?? 0),
      unmapped_row_count: Number(data?.windsor?.unmapped_row_count ?? 0),
      ignored_amount: String(data?.windsor?.ignored_amount ?? "0.00"),
      unmapped_amount: String(data?.windsor?.unmapped_amount ?? "0.00"),
      bucket_totals: (data?.windsor?.bucket_totals ?? {}) as Record<string, string>,
      marketplace_totals: (data?.windsor?.marketplace_totals ?? []) as PnlWindsorMarketplaceTotal[],
      mapped_bucket_drilldowns: (data?.windsor?.mapped_bucket_drilldowns ?? []) as PnlWindsorCompare["windsor"]["mapped_bucket_drilldowns"],
      top_unmapped_combos: (data?.windsor?.top_unmapped_combos ?? []) as PnlWindsorComboSummary[],
      top_ignored_combos: (data?.windsor?.top_ignored_combos ?? []) as PnlWindsorComboSummary[],
    },
    comparison: {
      bucket_deltas: (data?.comparison?.bucket_deltas ?? []) as PnlWindsorBucketDelta[],
    },
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
): Promise<PnlSkuCogs[]> {
  const response = await fetch(
    `${getBackendUrl()}/admin/pnl/profiles/${profileId}/cogs-skus`,
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

export async function listPnlOtherExpenses(
  token: string,
  profileId: string,
  startMonth: string,
  endMonth: string,
): Promise<PnlOtherExpenses> {
  const params = new URLSearchParams({
    start_month: startMonth,
    end_month: endMonth,
  });
  const response = await fetch(
    `${getBackendUrl()}/admin/pnl/profiles/${profileId}/other-expenses?${params.toString()}`,
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
    expense_types: (data?.expense_types ?? []) as PnlOtherExpenseType[],
    months: (data?.months ?? []) as PnlOtherExpenseMonth[],
  };
}

export async function savePnlOtherExpenses(
  token: string,
  profileId: string,
  payload: {
    start_month: string;
    end_month: string;
    expense_types: Array<{ key: string; enabled: boolean }>;
    months: Array<{ entry_month: string; values: Record<string, string | null> }>;
  },
): Promise<void> {
  const response = await fetch(
    `${getBackendUrl()}/admin/pnl/profiles/${profileId}/other-expenses`,
    {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new Error(detail);
  }
}
