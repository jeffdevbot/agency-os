"use client";

import type { BudgetCapper } from "../../types";
import { formatCurrency, formatPercent, getStateBadgeColor } from "../../utils";

interface BudgetCappersViewProps {
  data: BudgetCapper[];
  currency: string;
}

export function BudgetCappersView({ data, currency }: BudgetCappersViewProps) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold text-slate-100 mb-2">Budget Cappers</h2>
        <p className="text-sm text-slate-400">
          Campaigns hitting budget limits (utilization &gt; 90%). Consider increasing budgets for high-ROAS campaigns.
        </p>
      </div>

      {data.length === 0 ? (
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-12 text-center">
          <svg className="mx-auto h-12 w-12 text-emerald-500 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-slate-300 font-medium">No budget cappers found</p>
          <p className="text-slate-500 text-sm mt-1">No campaigns hitting budget limits.</p>
        </div>
      ) : (
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-900/50 border-b border-slate-700">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Campaign</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">Daily Budget</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">Avg Spend</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">Utilization</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">ROAS</th>
                <th className="px-6 py-3 text-center text-xs font-medium text-slate-400 uppercase tracking-wider">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {data.map((item, idx) => (
                <tr key={idx} className="hover:bg-slate-700/30 transition-colors">
                  <td className="px-6 py-4 text-sm text-slate-300">{item.campaign_name}</td>
                  <td className="px-6 py-4 text-right text-sm text-slate-300 font-mono">
                    {formatCurrency(item.daily_budget, currency)}
                  </td>
                  <td className="px-6 py-4 text-right text-sm text-slate-300 font-mono">
                    {formatCurrency(item.avg_daily_spend, currency)}
                  </td>
                  <td className="px-6 py-4 text-right text-sm font-mono">
                    <span className={item.utilization > 0.95 ? "text-red-400 font-semibold" : "text-yellow-400"}>
                      {formatPercent(item.utilization, 0)}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right text-sm font-mono">
                    <span className={item.roas >= 3 ? "text-emerald-400 font-semibold" : "text-slate-300"}>
                      {item.roas.toFixed(2)}x
                    </span>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${getStateBadgeColor(item.state)}`}>
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
