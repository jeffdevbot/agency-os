"use client";

import type { Zombies } from "../../types";

interface ZombiesViewProps {
  data: Zombies;
}

export function ZombiesView({ data }: ZombiesViewProps) {
  const zombiePercentage = data.total_active_ad_groups > 0
    ? (data.zombie_count / data.total_active_ad_groups) * 100
    : 0;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-100 mb-2">Zombie Ad Groups</h2>
        <p className="text-sm text-slate-400">
          Active ad groups with zero impressions. These are wasting potential but not yet spending.
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-6">
          <h3 className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Total Active Ad Groups</h3>
          <p className="text-3xl font-bold text-slate-100">{data.total_active_ad_groups}</p>
        </div>

        <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-6">
          <h3 className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Zombie Count</h3>
          <p className="text-3xl font-bold text-red-400">{data.zombie_count}</p>
        </div>

        <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-6">
          <h3 className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Zombie %</h3>
          <p className="text-3xl font-bold text-yellow-400">{zombiePercentage.toFixed(1)}%</p>
        </div>
      </div>

      {/* Zombie List */}
      {data.zombie_count === 0 ? (
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-12 text-center">
          <svg className="mx-auto h-12 w-12 text-emerald-500 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-slate-300 font-medium">No zombies found</p>
          <p className="text-slate-500 text-sm mt-1">All active ad groups are getting impressions.</p>
        </div>
      ) : (
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-6">
          <h3 className="text-sm font-semibold text-slate-200 mb-4">Zombie Ad Groups List</h3>
          <div className="space-y-2">
            {data.zombie_list.map((zombie, idx) => (
              <div key={idx} className="rounded-lg bg-slate-900/50 border border-slate-700 px-4 py-3">
                <p className="text-sm text-slate-300">{zombie}</p>
              </div>
            ))}
          </div>
          {data.zombie_count > data.zombie_list.length && (
            <p className="text-xs text-slate-500 mt-4 text-center">
              Showing {data.zombie_list.length} of {data.zombie_count} zombies
            </p>
          )}
        </div>
      )}
    </div>
  );
}
