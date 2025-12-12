"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { SponsoredDisplayTargetingView } from "../../types";
import { formatCurrency, formatNumber, formatPercent } from "../../utils/format";

interface SponsoredDisplayTargetingViewProps {
  data: SponsoredDisplayTargetingView;
  currency: string;
}

const COLORS = [
  "#0077cc",
  "#10b981",
  "#f59e0b",
  "#8b5cf6",
  "#ef4444",
  "#06b6d4",
];

export function SponsoredDisplayTargetingView({ data, currency }: SponsoredDisplayTargetingViewProps) {
  const targetingTypes = data?.targeting_types ?? [];
  const refinements = data?.category_refinements ?? [];

  const totalTargetingSpend = targetingTypes.reduce((acc, curr) => acc + curr.spend, 0);
  const targetingPieData = targetingTypes.map((row) => ({
    name: row.targeting_type,
    value: row.spend,
    percent: totalTargetingSpend > 0 ? (row.spend / totalTargetingSpend) * 100 : 0,
  }));

  const totalRefSpend = refinements.reduce((acc, curr) => acc + curr.spend, 0);
  const refPieData = refinements.map((row) => ({
    name: row.refinement,
    value: row.spend,
    percent: totalRefSpend > 0 ? (row.spend / totalRefSpend) * 100 : 0,
  }));

  return (
    <div className="space-y-6 p-6">
      {/* Section 1: Targeting Types */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50">
          <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wide">
            Sponsored Display Targeting Types
          </h3>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-10 gap-0">
          <div className="lg:col-span-3 p-6 border-b lg:border-b-0 lg:border-r border-slate-100">
            <div className="h-[220px]">
              {targetingPieData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={targetingPieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={70}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {targetingPieData.map((_, index) => (
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
                  No targeting data
                </div>
              )}
            </div>
          </div>

          <div className="lg:col-span-7 overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-slate-50 text-slate-500 uppercase text-xs font-semibold border-b border-slate-200">
                <tr>
                  <th className="px-6 py-3 font-medium">Type</th>
                  <th className="px-6 py-3 text-right font-medium"># Targets</th>
                  <th className="px-6 py-3 text-right font-medium">Spend</th>
                  <th className="px-6 py-3 text-right font-medium">Sales</th>
                  <th className="px-6 py-3 text-right font-medium">CPC</th>
                  <th className="px-6 py-3 text-right font-medium">CTR</th>
                  <th className="px-6 py-3 text-right font-medium">CVR</th>
                  <th className="px-6 py-3 text-right font-medium">ACoS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {targetingTypes.length > 0 ? (
                  targetingTypes.map((row, index) => (
                    <tr key={`${row.targeting_type}-${index}`} className="hover:bg-slate-50 transition-colors">
                      <td className="px-6 py-4 font-medium text-slate-900 flex items-center gap-2">
                        <span className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }} />
                        {row.targeting_type}
                      </td>
                      <td className="px-6 py-4 text-right text-slate-600">{formatNumber(row.target_count)}</td>
                      <td className="px-6 py-4 text-right text-slate-900">{formatCurrency(row.spend, currency)}</td>
                      <td className="px-6 py-4 text-right text-slate-900">{formatCurrency(row.sales, currency)}</td>
                      <td className="px-6 py-4 text-right text-slate-600">{formatCurrency(row.cpc, currency)}</td>
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
                  ))
                ) : (
                  <tr>
                    <td colSpan={8} className="px-6 py-8 text-center text-slate-400">
                      No targeting data available
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Section 2: Category Targeting Refinements */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50">
          <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wide">
            Category Targeting Refinements
          </h3>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-10 gap-0">
          <div className="lg:col-span-3 p-6 border-b lg:border-b-0 lg:border-r border-slate-100">
            <div className="h-[220px]">
              {refPieData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={refPieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={70}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {refPieData.map((_, index) => (
                        <Cell key={`cell-ref-${index}`} fill={COLORS[index % COLORS.length]} />
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
                  No refinement data
                </div>
              )}
            </div>
          </div>

          <div className="lg:col-span-7 overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-slate-50 text-slate-500 uppercase text-xs font-semibold border-b border-slate-200">
                <tr>
                  <th className="px-6 py-3 font-medium">Refinement</th>
                  <th className="px-6 py-3 text-right font-medium"># Targets</th>
                  <th className="px-6 py-3 text-right font-medium">Spend</th>
                  <th className="px-6 py-3 text-right font-medium">Sales</th>
                  <th className="px-6 py-3 text-right font-medium">CPC</th>
                  <th className="px-6 py-3 text-right font-medium">CTR</th>
                  <th className="px-6 py-3 text-right font-medium">CVR</th>
                  <th className="px-6 py-3 text-right font-medium">ACoS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {refinements.length > 0 ? (
                  refinements.map((row, index) => (
                    <tr key={`${row.refinement}-${index}`} className="hover:bg-slate-50 transition-colors">
                      <td className="px-6 py-4 font-medium text-slate-900 flex items-center gap-2">
                        <span className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }} />
                        {row.refinement}
                      </td>
                      <td className="px-6 py-4 text-right text-slate-600">{formatNumber(row.target_count)}</td>
                      <td className="px-6 py-4 text-right text-slate-900">{formatCurrency(row.spend, currency)}</td>
                      <td className="px-6 py-4 text-right text-slate-900">{formatCurrency(row.sales, currency)}</td>
                      <td className="px-6 py-4 text-right text-slate-600">{formatCurrency(row.cpc, currency)}</td>
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
                  ))
                ) : (
                  <tr>
                    <td colSpan={8} className="px-6 py-8 text-center text-slate-400">
                      No category refinement data available
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

