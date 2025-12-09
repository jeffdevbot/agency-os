"use client";

import type { NGram } from "../../types";
import { formatCurrency, formatPercent, formatNumber } from "../../utils";

interface NGramsViewProps {
  data: NGram[];
  currency: string;
}

export function NGramsView({ data, currency }: NGramsViewProps) {
  const oneGrams = data.filter((g) => g.type === "1-gram");
  const twoGrams = data.filter((g) => g.type === "2-gram");

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-100 mb-2">N-Grams Analysis</h2>
        <p className="text-sm text-slate-400">Most common keywords and phrases in search terms.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 1-Grams */}
        <div>
          <h3 className="text-lg font-semibold text-blue-400 mb-3">Single Keywords</h3>
          {oneGrams.length === 0 ? (
            <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-8 text-center">
              <p className="text-slate-400">No 1-gram data</p>
            </div>
          ) : (
            <div className="space-y-2">
              {oneGrams.slice(0, 20).map((item, idx) => (
                <div key={idx} className="rounded-lg bg-slate-800/50 border border-slate-700 p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-semibold text-slate-200">{item.gram}</span>
                    <span className="text-xs text-slate-500">{formatNumber(item.count)} terms</span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-400">Spend: {formatCurrency(item.spend, currency)}</span>
                    <span className="text-slate-400">Sales: {formatCurrency(item.sales, currency)}</span>
                    <span className={item.acos > 0.3 ? "text-red-400" : "text-emerald-400"}>
                      ACOS: {formatPercent(item.acos, 1)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 2-Grams */}
        <div>
          <h3 className="text-lg font-semibold text-purple-400 mb-3">Two-Word Phrases</h3>
          {twoGrams.length === 0 ? (
            <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-8 text-center">
              <p className="text-slate-400">No 2-gram data</p>
            </div>
          ) : (
            <div className="space-y-2">
              {twoGrams.slice(0, 20).map((item, idx) => (
                <div key={idx} className="rounded-lg bg-slate-800/50 border border-slate-700 p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-semibold text-slate-200">{item.gram}</span>
                    <span className="text-xs text-slate-500">{formatNumber(item.count)} terms</span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-400">Spend: {formatCurrency(item.spend, currency)}</span>
                    <span className="text-slate-400">Sales: {formatCurrency(item.sales, currency)}</span>
                    <span className={item.acos > 0.3 ? "text-red-400" : "text-emerald-400"}>
                      ACOS: {formatPercent(item.acos, 1)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
