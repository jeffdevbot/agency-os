"use client";

import type { Duplicate } from "../../types";

interface DuplicatesViewProps {
  data: Duplicate[];
}

export function DuplicatesView({ data }: DuplicatesViewProps) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold text-slate-100 mb-2">Duplicate Keywords</h2>
        <p className="text-sm text-slate-400">
          Keywords used in multiple campaigns. May cause budget conflicts and bid competition.
        </p>
      </div>

      {data.length === 0 ? (
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-12 text-center">
          <svg className="mx-auto h-12 w-12 text-emerald-500 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-slate-300 font-medium">No duplicate keywords found</p>
          <p className="text-slate-500 text-sm mt-1">Each keyword is unique to one campaign.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {data.map((item, idx) => (
            <div key={idx} className="rounded-xl bg-slate-800/50 border border-yellow-500/30 p-4">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <p className="text-sm font-semibold text-slate-200">{item.keyword}</p>
                  <p className="text-xs text-slate-500">{item.match_type}</p>
                </div>
                <span className="px-3 py-1 rounded-full bg-yellow-500/20 text-yellow-400 text-xs font-medium">
                  {item.campaign_count} campaigns
                </span>
              </div>
              <div className="mt-3">
                <p className="text-xs text-slate-400 mb-2">Used in:</p>
                <div className="flex flex-wrap gap-2">
                  {item.campaigns.map((campaign, cidx) => (
                    <span key={cidx} className="px-2 py-1 rounded bg-slate-700 text-slate-300 text-xs">
                      {campaign}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
