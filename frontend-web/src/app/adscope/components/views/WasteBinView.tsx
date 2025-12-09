"use client";

import type { WasteBinItem } from "../../types";
import { formatCurrency, formatNumber } from "../../utils";

interface WasteBinViewProps {
  data: WasteBinItem[];
  currency: string;
}

export function WasteBinView({ data, currency }: WasteBinViewProps) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold text-slate-100 mb-2">Waste Bin</h2>
        <p className="text-sm text-slate-400">
          Search terms with spend &gt; {formatCurrency(50, currency)} but zero sales. Clear waste.
        </p>
      </div>

      {data.length === 0 ? (
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-12 text-center">
          <svg className="mx-auto h-12 w-12 text-emerald-500 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-slate-300 font-medium">No wasted spend found</p>
          <p className="text-slate-500 text-sm mt-1">Great job! No search terms with spend but zero sales.</p>
        </div>
      ) : (
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-900/50 border-b border-slate-700">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Search Term</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">Wasted Spend</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">Clicks</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {data.map((item, idx) => (
                <tr key={idx} className="hover:bg-slate-700/30 transition-colors">
                  <td className="px-6 py-4 text-sm text-slate-300">{item.search_term}</td>
                  <td className="px-6 py-4 text-right text-sm text-red-400 font-mono font-semibold">
                    {formatCurrency(item.spend, currency)}
                  </td>
                  <td className="px-6 py-4 text-right text-sm text-slate-400 font-mono">
                    {formatNumber(item.clicks)}
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
