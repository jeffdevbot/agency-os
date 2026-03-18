"use client";

import { useEffect, useMemo, useState } from "react";
import type {
  PnlWindsorBucketDelta,
  PnlWindsorComboSummary,
  PnlWindsorCompare,
} from "../pnl/_lib/pnlApi";
import {
  describeImportSource,
  formatAmount,
  formatImportSourceType,
  formatMonth,
} from "../pnl/_lib/pnlDisplay";

type Props = {
  entryMonth: string;
  comparison: PnlWindsorCompare | null;
  loading: boolean;
  errorMessage: string | null;
  onEntryMonthChange: (entryMonth: string) => void;
  onRunCompare: () => void;
};

function toMonthInputValue(entryMonth: string): string {
  return /^\d{4}-\d{2}-01$/.test(entryMonth) ? entryMonth.slice(0, 7) : "";
}

function fromMonthInputValue(value: string): string {
  return /^\d{4}-\d{2}$/.test(value) ? `${value}-01` : value;
}

function deltaClass(amount: string): string {
  const parsed = Number.parseFloat(amount);
  if (Number.isNaN(parsed) || parsed === 0) return "text-[#64748b]";
  return parsed > 0 ? "text-[#14532d]" : "text-[#991b1b]";
}

function renderComboLabel(combo: PnlWindsorComboSummary): string {
  return [combo.transaction_type, combo.amount_type, combo.amount_description]
    .filter((value) => value.trim().length > 0)
    .join(" / ");
}

