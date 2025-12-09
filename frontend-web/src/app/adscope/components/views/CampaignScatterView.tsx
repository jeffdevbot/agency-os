"use client";

import type { CampaignScatter } from "../../types";
import { formatCurrency, formatPercent } from "../../utils";

interface CampaignScatterViewProps {
  data: CampaignScatter[];
  currency: string;
}

export function CampaignScatterView({ data, currency }: CampaignScatterViewProps) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold text-slate-100 mb-2">Campaign Scatter</h2>
        <p className="text-sm text-slate-400">Campaign-level spend vs ACOS visualization.</p>
      </div>

      {data.length === 0 ? (
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-12 text-center">
          <p className="text-slate-400">No campaign data available</p>
        </div>
      ) : (
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-900/50 border-b border-slate-700">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Campaign</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Ad Type</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">Spend</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">ACOS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {data.map((item, idx) => (
                <tr key={idx} className="hover:bg-slate-700/30 transition-colors">
                  <td className="px-6 py-4 text-sm text-slate-300">{item.name}</td>
                  <td className="px-6 py-4 text-sm text-slate-400">{item.ad_type}</td>
                  <td className="px-6 py-4 text-right text-sm text-slate-300 font-mono">
                    {formatCurrency(item.spend, currency)}
                  </td>
                  <td className="px-6 py-4 text-right text-sm font-mono">
                    <span className={item.acos > 0.3 ? "text-red-400" : item.acos > 0.15 ? "text-yellow-400" : "text-emerald-400"}>
                      {formatPercent(item.acos, 1)}
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
