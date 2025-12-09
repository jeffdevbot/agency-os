"use client";

import type { OverviewView as OverviewData } from "../../types";
import { formatCurrency, formatPercent, formatNumber, formatCompact, getACOSColor, getACOSBgColor } from "../../utils";

interface OverviewViewProps {
  data: OverviewData;
  currency: string;
  warnings: string[];
  dateRangeMismatch: boolean;
}

export function OverviewView({ data, currency, warnings, dateRangeMismatch }: OverviewViewProps) {
  // Ad type colors
  const getAdTypeColor = (type: string) => {
    if (type.toLowerCase().includes("sponsored products") || type.toLowerCase().includes("sp")) return "#3b82f6";
    if (type.toLowerCase().includes("sponsored brands") || type.toLowerCase().includes("sb")) return "#8b5cf6";
    if (type.toLowerCase().includes("sponsored display") || type.toLowerCase().includes("sd")) return "#f97316";
    return "#6b7280";
  };

  return (
    <div className="space-y-6">
      {/* Warnings */}
      {(dateRangeMismatch || warnings.length > 0) && (
        <div className="rounded-xl border border-yellow-500/40 bg-yellow-500/10 p-4">
          <div className="flex items-start gap-3">
            <svg className="h-5 w-5 text-yellow-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div>
              <h3 className="text-sm font-semibold text-yellow-300 mb-1">Warnings</h3>
              {dateRangeMismatch && (
                <p className="text-sm text-yellow-200/90">File date ranges do not match. Analysis may be skewed.</p>
              )}
              {warnings.map((warning, idx) => (
                <p key={idx} className="text-sm text-yellow-200/90">{warning}</p>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Spend */}
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-6">
          <h3 className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Total Spend</h3>
          <p className="text-2xl font-bold text-slate-100">{formatCurrency(data.spend, currency)}</p>
          <p className="text-xs text-slate-500 mt-1">{formatNumber(data.clicks)} clicks</p>
        </div>

        {/* Sales */}
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-6">
          <h3 className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Total Sales</h3>
          <p className="text-2xl font-bold text-slate-100">{formatCurrency(data.sales, currency)}</p>
          <p className="text-xs text-slate-500 mt-1">{formatNumber(data.orders)} orders</p>
        </div>

        {/* ACOS */}
        <div className={`rounded-xl border p-6 ${getACOSBgColor(data.acos)}`}>
          <h3 className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">ACOS</h3>
          <p className={`text-2xl font-bold ${getACOSColor(data.acos)}`}>{formatPercent(data.acos, 1)}</p>
          <p className="text-xs text-slate-400 mt-1">
            {data.acos < 0.15 ? "Good" : data.acos < 0.30 ? "OK" : "High"}
          </p>
        </div>

        {/* ROAS */}
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-6">
          <h3 className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">ROAS</h3>
          <p className="text-2xl font-bold text-slate-100">{data.roas.toFixed(2)}x</p>
          <p className="text-xs text-slate-500 mt-1">{formatNumber(data.impressions)} impressions</p>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Ad Type Mix - Donut */}
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-6">
          <h3 className="text-sm font-semibold text-slate-200 mb-4">Ad Type Mix</h3>
          <div className="space-y-3">
            {data.ad_type_mix.map((item, idx) => (
              <div key={idx}>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="text-slate-300">{item.type}</span>
                  <span className="text-slate-400">{formatPercent(item.percentage, 1)}</span>
                </div>
                <div className="h-2 bg-slate-900/50 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${item.percentage * 100}%`,
                      backgroundColor: getAdTypeColor(item.type),
                    }}
                  />
                </div>
                <p className="text-xs text-slate-500 mt-1">{formatCurrency(item.spend, currency)}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Targeting Mix */}
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-6">
          <h3 className="text-sm font-semibold text-slate-200 mb-4">Targeting Control</h3>
          <div className="space-y-4">
            <div>
              <div className="flex items-center justify-between text-sm mb-2">
                <span className="text-slate-300">Manual</span>
                <span className="text-slate-400">{formatPercent(data.targeting_mix.manual_percent, 1)}</span>
              </div>
              <div className="h-3 bg-slate-900/50 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full bg-blue-500"
                  style={{ width: `${data.targeting_mix.manual_percent * 100}%` }}
                />
              </div>
              <p className="text-xs text-slate-500 mt-1">{formatCurrency(data.targeting_mix.manual_spend, currency)}</p>
            </div>

            <div>
              <div className="flex items-center justify-between text-sm mb-2">
                <span className="text-slate-300">Auto</span>
                <span className="text-slate-400">{formatPercent(1 - data.targeting_mix.manual_percent, 1)}</span>
              </div>
              <div className="h-3 bg-slate-900/50 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full bg-purple-500"
                  style={{ width: `${(1 - data.targeting_mix.manual_percent) * 100}%` }}
                />
              </div>
              <p className="text-xs text-slate-500 mt-1">{formatCurrency(data.targeting_mix.auto_spend, currency)}</p>
            </div>

            {data.targeting_mix.auto_spend / (data.targeting_mix.manual_spend + data.targeting_mix.auto_spend) > 0.3 && (
              <div className="rounded-lg bg-yellow-500/10 border border-yellow-500/30 p-3 mt-4">
                <p className="text-xs text-yellow-300">
                  ⚠️ High auto spend ({formatPercent(1 - data.targeting_mix.manual_percent, 0)}) suggests low optimization
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Funnel */}
      <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-6">
        <h3 className="text-sm font-semibold text-slate-200 mb-6">Conversion Funnel</h3>
        <div className="space-y-4">
          {/* Impressions */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-slate-300">Impressions</span>
              <span className="text-sm text-slate-400">{formatCompact(data.impressions)}</span>
            </div>
            <div className="h-12 bg-gradient-to-r from-blue-600 to-blue-500 rounded-lg flex items-center justify-center">
              <span className="text-white font-semibold">{formatNumber(data.impressions)}</span>
            </div>
          </div>

          {/* Clicks */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-slate-300">Clicks</span>
              <span className="text-sm text-slate-400">
                {formatCompact(data.clicks)} ({formatPercent(data.clicks / data.impressions, 2)} CTR)
              </span>
            </div>
            <div className="h-12 bg-gradient-to-r from-purple-600 to-purple-500 rounded-lg flex items-center justify-center" style={{ width: `${Math.min((data.clicks / data.impressions) * 1000, 100)}%` }}>
              <span className="text-white font-semibold">{formatNumber(data.clicks)}</span>
            </div>
          </div>

          {/* Orders */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-slate-300">Orders</span>
              <span className="text-sm text-slate-400">
                {formatCompact(data.orders)} ({formatPercent(data.orders / data.clicks, 2)} CVR)
              </span>
            </div>
            <div className="h-12 bg-gradient-to-r from-emerald-600 to-emerald-500 rounded-lg flex items-center justify-center" style={{ width: `${Math.min((data.orders / data.clicks) * 500, 100)}%` }}>
              <span className="text-white font-semibold">{formatNumber(data.orders)}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
