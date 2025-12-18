"use client";

import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { InternalUsageLogRow, InternalUsageResult } from "@/app/actions/get-internal-usage";

const formatUsd = (amount: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(amount);

const estimateCostUsd = (row: InternalUsageLogRow): number | null => {
  const model = row.model ?? "";
  const promptTokens = row.promptTokens ?? 0;
  const completionTokens = row.completionTokens ?? 0;

  const pricingPer1M: Record<string, { input: number; output: number }> = {
    "gpt-4o-mini": { input: 0.15, output: 0.6 },
    "gpt-4o": { input: 2.5, output: 10 },
  };

  const match =
    Object.entries(pricingPer1M).find(([prefix]) => model.startsWith(prefix))?.[1] ?? null;
  if (!match) return null;

  return (promptTokens / 1_000_000) * match.input + (completionTokens / 1_000_000) * match.output;
};

const safeToolColor = (tool: string, idx: number) => {
  const palette = ["#0a6fd6", "#7c3aed", "#0f766e", "#f59e0b", "#ef4444", "#64748b"];
  const known: Record<string, string> = {
    scribe: "#0a6fd6",
    adscope: "#7c3aed",
    debrief: "#0f766e",
    "command-center": "#0f172a",
  };
  return known[tool] ?? palette[idx % palette.length];
};

export function InternalAttributionCard(props: { internal: InternalUsageResult }) {
  const { internal } = props;
  const [logsLimit, setLogsLimit] = useState(20);

  const tools = useMemo(() => {
    const set = new Set<string>();
    for (const day of internal.dailyByTool) {
      for (const tool of Object.keys(day.totalsByTool)) set.add(tool);
    }
    return Array.from(set.values()).sort();
  }, [internal.dailyByTool]);

  const usageByToolChartData = useMemo(() => {
    return internal.dailyByTool.map((day) => {
      const row: Record<string, string | number> = { date: day.day.slice(5) };
      for (const tool of tools) row[tool] = day.totalsByTool[tool] ?? 0;
      return row;
    });
  }, [internal.dailyByTool, tools]);

  const exportUrl = `/api/command-center/tokens/export?range=${encodeURIComponent(String(internal.rangeDays))}`;
  const safeLimit = Math.min(logsLimit, internal.logs.length);
  const visibleLogs = internal.logs.slice(0, safeLimit);
  const totalRowsLabel = internal.totalRows ?? internal.logs.length;

  return (
    <>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur lg:col-span-2">
          <h2 className="text-lg font-semibold text-[#0f172a]">Usage by Tool</h2>
          <p className="mt-2 text-sm text-[#4c576f]">Daily tokens (stacked) from `ai_token_usage`</p>
          <div className="mt-6 h-[280px]">
            {usageByToolChartData.length === 0 ? (
              <div className="flex h-full items-center justify-center text-sm text-[#4c576f]">No internal logs yet.</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={usageByToolChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 12 }} stroke="#64748b" />
                  <YAxis tick={{ fontSize: 12 }} stroke="#64748b" />
                  <Tooltip />
                  <Legend />
                  {tools.map((tool, idx) => (
                    <Bar
                      key={tool}
                      dataKey={tool}
                      stackId="tokens"
                      fill={safeToolColor(tool, idx)}
                      radius={[10, 10, 0, 0]}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          <h2 className="text-lg font-semibold text-[#0f172a]">Top Spenders</h2>
          <p className="mt-2 text-sm text-[#4c576f]">Total tokens (last {internal.rangeDays}d)</p>
          <div className="mt-6 space-y-3">
            {internal.topSpenders.length === 0 ? (
              <p className="text-sm text-[#4c576f]">No internal logs yet.</p>
            ) : (
              internal.topSpenders.map((u) => (
                <div key={u.userId} className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    {u.avatarUrl ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={u.avatarUrl} alt="" className="h-9 w-9 rounded-full" />
                    ) : (
                      <div className="h-9 w-9 rounded-full bg-[#e8eefc]" />
                    )}
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold text-[#0f172a]">{u.name}</div>
                      <div className="text-xs text-[#4c576f]">{u.userId.slice(0, 8)}</div>
                    </div>
                  </div>
                  <div className="text-sm font-semibold text-[#0f172a]">{u.totalTokens.toLocaleString()}</div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-[#0f172a]">Logs</h2>
            <p className="mt-2 text-sm text-[#4c576f]">
              Most recent {safeLimit} of {totalRowsLabel} rows (last {internal.rangeDays}d)
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <a
              href={exportUrl}
              className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
              aria-disabled={totalRowsLabel === 0}
            >
              Export CSV
            </a>
            <select
              value={logsLimit}
              onChange={(e) => setLogsLimit(Number(e.target.value))}
              className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm"
            >
              {[20, 50, 100, 250].map((n) => (
                <option key={n} value={n}>
                  Show {n}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-6 overflow-x-auto rounded-2xl border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-[#f7faff]">
              <tr className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">
                <th className="px-4 py-3">Time</th>
                <th className="px-4 py-3">User</th>
                <th className="px-4 py-3">Tool</th>
                <th className="px-4 py-3">Model</th>
                <th className="px-4 py-3">Tokens (In/Out)</th>
                <th className="px-4 py-3">Est. Cost</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white">
              {visibleLogs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-sm text-[#4c576f]">
                    No logs yet.
                  </td>
                </tr>
              ) : (
                visibleLogs.map((log) => {
                  const displayName =
                    log.user?.displayName || log.user?.fullName || log.user?.email || log.userId.slice(0, 8);
                  const est = estimateCostUsd(log);
                  return (
                    <tr key={log.id} className="align-top">
                      <td className="px-4 py-3 whitespace-nowrap text-[#0f172a]">
                        {new Date(log.createdAt).toLocaleString()}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          {log.user?.avatarUrl ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={log.user.avatarUrl} alt="" className="h-7 w-7 rounded-full" />
                          ) : (
                            <div className="h-7 w-7 rounded-full bg-[#e8eefc]" />
                          )}
                          <div className="min-w-0">
                            <div className="truncate font-semibold text-[#0f172a]">{displayName}</div>
                            <div className="text-xs text-[#4c576f]">{log.userId.slice(0, 8)}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 font-semibold text-[#0f172a]">{log.tool}</td>
                      <td className="px-4 py-3 text-[#0f172a]">{log.model ?? "—"}</td>
                      <td className="px-4 py-3 text-[#0f172a]">
                        {(log.promptTokens ?? 0).toLocaleString()} / {(log.completionTokens ?? 0).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-[#0f172a]">{est === null ? "—" : formatUsd(est)}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        <p className="mt-3 text-xs text-[#4c576f]">
          Est. cost is approximate and only computed for select models; rely on Section A for authoritative billing.
        </p>
      </div>
    </>
  );
}
