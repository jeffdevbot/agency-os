import type { PnlImport } from "./pnlApi";

const PROGRESS_META_KEY = "async_import_progress_v1";

export type PnlImportProgress = {
  stage: string | null;
  detail: string | null;
  heartbeatAt: string | null;
  totalRawRows: number | null;
  totalMonths: number | null;
  monthsCompleted: number | null;
  monthsTotal: number | null;
  currentMonth: string | null;
  currentMonthRawRows: number | null;
  currentMonthLedgerRows: number | null;
  lastCompletedMonth: string | null;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

export function getPnlImportProgress(importRecord: PnlImport | null): PnlImportProgress | null {
  const rawMeta = asRecord(importRecord?.raw_meta);
  const progress = asRecord(rawMeta?.[PROGRESS_META_KEY]);
  if (!progress) {
    return null;
  }

  return {
    stage: asString(progress.stage),
    detail: asString(progress.detail),
    heartbeatAt: asString(progress.heartbeat_at),
    totalRawRows: asNumber(progress.total_raw_rows),
    totalMonths: asNumber(progress.total_months),
    monthsCompleted: asNumber(progress.months_completed),
    monthsTotal: asNumber(progress.months_total),
    currentMonth: asString(progress.current_month),
    currentMonthRawRows: asNumber(progress.current_month_raw_rows),
    currentMonthLedgerRows: asNumber(progress.current_month_ledger_rows),
    lastCompletedMonth: asString(progress.last_completed_month),
  };
}

function formatRelativeTime(timestamp: string | null): string | null {
  if (!timestamp) {
    return null;
  }
  const parsed = Date.parse(timestamp);
  if (Number.isNaN(parsed)) {
    return null;
  }

  const deltaSeconds = Math.round((parsed - Date.now()) / 1000);
  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  const absSeconds = Math.abs(deltaSeconds);
  if (absSeconds < 60) {
    return formatter.format(deltaSeconds, "second");
  }
  const deltaMinutes = Math.round(deltaSeconds / 60);
  if (Math.abs(deltaMinutes) < 60) {
    return formatter.format(deltaMinutes, "minute");
  }
  const deltaHours = Math.round(deltaMinutes / 60);
  if (Math.abs(deltaHours) < 24) {
    return formatter.format(deltaHours, "hour");
  }
  const deltaDays = Math.round(deltaHours / 24);
  return formatter.format(deltaDays, "day");
}

function formatMonthLabel(monthIso: string | null): string | null {
  if (!monthIso) {
    return null;
  }
  const parsed = new Date(`${monthIso}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) {
    return monthIso;
  }
  return new Intl.DateTimeFormat("en-CA", { month: "short", year: "numeric", timeZone: "UTC" }).format(parsed);
}

export function buildPnlImportProgressLines(importRecord: PnlImport | null): string[] {
  if (!importRecord) {
    return [];
  }

  const progress = getPnlImportProgress(importRecord);
  const lines: string[] = [];

  if (progress?.detail) {
    lines.push(progress.detail);
  }

  const scopeParts: string[] = [];
  if (progress?.totalRawRows !== null && progress?.totalRawRows !== undefined) {
    scopeParts.push(`${progress.totalRawRows.toLocaleString()} rows`);
  } else if (typeof importRecord.row_count === "number" && importRecord.row_count > 0) {
    scopeParts.push(`${importRecord.row_count.toLocaleString()} rows`);
  }
  if (progress?.totalMonths !== null && progress?.totalMonths !== undefined) {
    scopeParts.push(`${progress.totalMonths} month${progress.totalMonths === 1 ? "" : "s"}`);
  }
  if (scopeParts.length > 0) {
    lines.push(scopeParts.join(" across "));
  }

  const completionParts: string[] = [];
  if (progress && progress.monthsCompleted !== null && progress.monthsTotal !== null) {
    completionParts.push(`Months complete: ${progress.monthsCompleted}/${progress.monthsTotal}`);
  }
  const currentMonth = formatMonthLabel(progress?.currentMonth ?? null);
  if (currentMonth) {
    completionParts.push(`Current month: ${currentMonth}`);
  } else {
    const lastCompleted = formatMonthLabel(progress?.lastCompletedMonth ?? null);
    if (lastCompleted) {
      completionParts.push(`Last completed month: ${lastCompleted}`);
    }
  }
  if (completionParts.length > 0) {
    lines.push(completionParts.join(". "));
  }

  const heartbeat = formatRelativeTime(progress?.heartbeatAt ?? null);
  if (heartbeat) {
    lines.push(`Last worker update ${heartbeat}.`);
  }

  return lines;
}
