"use client";

import type { MatchType } from "../../types";
import { formatCurrency, formatPercent } from "../../utils";

interface MatchTypesViewProps {
  data: MatchType[];
  currency: string;
}

export function MatchTypesView({ data, currency }: MatchTypesViewProps) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold text-slate-100 mb-2">Match Types</h2>
        <p className="text-sm text-slate-400">Performance breakdown by match type (Exact, Phrase, Broad).</p>
      </div>

      {data.length === 0 ? (
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-12 text-center">
          <p className="text-slate-400">No match type data available</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.map((item, idx) => (
            <div key={idx} className="rounded-xl bg-slate-800/50 border border-slate-700 p-6">
              <h3 className="text-lg font-semibold text-slate-200 mb-4">{item.type}</h3>
              <div className="space-y-3">
                <div>
                  <p className="text-xs text-slate-400 uppercase tracking-wide">Spend</p>
                  <p className="text-xl font-bold text-slate-100">{formatCurrency(item.spend, currency)}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-400 uppercase tracking-wide">Sales</p>
                  <p className="text-xl font-bold text-slate-100">{formatCurrency(item.sales, currency)}</p>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <p className="text-xs text-slate-400 uppercase tracking-wide">ACOS</p>
                    <p className="text-lg font-semibold text-slate-200">{formatPercent(item.acos, 1)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400 uppercase tracking-wide">CPC</p>
                    <p className="text-lg font-semibold text-slate-200">{formatCurrency(item.cpc, currency)}</p>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
