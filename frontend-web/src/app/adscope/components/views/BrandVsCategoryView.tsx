"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { BrandVsCategoryView } from "../../types";
import { formatCurrency, formatNumber, formatPercent } from "../../utils/format";

interface BrandVsCategoryViewProps {
  data: BrandVsCategoryView;
  currency: string;
}

const COLORS = ["#0077cc", "#10b981", "#f59e0b"];

export function BrandVsCategoryView({ data, currency }: BrandVsCategoryViewProps) {
  const segments = data?.segments ?? [];

  if (!segments || segments.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-slate-400">
        No Brand vs Category data available.
      </div>
    );
  }

  const totalSpend = segments.reduce((acc, curr) => acc + curr.spend, 0);
  const pieData = segments.map((row) => ({
    name: row.segment,
    value: row.spend,
    percent: totalSpend > 0 ? (row.spend / totalSpend) * 100 : 0,
  }));

  return (
    <div className="space-y-6 p-6">
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50">
          <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wide">
            Brand vs Category
          </h3>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-10 gap-0">
          {/* Pie Chart */}
          <div className="lg:col-span-3 p-6 border-b lg:border-b-0 lg:border-r border-slate-100">
            <div className="h-[220px]">
              {pieData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={70}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {pieData.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(_value, _name, props) => {
                        const pct = (props?.payload as { percent?: number })?.percent ?? 0;
                        return `${pct.toFixed(1)}%`;
                      }}
                      contentStyle={{
                        backgroundColor: "#ffffff",
                        borderColor: "#e2e8f0",
                        color: "#0f172a",
                        borderRadius: "8px",
                        boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                      }}
                      itemStyle={{ color: "#0f172a" }}
                    />
                    <Legend
                      iconType="circle"
                      layout="vertical"
                      align="left"
                      verticalAlign="middle"
                      wrapperStyle={{ fontSize: "11px", paddingLeft: "10px" }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-slate-400 text-sm">
                  No data
                </div>
              )}
            </div>
          </div>

          {/* Table */}
          <div className="lg:col-span-7 overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-slate-50 text-slate-500 uppercase text-xs font-semibold border-b border-slate-200">
                <tr>
                  <th className="px-6 py-3 font-medium">Segment</th>
                  <th className="px-6 py-3 text-right font-medium">Spend</th>
                  <th className="px-6 py-3 text-right font-medium">% Spend</th>
                  <th className="px-6 py-3 text-right font-medium">Sales</th>
                  <th className="px-6 py-3 text-right font-medium">Orders</th>
                  <th className="px-6 py-3 text-right font-medium">CTR</th>
                  <th className="px-6 py-3 text-right font-medium">CVR</th>
                  <th className="px-6 py-3 text-right font-medium">ACoS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {segments.map((row, index) => (
                  <tr key={`${row.segment}-${index}`} className="hover:bg-slate-50 transition-colors">
                    <td className="px-6 py-4 font-medium text-slate-900 flex items-center gap-2">
                      <span
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: COLORS[index % COLORS.length] }}
                      />
                      {row.segment}
                    </td>
                    <td className="px-6 py-4 text-right text-slate-900">{formatCurrency(row.spend, currency)}</td>
                    <td className="px-6 py-4 text-right text-slate-600">{formatPercent(row.spend_percent)}</td>
                    <td className="px-6 py-4 text-right text-slate-900">{formatCurrency(row.sales, currency)}</td>
                    <td className="px-6 py-4 text-right text-slate-600 font-mono">{formatNumber(row.orders)}</td>
                    <td className="px-6 py-4 text-right text-slate-600">{formatPercent(row.ctr)}</td>
                    <td className="px-6 py-4 text-right text-slate-600">{formatPercent(row.cvr)}</td>
                    <td
                      className={`px-6 py-4 text-right font-semibold ${
                        row.acos > 1 ? "text-red-600" : row.acos > 0.4 ? "text-amber-600" : "text-emerald-600"
                      }`}
                    >
                      {formatPercent(row.acos)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

