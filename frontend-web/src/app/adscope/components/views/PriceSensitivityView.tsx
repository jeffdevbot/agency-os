"use client";

import type { PriceSensitivity } from "../../types";
import { formatCurrency, formatPercent } from "../../utils";

interface PriceSensitivityViewProps {
  data: PriceSensitivity[];
  currency: string;
}

export function PriceSensitivityView({ data, currency }: PriceSensitivityViewProps) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold text-slate-100 mb-2">Price Sensitivity</h2>
        <p className="text-sm text-slate-400">
          ASIN average price vs conversion rate. Shows price point impact on purchase decisions.
        </p>
      </div>

      {data.length === 0 ? (
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-12 text-center">
          <p className="text-slate-400">No price sensitivity data available</p>
        </div>
      ) : (
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-900/50 border-b border-slate-700">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">ASIN</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">Avg Price</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">CVR</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {data.map((item, idx) => (
                <tr key={idx} className="hover:bg-slate-700/30 transition-colors">
                  <td className="px-6 py-4 text-sm text-slate-300 font-mono">{item.asin}</td>
                  <td className="px-6 py-4 text-right text-sm text-slate-300 font-mono">
                    {formatCurrency(item.avg_price, currency)}
                  </td>
                  <td className="px-6 py-4 text-right text-sm font-mono">
                    <span className={item.cvr > 0.1 ? "text-emerald-400" : item.cvr > 0.05 ? "text-yellow-400" : "text-slate-300"}>
                      {formatPercent(item.cvr, 2)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
