"use client";

import type { WastedSpendView } from "../../types";
import { formatCurrency, formatPercent, formatNumber } from "../../utils/format";
import { getWastedSpendBucket, WASTED_SPEND_BUCKETS } from "../../utils/auditRules";

interface WastedAdSpendViewProps {
  data: WastedSpendView;
  currency: string;
}

export function WastedAdSpendView({ data, currency }: WastedAdSpendViewProps) {
  const summary = data.summary;
  const bucket = getWastedSpendBucket(summary.wasted_spend_pct);

  const percentClass =
    bucket.id === "severe"
      ? "text-red-600"
      : bucket.id === "high"
        ? "text-orange-600"
        : bucket.id === "heavy_testing"
          ? "text-emerald-700"
          : bucket.id === "healthy"
            ? "text-emerald-600"
            : "text-amber-700";

  const pillClass =
    bucket.id === "severe"
      ? "bg-red-50 text-red-700 border-red-200"
      : bucket.id === "high"
        ? "bg-orange-50 text-orange-700 border-orange-200"
        : bucket.id === "heavy_testing"
          ? "bg-emerald-50 text-emerald-700 border-emerald-200"
          : bucket.id === "healthy"
            ? "bg-emerald-50 text-emerald-700 border-emerald-200"
            : "bg-amber-50 text-amber-800 border-amber-200";

  return (
    <div className="space-y-6 p-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 mb-2">Wasted Ad Spend — Sponsored Products</h2>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="rounded-xl bg-white border border-slate-200 shadow-sm p-6">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Total Wasted Spend</h3>
          <p className="text-3xl font-bold text-slate-900">{formatCurrency(summary.total_wasted_spend, currency)}</p>
          <p className="text-sm text-slate-500 mt-1">
            of {formatCurrency(summary.total_ad_spend, currency)} SP spend
          </p>
        </div>

        <div className="rounded-xl bg-white border border-slate-200 shadow-sm p-6">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Wasted Spend %</h3>
          <div className="flex items-center gap-3">
            <p className={`text-3xl font-bold ${percentClass}`}>{formatPercent(summary.wasted_spend_pct)}</p>
            <span className={`text-xs font-semibold px-2 py-1 rounded-full border ${pillClass}`}>
              {bucket.verdict}
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">{bucket.meaning}</p>
        </div>

        <div className="rounded-xl bg-white border border-slate-200 shadow-sm p-6">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Wasted Targets</h3>
          <p className="text-3xl font-bold text-slate-900">{formatNumber(summary.wasted_targets_count)}</p>
          <p className="text-sm text-slate-500 mt-1">targets that spent money but didn’t generate a sale</p>
        </div>

        <div className="rounded-xl bg-white border border-slate-200 shadow-sm p-6">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Campaigns With High Waste</h3>
          <p className="text-3xl font-bold text-slate-900">{formatNumber(summary.campaigns_high_waste_count)}</p>
          <p className="text-sm text-slate-500 mt-1">campaigns where 50–100% of spend went to non-converting targets</p>
        </div>
      </div>

      {/* Interpretation table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wide mb-4">How To Interpret</h3>
        <div className="overflow-x-auto">
          <table className="min-w-[720px] w-full">
            <thead className="border-b border-slate-200">
              <tr>
                <th className="py-2 pr-6 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Wasted Spend %</th>
                <th className="py-2 pr-6 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Verdict</th>
                <th className="py-2 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Meaning</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {WASTED_SPEND_BUCKETS.map((b) => (
                <tr key={b.id} className={b.id === bucket.id ? "bg-slate-50" : undefined}>
                  <td className="py-3 pr-6 text-sm text-slate-700 font-mono">{b.rangeLabel}</td>
                  <td className="py-3 pr-6 text-sm text-slate-800 font-semibold">{b.verdict}</td>
                  <td className="py-3 text-sm text-slate-600">{b.meaning}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Main table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200">
          <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wide">
            Targets Wasting The Most Spend (0 orders)
          </h3>
          <p className="text-sm text-slate-500 mt-1">
            Sorted by wasted spend. Each row shows a keyword or target that spent money but didn’t generate a sale.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-[1200px] w-full">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Campaign</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Ad Group</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Search Term</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Type</th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wide">Impr.</th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wide">Clicks</th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wide">Spend</th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wide">Orders</th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wide">Sales</th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wide">ACoS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.top_wasted_targets.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-6 py-10 text-center text-slate-500">
                    No wasted spend found (orders = 0).
                  </td>
                </tr>
              ) : (
                data.top_wasted_targets.map((row, idx) => (
                  <tr key={idx} className="hover:bg-slate-50 transition-colors">
                    <td className="px-6 py-3 text-sm text-slate-900 max-w-[320px] truncate">{row.campaign_name}</td>
                    <td className="px-6 py-3 text-sm text-slate-700 max-w-[240px] truncate">{row.ad_group_name || "—"}</td>
                    <td className="px-6 py-3 text-sm text-slate-900 max-w-[340px] truncate">{row.search_term}</td>
                    <td className="px-6 py-3 text-sm text-slate-700 whitespace-nowrap">{row.targeting_type}</td>
                    <td className="px-6 py-3 text-right text-sm text-slate-700 font-mono">{formatNumber(row.impressions)}</td>
                    <td className="px-6 py-3 text-right text-sm text-slate-700 font-mono">{formatNumber(row.clicks)}</td>
                    <td className="px-6 py-3 text-right text-sm text-slate-900 font-mono font-semibold">
                      {formatCurrency(row.wasted_spend, currency)}
                    </td>
                    <td className="px-6 py-3 text-right text-sm text-slate-700 font-mono">{formatNumber(row.orders)}</td>
                    <td className="px-6 py-3 text-right text-sm text-slate-700 font-mono">{formatCurrency(row.sales, currency)}</td>
                    <td className="px-6 py-3 text-right text-sm text-slate-700 font-mono">
                      {row.acos == null ? "—" : formatPercent(row.acos)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Campaign rollup */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200">
          <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wide">Campaign Roll-up</h3>
          <p className="text-sm text-slate-500 mt-1">
            Wasted spend aggregated by campaign (SP-only).
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-[980px] w-full">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Campaign</th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wide">Spend</th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wide">Sales</th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wide">ACoS</th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wide">Wasted Spend</th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wide">Wasted %</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.campaign_rollup.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-10 text-center text-slate-500">
                    No campaign roll-up available.
                  </td>
                </tr>
              ) : (
                data.campaign_rollup.map((row, idx) => (
                  <tr key={idx} className="hover:bg-slate-50 transition-colors">
                    <td className="px-6 py-3 text-sm text-slate-900 max-w-[420px] truncate">{row.campaign_name}</td>
                    <td className="px-6 py-3 text-right text-sm text-slate-700 font-mono">{formatCurrency(row.campaign_spend, currency)}</td>
                    <td className="px-6 py-3 text-right text-sm text-slate-700 font-mono">{formatCurrency(row.campaign_sales, currency)}</td>
                    <td className="px-6 py-3 text-right text-sm text-slate-700 font-mono">
                      {row.campaign_acos == null ? "—" : formatPercent(row.campaign_acos)}
                    </td>
                    <td className="px-6 py-3 text-right text-sm text-slate-900 font-mono font-semibold">
                      {formatCurrency(row.campaign_wasted_spend, currency)}
                    </td>
                    <td className="px-6 py-3 text-right text-sm text-slate-700 font-mono">
                      {formatPercent(row.campaign_wasted_pct)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
