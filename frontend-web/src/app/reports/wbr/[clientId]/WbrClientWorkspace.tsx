"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

if (!BACKEND_URL) {
  throw new Error("NEXT_PUBLIC_BACKEND_URL is not configured");
}

type DailyRow = {
  report_date: string;
  currency_code: string;
  page_views: number;
  unit_sales: number;
  sales: number;
};

type WeeklyTotalRow = {
  week_start: string;
  week_end: string;
  currency_code: string;
  page_views: number;
  unit_sales: number;
  sales: number;
  unit_conversions_pct: number;
};

type Props = {
  clientId: string;
};

const asNumber = (value: unknown): number => {
  if (typeof value === "number") return value;
  if (typeof value === "string" && value.trim() !== "") return Number(value);
  return 0;
};

const toIsoDate = (date: Date): string => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const parseIsoToLocalDate = (value: string): Date | null => {
  const parts = value.split("-").map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) return null;
  const [year, month, day] = parts;
  const d = new Date(year, month - 1, day);
  if (Number.isNaN(d.getTime())) return null;
  return d;
};

const weekBoundsFromReportDate = (reportDateIso: string): { weekStart: string; weekEnd: string } | null => {
  const reportDate = parseIsoToLocalDate(reportDateIso);
  if (!reportDate) return null;

  const weekStartDate = new Date(
    reportDate.getFullYear(),
    reportDate.getMonth(),
    reportDate.getDate() - reportDate.getDay()
  );
  const weekEndDate = new Date(
    weekStartDate.getFullYear(),
    weekStartDate.getMonth(),
    weekStartDate.getDate() + 6
  );

  return {
    weekStart: toIsoDate(weekStartDate),
    weekEnd: toIsoDate(weekEndDate),
  };
};

const formatDate = (value: string): string => {
  const d = parseIsoToLocalDate(value);
  if (!d) return value;
  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "short",
    day: "2-digit",
  }).format(d);
};

const currentWeekStartIso = (): string => {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - now.getDay());
  return toIsoDate(start);
};

