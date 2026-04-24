"use client";

import { useMemo, useState } from "react";
import type { BackfillRange, BackfillRowState, DomainCoverage } from "./types";

export type DomainBackfillVariant =
  | "active"
  | "read_only"
  | "coming_soon"
  | "needs_connection";

type Props = {
  domain: "Business" | "Ads" | "Listings" | "Inventory" | "Returns";
  variant: DomainBackfillVariant;
  coverage: DomainCoverage;
  rowState?: BackfillRowState;
  onRun?(range: BackfillRange): void;
  onRetry?(): void;
};

const isoDateDaysAgo = (daysAgo: number): string => {
  const now = new Date();
  const utc = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() - daysAgo);
  return new Date(utc).toISOString().slice(0, 10);
};

const defaultRange = (): BackfillRange => ({
  dateFrom: isoDateDaysAgo(5),
  dateTo: isoDateDaysAgo(3),
});

const formatCoverageDate = (value: string | null): string => {
  if (!value) return "—";
  const parsed = value.includes("T") ? new Date(value) : new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-CA", {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(parsed);
};

const variantReason: Record<Exclude<DomainBackfillVariant, "active">, string> = {
  read_only: "Managed by nightly sync",
  coming_soon: "Coming soon — Slice 3f",
  needs_connection: "Connect SP-API to enable",
};

function BackfillDateRangeDialog({
  domain,
  running,
  onRun,
}: {
  domain: string;
  running: boolean;
  onRun(range: BackfillRange): void;
}) {
  const initialRange = useMemo(defaultRange, []);
  const [open, setOpen] = useState(false);
  const [dateFrom, setDateFrom] = useState(initialRange.dateFrom);
  const [dateTo, setDateTo] = useState(initialRange.dateTo);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        disabled={running}
        className="rounded-xl bg-slate-950 px-3 py-2 text-xs font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        {running ? "Running..." : "Run backfill"}
      </button>
      {open ? (
        <div className="absolute right-0 z-20 mt-2 w-72 rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-2xl">
          <p className="text-sm font-semibold text-slate-950">Run {domain} backfill</p>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <label className="text-xs font-semibold text-slate-600">
              From
              <input
                type="date"
                value={dateFrom}
                onChange={(event) => setDateFrom(event.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-2 text-sm text-slate-950"
              />
            </label>
            <label className="text-xs font-semibold text-slate-600">
              To
              <input
                type="date"
                value={dateTo}
                onChange={(event) => setDateTo(event.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-2 text-sm text-slate-950"
              />
            </label>
          </div>
          <p className="mt-3 text-xs text-slate-500">
            Defaults to three days ending three days ago to avoid fresh Amazon validation gaps.
          </p>
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-lg px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                onRun({ dateFrom, dateTo });
              }}
              className="rounded-lg bg-[#0a6fd6] px-3 py-2 text-xs font-semibold text-white hover:bg-[#075bad]"
            >
              Run
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default function DomainBackfillRow({
  domain,
  variant,
  coverage,
  rowState,
  onRun,
  onRetry,
}: Props) {
  const disabled = variant !== "active";
  const latest = formatCoverageDate(coverage.latest);
  const reason = disabled ? variantReason[variant] : null;

  return (
    <div
      className={`rounded-2xl border px-4 py-3 ${
        disabled
          ? "border-slate-100 bg-slate-50/70 text-slate-400"
          : "border-slate-200 bg-white text-slate-800"
      }`}
    >
      <div className="grid gap-3 md:grid-cols-[minmax(120px,1fr)_minmax(150px,1fr)_auto] md:items-start">
        <div>
          <p className={`text-sm font-semibold ${disabled ? "text-slate-400" : "text-slate-950"}`}>
            {domain}
          </p>
          {domain === "Business" && variant === "active" ? (
            <p className="mt-1 max-w-md text-xs text-slate-500">
              A/B compare against Windsor. Production data still flows through nightly sync.
            </p>
          ) : null}
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
            Last backfilled
          </p>
          <p className={`mt-1 text-sm font-medium ${disabled ? "text-slate-400" : "text-slate-700"}`}>
            {latest}
          </p>
        </div>
        <div className="md:text-right">
          {variant === "active" && onRun ? (
            <BackfillDateRangeDialog
              domain={domain}
              running={rowState?.running === true}
              onRun={onRun}
            />
          ) : (
            <p className="rounded-xl border border-slate-200 bg-white/70 px-3 py-2 text-xs font-semibold text-slate-500">
              {reason}
            </p>
          )}
        </div>
      </div>
      {rowState?.successMessage ? (
        <p className="mt-3 text-xs font-semibold text-emerald-700">{rowState.successMessage}</p>
      ) : null}
      {rowState?.errorMessage ? (
        <div className="mt-3 flex flex-wrap items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2">
          <p className="text-xs font-semibold text-rose-900">{rowState.errorMessage}</p>
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              disabled={rowState.running}
              className="rounded-lg bg-white px-2 py-1 text-xs font-semibold text-rose-700 hover:bg-rose-100 disabled:cursor-not-allowed disabled:text-slate-400"
            >
              Retry
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
