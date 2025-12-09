"use client";

import type { KeywordLeaderboard } from "../../types";
import { formatCurrency, getStateBadgeColor } from "../../utils";

interface KeywordLeaderboardViewProps {
  data: KeywordLeaderboard;
  currency: string;
}

export function KeywordLeaderboardView({ data, currency }: KeywordLeaderboardViewProps) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-100 mb-2">Keyword Leaderboard</h2>
        <p className="text-sm text-slate-400">Top performers and underperformers by ROAS.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Winners */}
        <div>
          <h3 className="text-lg font-semibold text-emerald-400 mb-3">🏆 Winners (Top 10 by Sales)</h3>
          <div className="space-y-3">
            {data.winners.length === 0 ? (
              <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-8 text-center">
                <p className="text-slate-400">No winners found</p>
              </div>
            ) : (
              data.winners.map((kw, idx) => (
                <div key={idx} className="rounded-lg bg-slate-800/50 border border-emerald-500/30 p-4">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      <p className="text-sm font-semibold text-slate-200">{kw.text}</p>
                      <p className="text-xs text-slate-500">{kw.match_type} • {kw.campaign}</p>
                    </div>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${getStateBadgeColor(kw.state)}`}>
                      {kw.state}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-400">Spend: {formatCurrency(kw.spend, currency)}</span>
                    <span className="text-slate-400">Sales: {formatCurrency(kw.sales, currency)}</span>
                    <span className="text-emerald-400 font-semibold">ROAS: {kw.roas.toFixed(2)}x</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Losers */}
        <div>
          <h3 className="text-lg font-semibold text-red-400 mb-3">⚠️ Losers (Top 10 by Spend, ROAS &lt; 2)</h3>
          <div className="space-y-3">
            {data.losers.length === 0 ? (
              <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-8 text-center">
                <p className="text-slate-400">No losers found (great!)</p>
              </div>
            ) : (
              data.losers.map((kw, idx) => (
                <div key={idx} className="rounded-lg bg-slate-800/50 border border-red-500/30 p-4">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      <p className="text-sm font-semibold text-slate-200">{kw.text}</p>
                      <p className="text-xs text-slate-500">{kw.match_type} • {kw.campaign}</p>
                    </div>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${getStateBadgeColor(kw.state)}`}>
                      {kw.state}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-400">Spend: {formatCurrency(kw.spend, currency)}</span>
                    <span className="text-slate-400">Sales: {formatCurrency(kw.sales, currency)}</span>
                    <span className="text-red-400 font-semibold">ROAS: {kw.roas.toFixed(2)}x</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
