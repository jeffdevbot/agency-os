"use client";

import type { Portfolio } from "../../types";
import { formatCurrency, formatPercent } from "../../utils";

interface PortfoliosViewProps {
  data: Portfolio[];
  currency: string;
}

export function PortfoliosView({ data, currency }: PortfoliosViewProps) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold text-slate-100 mb-2">Portfolios</h2>
        <p className="text-sm text-slate-400">Performance breakdown by portfolio.</p>
      </div>

      {data.length === 0 ? (
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-12 text-center">
          <p className="text-slate-400">No portfolio data available</p>
        </div>
      ) : (
        <div className="space-y-3">
          {data.map((item, idx) => (
            <div key={idx} className="rounded-xl bg-slate-800/50 border border-slate-700 p-6">
              <h3 className="text-lg font-semibold text-slate-200 mb-4">{item.name}</h3>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <p className="text-xs text-slate-400 uppercase tracking-wide">Spend</p>
                  <p className="text-xl font-bold text-slate-100">{formatCurrency(item.spend, currency)}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-400 uppercase tracking-wide">Sales</p>
                  <p className="text-xl font-bold text-slate-100">{formatCurrency(item.sales, currency)}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-400 uppercase tracking-wide">ACOS</p>
                  <p className={`text-xl font-bold ${item.acos > 0.3 ? "text-red-400" : item.acos > 0.15 ? "text-yellow-400" : "text-emerald-400"}`}>
                    {formatPercent(item.acos, 1)}
                  </p>
                </div>
              </div>
              {/* Spend bar */}
              <div className="mt-4 h-2 bg-slate-900/50 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-600 to-blue-500 rounded-full"
                  style={{ width: `${Math.min((item.spend / Math.max(...data.map((d) => d.spend))) * 100, 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