export default function WbrClientWorkspace({ clientId }: Props) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [accountId, setAccountId] = useState("A1MY3C51FMRZ3Z-CA");
  const [weeks, setWeeks] = useState(4);
  const [isBackfilling, setIsBackfilling] = useState(false);
  const [isLoadingRows, setIsLoadingRows] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [runSummary, setRunSummary] = useState<string | null>(null);
  const [rows, setRows] = useState<DailyRow[]>([]);

  const totalRows = useMemo(() => {
    const thisWeekStart = currentWeekStartIso();
    const byWeek = new Map<string, WeeklyTotalRow>();

    for (const row of rows) {
      const bounds = weekBoundsFromReportDate(row.report_date);
      if (!bounds) continue;
      if (bounds.weekStart >= thisWeekStart) continue;

      const key = `${bounds.weekStart}|${bounds.weekEnd}|${row.currency_code}`;
      const existing = byWeek.get(key);
      if (!existing) {
        byWeek.set(key, {
          week_start: bounds.weekStart,
          week_end: bounds.weekEnd,
          currency_code: row.currency_code,
          page_views: row.page_views,
          unit_sales: row.unit_sales,
          sales: row.sales,
          unit_conversions_pct: 0,
        });
        continue;
      }

      existing.page_views += row.page_views;
      existing.unit_sales += row.unit_sales;
      existing.sales += row.sales;
    }

    const totals = Array.from(byWeek.values());
    for (const total of totals) {
      total.unit_conversions_pct = total.page_views > 0 ? total.unit_sales / total.page_views : 0;
    }

    totals.sort((a, b) => b.week_start.localeCompare(a.week_start));
    return totals.slice(0, weeks);
  }, [rows, weeks]);

  const loadWeeklyRows = useCallback(async () => {
    setIsLoadingRows(true);
    setErrorMessage(null);

    const query = supabase
      .from("wbr_section1_daily")
      .select("report_date,currency_code,page_views,unit_sales,sales")
      .eq("client_id", clientId)
      .order("report_date", { ascending: false });

    const scopedQuery = accountId.trim() ? query.eq("account_id", accountId.trim()) : query;
    const { data, error } = await scopedQuery;
    if (error) {
      setErrorMessage(error.message);
      setRows([]);
      setIsLoadingRows(false);
      return;
    }

    const parsed: DailyRow[] = (data ?? []).map((row: Record<string, unknown>) => ({
      report_date: String(row.report_date ?? ""),
      currency_code: String(row.currency_code ?? ""),
      page_views: asNumber(row.page_views),
      unit_sales: asNumber(row.unit_sales),
      sales: asNumber(row.sales),
    }));

    setRows(parsed);
    setIsLoadingRows(false);
  }, [accountId, clientId, supabase]);

  const runBackfill = useCallback(async () => {
    if (!accountId.trim()) {
      setErrorMessage("Account ID is required");
      return;
    }

    setIsBackfilling(true);
    setErrorMessage(null);
    setRunSummary(null);

    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session?.access_token) {
        setErrorMessage("Please sign in again.");
        setIsBackfilling(false);
        return;
      }

      const response = await fetch(`${BACKEND_URL}/admin/wbr/section1/backfill-last-full-weeks`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          client_id: clientId,
          account_id: accountId.trim(),
          weeks,
        }),
      });

      const json = (await response.json()) as {
        detail?: string;
        results?: Array<{ rows_loaded?: number; date_from?: string; date_to?: string }>;
      };

      if (!response.ok) {
        throw new Error(json.detail ?? "Backfill failed");
      }

      const chunks = json.results ?? [];
      const rowsLoaded = chunks.reduce((sum, item) => sum + (item.rows_loaded ?? 0), 0);
      setRunSummary(`Backfill completed: ${chunks.length} chunks, ${rowsLoaded} rows loaded.`);
      await loadWeeklyRows();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Backfill failed");
    } finally {
      setIsBackfilling(false);
    }
  }, [accountId, clientId, loadWeeklyRows, supabase, weeks]);

  return (
    <main className="space-y-4">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-2xl font-semibold text-[#0f172a]">WBR Client Workspace</h1>
        <p className="mt-2 text-sm text-[#4c576f]">Client ID: {clientId}</p>

        <div className="mt-6 grid gap-4 rounded-2xl border border-[#c7d8f5] bg-[#f7faff] p-5 md:grid-cols-3">
          <label className="text-sm">
            <span className="mb-1 block font-semibold text-[#0f172a]">Account ID</span>
            <input
              value={accountId}
              onChange={(event) => setAccountId(event.target.value)}
              placeholder="A1MY3C51FMRZ3Z-CA"
              className="w-full rounded-xl border border-[#c7d8f5] bg-white px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block font-semibold text-[#0f172a]">Weeks</span>
            <input
              type="number"
              min={1}
              max={8}
              value={weeks}
              onChange={(event) => setWeeks(Number(event.target.value) || 4)}
              className="w-full rounded-xl border border-[#c7d8f5] bg-white px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
            />
          </label>
          <div className="flex items-end gap-3">
            <button
              onClick={runBackfill}
              disabled={isBackfilling || !accountId.trim()}
              className="w-full rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-[#b7cbea]"
            >
              {isBackfilling ? "Running backfill..." : "Backfill Last Full Weeks"}
            </button>
            <button
              onClick={loadWeeklyRows}
              disabled={isLoadingRows}
              className="w-full rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
            >
              {isLoadingRows ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </div>

        {runSummary ? (
          <p className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            {runSummary}
          </p>
        ) : null}

        {errorMessage ? (
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {errorMessage}
          </p>
        ) : null}

        <div className="mt-6 overflow-x-auto rounded-2xl border border-slate-200 bg-white">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-[#f7faff]">
              <tr className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">
                <th className="px-4 py-3">Week</th>
                <th className="px-4 py-3">Page Views</th>
                <th className="px-4 py-3">Unit Sales</th>
                <th className="px-4 py-3">Unit Conv %</th>
                <th className="px-4 py-3">Sales</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white">
              {totalRows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-sm text-[#64748b]">
                    No rows yet. Run backfill and then click refresh.
                  </td>
                </tr>
              ) : (
                totalRows.map((row, index) => (
                  <tr key={`${row.week_start}-${index}`} className="hover:bg-slate-50">
                    <td className="px-4 py-3 text-[#0f172a]">
                      {formatDate(row.week_start)} to {formatDate(row.week_end)}
                    </td>
                    <td className="px-4 py-3 text-[#0f172a]">{row.page_views.toLocaleString()}</td>
                    <td className="px-4 py-3 text-[#0f172a]">{row.unit_sales.toLocaleString()}</td>
                    <td className="px-4 py-3 text-[#0f172a]">
                      {(row.unit_conversions_pct * 100).toFixed(2)}%
                    </td>
                    <td className="px-4 py-3 text-[#0f172a]">
                      {row.currency_code}{" "}
                      {row.sales.toLocaleString(undefined, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/reports/wbr/setup"
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            Back to Setup
          </Link>
          <Link
            href="/reports/wbr"
            className="rounded-2xl bg-[#e8eefc] px-4 py-3 text-sm font-semibold text-[#0f172a] transition hover:bg-[#d7e1fb]"
          >
            Back to WBR
          </Link>
        </div>
      </div>
    </main>
  );
}
