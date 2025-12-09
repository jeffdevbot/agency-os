"use client";

import type { BrandAnalysis } from "../../types";
import { formatCurrency, formatPercent } from "../../utils";

interface BrandAnalysisViewProps {
  data: BrandAnalysis;
  currency: string;
}

export function BrandAnalysisView({ data, currency }: BrandAnalysisViewProps) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-100 mb-2">Brand Analysis</h2>
        <p className="text-sm text-slate-400">
          Performance comparison between branded and generic search terms.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Branded */}
        <div className="rounded-xl bg-gradient-to-br from-blue-600/20 to-blue-800/20 border border-blue-500/30 p-6">
          <h3 className="text-lg font-semibold text-blue-300 mb-4">Branded Terms</h3>
          <div className="space-y-3">
            <div>
              <p className="text-xs text-slate-400 uppercase tracking-wide">Spend</p>
              <p className="text-2xl font-bold text-slate-100">{formatCurrency(data.branded.spend, currency)}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400 uppercase tracking-wide">Sales</p>
              <p className="text-2xl font-bold text-slate-100">{formatCurrency(data.branded.sales, currency)}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400 uppercase tracking-wide">ACOS</p>
              <p className="text-2xl font-bold text-blue-300">{formatPercent(data.branded.acos, 1)}</p>
            </div>
          </div>
        </div>

        {/* Generic */}
        <div className="rounded-xl bg-gradient-to-br from-purple-600/20 to-purple-800/20 border border-purple-500/30 p-6">
          <h3 className="text-lg font-semibold text-purple-300 mb-4">Generic Terms</h3>
          <div className="space-y-3">
            <div>
              <p className="text-xs text-slate-400 uppercase tracking-wide">Spend</p>
              <p className="text-2xl font-bold text-slate-100">{formatCurrency(data.generic.spend, currency)}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400 uppercase tracking-wide">Sales</p>
              <p className="text-2xl font-bold text-slate-100">{formatCurrency(data.generic.sales, currency)}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400 uppercase tracking-wide">ACOS</p>
              <p className="text-2xl font-bold text-purple-300">{formatPercent(data.generic.acos, 1)}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Comparison */}
      <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-6">
        <h3 className="text-sm font-semibold text-slate-200 mb-4">Spend Distribution</h3>
        <div className="h-8 bg-slate-900/50 rounded-full overflow-hidden flex">
          <div
            className="bg-gradient-to-r from-blue-600 to-blue-500 flex items-center justify-center"
            style={{ width: `${(data.branded.spend / (data.branded.spend + data.generic.spend)) * 100}%` }}
          >
            <span className="text-white text-xs font-medium">{formatPercent(data.branded.spend / (data.branded.spend + data.generic.spend), 0)}</span>
          </div>
          <div
            className="bg-gradient-to-r from-purple-600 to-purple-500 flex items-center justify-center"
            style={{ width: `${(data.generic.spend / (data.branded.spend + data.generic.spend)) * 100}%` }}
          >
            <span className="text-white text-xs font-medium">{formatPercent(data.generic.spend / (data.branded.spend + data.generic.spend), 0)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
