"use client";

import type { Placement } from "../../types";
import { formatCurrency, formatPercent } from "../../utils";

interface PlacementsViewProps {
  data: Placement[];
  currency: string;
}

export function PlacementsView({ data, currency }: PlacementsViewProps) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold text-slate-100 mb-2">Placements</h2>
        <p className="text-sm text-slate-400">Performance by ad placement (Top of Search, Product Pages, etc.).</p>
      </div>

      {data.length === 0 ? (
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-12 text-center">
          <p className="text-slate-400">No placement data available</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {data.map((item, idx) => (
            <div key={idx} className="rounded-xl bg-slate-800/50 border border-slate-700 p-6">
              <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-3">{item.placement}</h3>
              <div className="space-y-3">
                <div>
                  <p className="text-xs text-slate-500">Spend</p>
                  <p className="text-2xl font-bold text-slate-100">{formatCurrency(item.spend, currency)}</p>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <p className="text-xs text-slate-500">ACOS</p>
                    <p className="text-lg font-semibold text-slate-200">{formatPercent(item.acos, 1)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">CPC</p>
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
