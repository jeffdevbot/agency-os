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
  // Derived Metrics
  const cpc = data.clicks > 0 ? data.spend / data.clicks : 0;
  const ctr = data.impressions > 0 ? data.clicks / data.impressions : 0;
  const cvr = data.clicks > 0 ? data.orders / data.clicks : 0;

  // Ad type colors
  // Ad type colors for Ecomlabs palette
  const getAdTypeColor = (type: string) => {
    if (type.toLowerCase().includes("sponsored products") || type.toLowerCase().includes("sp")) return "#0077cc"; // Primary Blue
    if (type.toLowerCase().includes("sponsored brands") || type.toLowerCase().includes("sb")) return "#8b5cf6";   // Purple
    if (type.toLowerCase().includes("sponsored display") || type.toLowerCase().includes("sd")) return "#f97316";  // Orange
    return "#64748b"; // Slate-500
  };

  return (
    <div className="space-y-6 p-6">
      {/* Warnings */}
      {(dateRangeMismatch || warnings.length > 0) && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
          <div className="flex items-start gap-3">
            <svg className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div>
              <h3 className="text-sm font-semibold text-amber-800 mb-1">Warnings</h3>
              {dateRangeMismatch && (
                <p className="text-sm text-amber-700">File date ranges do not match. Analysis may be skewed.</p>
              )}
              {warnings.map((warning, idx) => (
                <p key={idx} className="text-sm text-amber-700">{warning}</p>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Spend */}
        <div className="rounded-xl bg-white border border-slate-200 shadow-sm p-6">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Total Spend</h3>
          <p className="text-2xl font-bold text-slate-900">{formatCurrency(data.spend, currency)}</p>
          <p className="text-xs text-slate-500 mt-1">{formatNumber(data.clicks)} clicks</p>
        </div>

        {/* Sales */}
        <div className="rounded-xl bg-white border border-slate-200 shadow-sm p-6">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Ad Sales</h3>
          <p className="text-2xl font-bold text-slate-900">{formatCurrency(data.sales, currency)}</p>
          <p className="text-xs text-slate-500 mt-1">{formatNumber(data.orders)} orders</p>
        </div>

        {/* ACoS */}
        <div className="rounded-xl bg-white border border-slate-200 shadow-sm p-6">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">ACoS</h3>
          <div className="flex items-baseline gap-2">
            <p className={`text-2xl font-bold ${getACOSColor(data.acos)}`}>{formatPercent(data.acos)}</p>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-1.5 mt-3">
            <div
              className={`h-1.5 rounded-full ${getACOSBgColor(data.acos)}`}
              style={{ width: `${Math.min(data.acos * 2, 100)}%` }}
            ></div>
          </div>
        </div>

        {/* ROAS */}
        <div className="rounded-xl bg-white border border-slate-200 shadow-sm p-6">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">ROAS</h3>
          <p className="text-2xl font-bold text-slate-900">{data.roas.toFixed(2)}x</p>
          <p className="text-xs text-slate-500 mt-1">{formatCurrency(cpc, currency)} CPC</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Funnel Health */}
        <div className="lg:col-span-2 rounded-xl bg-white border border-slate-200 shadow-sm p-6">
          <h3 className="text-sm font-semibold text-slate-800 mb-6">Funnel Health</h3>
          <div className="space-y-6">
            {/* Impressions -> Clicks */}
            <div className="relative">
              <div className="flex justify-between items-end mb-2">
                <div>
                  <p className="text-xs font-semibold uppercase text-slate-500">Impressions</p>
                  <p className="text-lg font-bold text-slate-900">{formatCompact(data.impressions)}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs font-semibold uppercase text-slate-500">CTR</p>
                  <p className="text-lg font-bold text-slate-900">{formatPercent(ctr)}</p>
                </div>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-2">
                <div className="bg-[#0077cc] h-2 rounded-full" style={{ width: '100%' }}></div>
              </div>
            </div>

            {/* Clicks -> Orders */}
            <div className="relative pl-8 border-l-2 border-slate-100 ml-4">
              <div className="flex justify-between items-end mb-2">
                <div>
                  <p className="text-xs font-semibold uppercase text-slate-500">Clicks</p>
                  <p className="text-lg font-bold text-slate-900">{formatCompact(data.clicks)}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs font-semibold uppercase text-slate-500">CVR</p>
                  <p className="text-lg font-bold text-slate-900">{formatPercent(cvr)}</p>
                </div>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-2">
                <div className="bg-[#0077cc] h-2 rounded-full opacity-60" style={{ width: `${Math.min(ctr * 500, 100)}%` }}></div>
              </div>
            </div>

            {/* Orders */}
            <div className="relative pl-8 border-l-2 border-slate-100 ml-4">
              <div className="flex justify-between items-end mb-2">
                <div>
                  <p className="text-xs font-semibold uppercase text-slate-500">Orders</p>
                  <p className="text-lg font-bold text-slate-900">{formatNumber(data.orders)}</p>
                </div>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-2">
                <div className="bg-[#0077cc] h-2 rounded-full opacity-30" style={{ width: `${Math.min(cvr * 500, 100)}%` }}></div>
              </div>
            </div>
          </div>
        </div>

        {/* Ad Type Mix */}
        <div className="rounded-xl bg-white border border-slate-200 shadow-sm p-6">
          <h3 className="text-sm font-semibold text-slate-800 mb-6">Spend Mix</h3>
          <div className="space-y-4">
            {data.ad_type_mix.map((item, idx) => (
              <div key={idx}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-slate-600 font-medium">{item.type}</span>
                  <span className="text-slate-900 font-bold">{formatPercent(item.percentage)}</span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2">
                  <div
                    className="h-2 rounded-full"
                    style={{
                      width: `${item.percentage}%`,
                      backgroundColor: getAdTypeColor(item.type)
                    }}
                  ></div>
                </div>
                <p className="text-xs text-slate-400 mt-1 text-right">{formatCurrency(item.spend, currency)}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Targeting Mix (moved from original Charts Row) */}
      <div className="rounded-xl bg-white border border-slate-200 shadow-sm p-6">
        <h3 className="text-sm font-semibold text-slate-800 mb-4">Targeting Control</h3>
        <div className="space-y-4">
          <div>
            <div className="flex items-center justify-between text-sm mb-2">
              <span className="text-slate-600 font-medium">Manual</span>
              <span className="text-slate-900 font-bold">{formatPercent(data.targeting_mix.manual_percent, 1)}</span>
            </div>
            <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full bg-blue-600"
                style={{ width: `${data.targeting_mix.manual_percent * 100}%` }}
              />
            </div>
            <p className="text-xs text-slate-400 mt-1 text-right">{formatCurrency(data.targeting_mix.manual_spend, currency)}</p>
          </div>

          <div>
            <div className="flex items-center justify-between text-sm mb-2">
              <span className="text-slate-600 font-medium">Auto</span>
              <span className="text-slate-900 font-bold">{formatPercent(1 - data.targeting_mix.manual_percent, 1)}</span>
            </div>
            <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full bg-purple-600"
                style={{ width: `${(1 - data.targeting_mix.manual_percent) * 100}%` }}
              />
            </div>
            <p className="text-xs text-slate-400 mt-1 text-right">{formatCurrency(data.targeting_mix.auto_spend, currency)}</p>
          </div>

          {data.targeting_mix.auto_spend / (data.targeting_mix.manual_spend + data.targeting_mix.auto_spend) > 0.3 && (
            <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 mt-4">
              <p className="text-xs text-amber-700">
                ⚠️ High auto spend ({formatPercent(1 - data.targeting_mix.manual_percent, 0)}) suggests low optimization
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
