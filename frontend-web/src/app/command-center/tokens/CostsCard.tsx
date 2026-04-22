"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { OpenAIDailyCost, OpenAICostsStatus } from "@/app/actions/get-openai-costs";

const formatUsd = (amount: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(amount);

export function CostsCard(props: {
  costs: OpenAIDailyCost[];
  rangeDays: number;
  status: OpenAICostsStatus;
  message: string | null;
}) {
  const { costs, rangeDays, status, message } = props;

  const yesterday = costs.length > 0 ? costs[costs.length - 1] : null;
  const totalSpend = costs.reduce((sum, cost) => sum + (Number.isFinite(cost.amount) ? cost.amount : 0), 0);
  const chartData = costs.map((c) => ({
    date: c.date.slice(5),
    cost: Number.isFinite(c.amount) ? c.amount : 0,
  }));

  return (
    <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
      <div className="flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-[260px]">
          <div className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Total spend</div>
          <div className="mt-2 text-4xl font-semibold text-[#0f172a]">
            {chartData.length > 0 ? formatUsd(totalSpend) : "—"}
          </div>
          <div className="mt-2 text-sm text-[#4c576f]">OpenAI org costs (last {rangeDays} days)</div>
          <div className="mt-6 rounded-2xl border border-slate-200 bg-[#f7faff] px-4 py-3">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[#4c576f]">
              Yesterday&apos;s spend
            </div>
            <div className="mt-1 text-xl font-semibold text-[#0f172a]">
              {yesterday ? formatUsd(yesterday.amount) : "—"}
            </div>
          </div>
        </div>

        <div className="h-[240px] w-full lg:h-[260px]">
          {chartData.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-sm text-[#4c576f]">
              <div className="font-semibold text-[#0f172a]">
                {status === "missing_config" ? "Official spend not configured" : "Official spend unavailable"}
              </div>
              <div className="max-w-xl">
                {message ?? "Official spend is currently unavailable."}
              </div>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} stroke="#64748b" />
                <YAxis tick={{ fontSize: 12 }} stroke="#64748b" />
                <Tooltip formatter={(value) => formatUsd(Number(value))} labelFormatter={(label) => `Day: ${label}`} />
                <Bar dataKey="cost" name="Daily Cost" fill="#0a6fd6" radius={[10, 10, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
}