function formatBucketLabel(bucket: string): string {
  return bucket
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function renderBucketRows(bucketDeltas: PnlWindsorBucketDelta[]) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-[#dbe4f0]">
      <table className="min-w-full divide-y divide-[#dbe4f0] text-sm">
        <thead className="bg-[#f8fafc] text-left text-xs uppercase tracking-[0.14em] text-[#64748b]">
          <tr>
            <th className="px-4 py-3 font-semibold">Bucket</th>
            <th className="px-4 py-3 font-semibold">CSV</th>
            <th className="px-4 py-3 font-semibold">Windsor</th>
            <th className="px-4 py-3 font-semibold">Delta</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[#e2e8f0] bg-white text-[#0f172a]">
          {bucketDeltas.map((row) => (
            <tr key={row.bucket}>
              <td className="px-4 py-3 font-medium">{row.bucket}</td>
              <td className="px-4 py-3">{formatAmount(row.csv_amount)}</td>
              <td className="px-4 py-3">{formatAmount(row.windsor_amount)}</td>
              <td className={`px-4 py-3 font-semibold ${deltaClass(row.delta_amount)}`}>
                {formatAmount(row.delta_amount)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function PnlWindsorCompareCard({
  entryMonth,
  comparison,
  loading,
  errorMessage,
  onEntryMonthChange,
  onRunCompare,
}: Props) {
  const [selectedBucket, setSelectedBucket] = useState<string>("");
  const bucketDeltas = useMemo(
    () => comparison?.comparison.bucket_deltas ?? [],
    [comparison],
  );
  const topDeltas = useMemo(
    () => bucketDeltas.filter((row) => Number.parseFloat(row.delta_amount) !== 0).slice(0, 12),
    [bucketDeltas],
  );
  const mappedBucketDrilldowns = useMemo(
    () => comparison?.windsor.mapped_bucket_drilldowns ?? [],
    [comparison],
  );
  const selectedBucketDrilldown = useMemo(
    () => mappedBucketDrilldowns.find((row) => row.bucket === selectedBucket) ?? null,
    [mappedBucketDrilldowns, selectedBucket],
  );
  const monthInputValue = toMonthInputValue(entryMonth);

  useEffect(() => {
    const preferredBucket = topDeltas[0]?.bucket ?? mappedBucketDrilldowns[0]?.bucket ?? "";
    setSelectedBucket(preferredBucket);
  }, [comparison, mappedBucketDrilldowns, topDeltas]);

  return (
    <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[#0f172a]">Windsor settlement compare</h2>
          <p className="mt-1 max-w-3xl text-sm text-[#475569]">
            Pull one month from Windsor.ai and compare it against the active CSV-backed Monthly
            P&amp;L month without replacing the current source of truth.
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <label className="text-sm text-[#334155]">
            <span className="mb-1 block font-medium">Month</span>
            <input
              type="month"
              value={monthInputValue}
              onChange={(event) => onEntryMonthChange(fromMonthInputValue(event.target.value))}
              className="w-full rounded-xl border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0f172a] outline-none transition focus:border-[#0a6fd6] focus:ring-2 focus:ring-[#0a6fd6]/20"
            />
          </label>
          <button
            type="button"
            onClick={onRunCompare}
            disabled={loading || monthInputValue.length === 0}
            className="rounded-full bg-[#0a6fd6] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#0859ab] disabled:cursor-not-allowed disabled:bg-[#93c5fd]"
          >
            {loading ? "Comparing..." : "Run compare"}
          </button>
        </div>
      </div>

      {errorMessage ? (
        <div className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
          {errorMessage}
        </div>
      ) : null}

      {!comparison && !loading && !errorMessage ? (
        <p className="mt-4 text-sm text-[#64748b]">
          Choose a month with an active CSV import, then run the Windsor comparison to inspect
          bucket deltas, marketplaces, and unmapped combinations.
        </p>
      ) : null}

      {comparison ? (
        <div className="mt-5 space-y-5">
          <div className="flex flex-wrap gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#334155]">
            <span className="rounded-full border border-[#cbd5e1] bg-[#f8fafc] px-3 py-1">
              {formatMonth(comparison.entry_month)}
            </span>
            <span className="rounded-full border border-[#cbd5e1] bg-[#f8fafc] px-3 py-1">
              Windsor account {comparison.windsor_account_id}
            </span>
            <span className="rounded-full border border-[#cbd5e1] bg-[#f8fafc] px-3 py-1">
              {comparison.profile.marketplace_code} profile
            </span>
          </div>

          <div className="grid gap-3 md:grid-cols-5">
            <div className="rounded-2xl border border-[#dbe4f0] bg-[#f8fafc] p-4">
              <p className="text-xs uppercase tracking-[0.14em] text-[#64748b]">Rows</p>
              <p className="mt-2 text-2xl font-semibold text-[#0f172a]">
                {comparison.windsor.row_count.toLocaleString("en-US")}
              </p>
            </div>
            <div className="rounded-2xl border border-[#dbe4f0] bg-[#f8fafc] p-4">
              <p className="text-xs uppercase tracking-[0.14em] text-[#64748b]">Mapped</p>
              <p className="mt-2 text-2xl font-semibold text-[#0f172a]">
                {comparison.windsor.mapped_row_count.toLocaleString("en-US")}
              </p>
            </div>
            <div className="rounded-2xl border border-[#dbe4f0] bg-[#f8fafc] p-4">
              <p className="text-xs uppercase tracking-[0.14em] text-[#64748b]">Ignored</p>
              <p className="mt-2 text-2xl font-semibold text-[#0f172a]">
                {comparison.windsor.ignored_row_count.toLocaleString("en-US")}
              </p>
              <p className="mt-1 text-sm text-[#64748b]">
                {formatAmount(comparison.windsor.ignored_amount)}
              </p>
            </div>
            <div className="rounded-2xl border border-[#dbe4f0] bg-[#f8fafc] p-4">
              <p className="text-xs uppercase tracking-[0.14em] text-[#64748b]">Unmapped</p>
              <p className="mt-2 text-2xl font-semibold text-[#0f172a]">
                {comparison.windsor.unmapped_row_count.toLocaleString("en-US")}
              </p>
              <p className="mt-1 text-sm text-[#64748b]">
                {formatAmount(comparison.windsor.unmapped_amount)}
              </p>
            </div>
            <div className="rounded-2xl border border-[#dbe4f0] bg-[#f8fafc] p-4">
              <p className="text-xs uppercase tracking-[0.14em] text-[#64748b]">Active CSV imports</p>
              <p className="mt-2 text-2xl font-semibold text-[#0f172a]">
                {comparison.csv_baseline.active_imports.length.toLocaleString("en-US")}
              </p>
            </div>
          </div>

          {comparison.csv_baseline.active_imports.length > 0 ? (
            <div className="grid gap-3 lg:grid-cols-2">
              {comparison.csv_baseline.active_imports.map((activeImport) => (
                <div
                  key={activeImport.import_month_id}
                  className="rounded-2xl border border-[#dbe4f0] bg-[#f8fafc] p-4"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full border border-[#cbd5e1] bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-[#334155]">
                      {formatImportSourceType(activeImport.source_type)}
                    </span>
                    <span className="rounded-full bg-[#e2e8f0] px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-[#475569]">
                      {activeImport.import_status}
                    </span>
                  </div>
                  <p className="mt-3 text-sm font-semibold text-[#0f172a]">
                    {describeImportSource(activeImport.source_type, activeImport.source_filename)}
                  </p>
                  <p className="mt-2 break-all font-mono text-xs text-[#475569]">
                    {activeImport.import_id}
                  </p>
                </div>
              ))}
            </div>
          ) : null}

          <div>
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold text-[#0f172a]">Bucket deltas</h3>
                <p className="mt-1 text-sm text-[#64748b]">
                  Windsor minus the active CSV baseline for the same month.
                </p>
              </div>
              <p className="text-sm text-[#64748b]">
                Showing {topDeltas.length > 0 ? topDeltas.length : bucketDeltas.length} bucket
                {bucketDeltas.length === 1 ? "" : "s"}
              </p>
            </div>
            {renderBucketRows(topDeltas.length > 0 ? topDeltas : bucketDeltas)}
          </div>

          <div className="grid gap-5 xl:grid-cols-2">
            <div>
              <h3 className="text-base font-semibold text-[#0f172a]">Marketplace totals</h3>
              <div className="mt-3 space-y-2">
                {comparison.windsor.marketplace_totals.map((row) => (
                  <div
                    key={row.marketplace_name}
                    className="flex items-center justify-between gap-3 rounded-2xl border border-[#dbe4f0] bg-[#f8fafc] px-4 py-3 text-sm"
                  >
                    <div>
                      <p className="font-medium text-[#0f172a]">{row.marketplace_name}</p>
                      <p className="text-[#64748b]">{row.row_count.toLocaleString("en-US")} rows</p>
                    </div>
                    <p className="font-semibold text-[#0f172a]">{formatAmount(row.amount)}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-5">
              <div>
                <h3 className="text-base font-semibold text-[#0f172a]">Top unmapped combos</h3>
                {comparison.windsor.top_unmapped_combos.length === 0 ? (
                  <p className="mt-3 text-sm text-[#64748b]">No unmapped combinations in this pull.</p>
                ) : (
                  <div className="mt-3 space-y-2">
                    {comparison.windsor.top_unmapped_combos.slice(0, 8).map((combo) => (
                      <div
                        key={`${combo.transaction_type}-${combo.amount_type}-${combo.amount_description}`}
                        className="rounded-2xl border border-[#dbe4f0] bg-[#f8fafc] px-4 py-3 text-sm"
                      >
                        <p className="font-medium text-[#0f172a]">{renderComboLabel(combo)}</p>
                        <p className="mt-1 text-[#64748b]">
                          {combo.row_count.toLocaleString("en-US")} rows
                          {" · "}
                          {formatAmount(combo.amount)}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <h3 className="text-base font-semibold text-[#0f172a]">Top ignored combos</h3>
                {comparison.windsor.top_ignored_combos.length === 0 ? (
                  <p className="mt-3 text-sm text-[#64748b]">No ignored combinations in this pull.</p>
                ) : (
                  <div className="mt-3 space-y-2">
                    {comparison.windsor.top_ignored_combos.slice(0, 8).map((combo) => (
                      <div
                        key={`${combo.transaction_type}-${combo.amount_type}-${combo.amount_description}`}
                        className="rounded-2xl border border-[#dbe4f0] bg-[#f8fafc] px-4 py-3 text-sm"
                      >
                        <p className="font-medium text-[#0f172a]">{renderComboLabel(combo)}</p>
                        <p className="mt-1 text-[#64748b]">
                          {combo.row_count.toLocaleString("en-US")} rows
                          {" · "}
                          {formatAmount(combo.amount)}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {mappedBucketDrilldowns.length > 0 ? (
            <div className="grid gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,0.9fr)]">
              <div>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <h3 className="text-base font-semibold text-[#0f172a]">Bucket drilldown</h3>
                    <p className="mt-1 text-sm text-[#64748b]">
                      Inspect the Windsor combo mix behind one mapped bucket.
                    </p>
                  </div>
                  <label className="text-sm text-[#334155]">
                    <span className="mb-1 block font-medium">Bucket</span>
                    <select
                      value={selectedBucket}
                      onChange={(event) => setSelectedBucket(event.target.value)}
                      className="rounded-xl border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0f172a] outline-none transition focus:border-[#0a6fd6] focus:ring-2 focus:ring-[#0a6fd6]/20"
                    >
                      {mappedBucketDrilldowns.map((row) => (
                        <option key={row.bucket} value={row.bucket}>
                          {formatBucketLabel(row.bucket)}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                {selectedBucketDrilldown ? (
                  <div className="mt-3 overflow-x-auto rounded-2xl border border-[#dbe4f0]">
                    <table className="min-w-full divide-y divide-[#dbe4f0] text-sm">
                      <thead className="bg-[#f8fafc] text-left text-xs uppercase tracking-[0.14em] text-[#64748b]">
                        <tr>
                          <th className="px-4 py-3 font-semibold">Combo</th>
                          <th className="px-4 py-3 font-semibold">Rows</th>
                          <th className="px-4 py-3 font-semibold">Amount</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#e2e8f0] bg-white text-[#0f172a]">
                        {selectedBucketDrilldown.combo_totals.slice(0, 20).map((combo) => (
                          <tr
                            key={`${selectedBucketDrilldown.bucket}-${combo.transaction_type}-${combo.amount_type}-${combo.amount_description}`}
                          >
                            <td className="px-4 py-3 font-medium">{renderComboLabel(combo)}</td>
                            <td className="px-4 py-3">
                              {combo.row_count.toLocaleString("en-US")}
                            </td>
                            <td className="px-4 py-3 font-semibold">
                              {formatAmount(combo.amount)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
              </div>

              <div>
                <h3 className="text-base font-semibold text-[#0f172a]">Bucket marketplaces</h3>
                {selectedBucketDrilldown?.marketplace_totals.length ? (
                  <div className="mt-3 space-y-2">
                    {selectedBucketDrilldown.marketplace_totals.map((row) => (
                      <div
                        key={`${selectedBucketDrilldown.bucket}-${row.marketplace_name}`}
                        className="flex items-center justify-between gap-3 rounded-2xl border border-[#dbe4f0] bg-[#f8fafc] px-4 py-3 text-sm"
                      >
                        <div>
                          <p className="font-medium text-[#0f172a]">{row.marketplace_name}</p>
                          <p className="text-[#64748b]">{row.row_count.toLocaleString("en-US")} rows</p>
                        </div>
                        <p className="font-semibold text-[#0f172a]">{formatAmount(row.amount)}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-[#64748b]">
                    No marketplace totals are available for the selected bucket.
                  </p>
                )}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
