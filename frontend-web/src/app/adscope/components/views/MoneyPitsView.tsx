"use client";

import type { MoneyPit } from "../../types";
import { formatCurrency, formatPercent, getASINThumbnailURL, getStateBadgeColor } from "../../utils";
import { useState } from "react";

interface MoneyPitsViewProps {
  data: MoneyPit[];
  currency: string;
}

export function MoneyPitsView({ data, currency }: MoneyPitsViewProps) {
  const [imageErrors, setImageErrors] = useState<Set<string>>(new Set());

  const handleImageError = (asin: string) => {
    setImageErrors((prev) => new Set(prev).add(asin));
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold text-slate-100 mb-2">Money Pits</h2>
        <p className="text-sm text-slate-400">
          Top 20% of ASINs by spend (max 50). High-spend products that may need optimization.
        </p>
      </div>

      {data.length === 0 ? (
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-12 text-center">
          <p className="text-slate-400">No money pits found</p>
        </div>
      ) : (
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-900/50 border-b border-slate-700">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Product</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">Spend</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">Sales</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">ACOS</th>
                <th className="px-6 py-3 text-center text-xs font-medium text-slate-400 uppercase tracking-wider">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {data.map((item, idx) => (
                <tr key={idx} className="hover:bg-slate-700/30 transition-colors">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-slate-700 flex items-center justify-center overflow-hidden flex-shrink-0">
                        {!imageErrors.has(item.asin) ? (
                          <img
                            src={getASINThumbnailURL(item.asin)}
                            alt={item.asin}
                            className="w-full h-full object-cover"
                            onError={() => handleImageError(item.asin)}
                          />
                        ) : (
                          <span className="text-xs text-slate-500">{item.asin.slice(0, 2)}</span>
                        )}
                      </div>
                      <div>
                        <p className="text-sm font-medium text-slate-200">{item.asin}</p>
                        {item.product_name && (
                          <p className="text-xs text-slate-500">{item.product_name}</p>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right text-sm text-slate-300 font-mono">
                    {formatCurrency(item.spend, currency)}
                  </td>
                  <td className="px-6 py-4 text-right text-sm text-slate-300 font-mono">
                    {formatCurrency(item.sales, currency)}
                  </td>
                  <td className="px-6 py-4 text-right text-sm font-mono">
                    <span className={item.acos > 0.5 ? "text-red-400" : item.acos > 0.3 ? "text-yellow-400" : "text-slate-300"}>
                      {formatPercent(item.acos, 1)}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${getStateBadgeColor(item.state)}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${item.state.toLowerCase() === "enabled" ? "bg-emerald-400" : "bg-slate-400"}`} />
                      {item.state}
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
