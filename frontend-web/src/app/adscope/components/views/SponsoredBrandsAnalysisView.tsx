"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { SponsoredBrandsView } from "../../types";
import { formatCurrency, formatNumber, formatPercent } from "../../utils/format";

interface SponsoredBrandsAnalysisViewProps {
  data: SponsoredBrandsView;
  currency: string;
}

const MATCH_TYPE_COLORS = [
  "#0077cc", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
  "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#6366f1",
];

const AD_FORMAT_COLORS = [
  "#0077cc", "#8b5cf6", "#10b981", "#f59e0b", "#ef4444",
  "#06b6d4", "#f97316",
];

export function SponsoredBrandsAnalysisView({ data, currency }: SponsoredBrandsAnalysisViewProps) {
  if (!data) {
    return (
      <div className="flex h-full items-center justify-center text-slate-400">
        No Sponsored Brands data available.
      </div>
    );
  }

  const { match_types, ad_formats } = data;

  const totalMatchSpend = match_types.reduce((acc, curr) => acc + curr.spend, 0);
  const matchPieData = match_types.map((item) => ({
    name: item.match_type,
    value: item.spend,
    percent: totalMatchSpend > 0 ? (item.spend / totalMatchSpend) * 100 : 0,
  }));

  const totalFormatSpend = ad_formats.reduce((acc, curr) => acc + curr.spend, 0);
  const formatPieData = ad_formats.map((item) => ({
    name: item.ad_format,
    value: item.spend,
    percent: totalFormatSpend > 0 ? (item.spend / totalFormatSpend) * 100 : 0,
  }));

  return (
    <div className="space-y-6 p-6">
      {/* Section 1: Match / Targeting Types */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50">
          <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wide">
            Sponsored Brands Match / Targeting Types
          </h3>
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-10 gap-0">
          {/* Pie Chart */}
          <div className="xl:col-span-3 p-6 border-b xl:border-b-0 xl:border-r border-slate-100">
            <div className="h-[260px] xl:h-[220px]">
              {matchPieData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={matchPieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={70}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {matchPieData.map((_, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={MATCH_TYPE_COLORS[index % MATCH_TYPE_COLORS.length]}
                        />
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
                  No match type data
                </div>
              )}
            </div>
          </div>
          {/* Table */}
          <div className="xl:col-span-7 overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-slate-50 text-slate-500 uppercase text-xs font-semibold border-b border-slate-200">
                <tr>
                  <th className="px-6 py-3 font-medium">Type</th>
                  <th className="px-6 py-3 text-right font-medium"># Targets</th>
                  <th className="px-6 py-3 text-right font-medium">Spend</th>
                  <th className="px-6 py-3 text-right font-medium">Sales</th>
                  <th className="px-6 py-3 text-right font-medium hidden xl:table-cell">CPC</th>
                  <th className="px-6 py-3 text-right font-medium hidden xl:table-cell">CTR</th>
                  <th className="px-6 py-3 text-right font-medium hidden xl:table-cell">CVR</th>
                  <th className="px-6 py-3 text-right font-medium">ACoS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {match_types.length > 0 ? (
                  match_types.map((row, index) => (
                    <tr key={`${row.match_type}-${index}`} className="hover:bg-slate-50 transition-colors">
                      <td className="px-6 py-4 font-medium text-slate-900 flex items-center gap-2">
                        <span
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: MATCH_TYPE_COLORS[index % MATCH_TYPE_COLORS.length] }}
                        />
                        {row.match_type}
                      </td>
                      <td className="px-6 py-4 text-right text-slate-600">{formatNumber(row.target_count)}</td>
                      <td className="px-6 py-4 text-right text-slate-900">{formatCurrency(row.spend, currency)}</td>
                      <td className="px-6 py-4 text-right text-slate-900">{formatCurrency(row.sales, currency)}</td>
                      <td className="px-6 py-4 text-right text-slate-600 hidden xl:table-cell">{formatCurrency(row.cpc, currency)}</td>
                      <td className="px-6 py-4 text-right text-slate-600 hidden xl:table-cell">{formatPercent(row.ctr)}</td>
                      <td className="px-6 py-4 text-right text-slate-600 hidden xl:table-cell">{formatPercent(row.cvr)}</td>
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
                    <td colSpan={5} className="px-6 py-8 text-center text-slate-400">
                      No match type data available
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Section 2: Ad Formats */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50">
          <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wide">
            Sponsored Brands Ad Formats
          </h3>
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-10 gap-0">
          {/* Pie Chart */}
          <div className="xl:col-span-3 p-6 border-b xl:border-b-0 xl:border-r border-slate-100">
            <div className="h-[260px] xl:h-[220px]">
              {formatPieData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={formatPieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={70}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {formatPieData.map((_, index) => (
                        <Cell
                          key={`cell-format-${index}`}
                          fill={AD_FORMAT_COLORS[index % AD_FORMAT_COLORS.length]}
                        />
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
                  No ad format data
                </div>
              )}
            </div>
          </div>
          {/* Table */}
          <div className="xl:col-span-7 overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-slate-50 text-slate-500 uppercase text-xs font-semibold border-b border-slate-200">
                <tr>
                  <th className="px-6 py-3 font-medium">Ad Format</th>
                  <th className="px-6 py-3 text-right font-medium">Campaigns</th>
                  <th className="px-6 py-3 text-right font-medium">Spend</th>
                  <th className="px-6 py-3 text-right font-medium">Sales</th>
                  <th className="px-6 py-3 text-right font-medium">ACoS</th>
                  <th className="px-6 py-3 text-right font-medium">ROAS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {ad_formats.length > 0 ? (
                  ad_formats.map((row, index) => (
                    <tr key={`${row.ad_format}-${index}`} className="hover:bg-slate-50 transition-colors">
                      <td className="px-6 py-4 font-medium text-slate-900 flex items-center gap-2">
                        <span
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: AD_FORMAT_COLORS[index % AD_FORMAT_COLORS.length] }}
                        />
                        {row.ad_format}
                      </td>
                      <td className="px-6 py-4 text-right text-slate-600">{formatNumber(row.campaigns)}</td>
                      <td className="px-6 py-4 text-right text-slate-900">{formatCurrency(row.spend, currency)}</td>
                      <td className="px-6 py-4 text-right text-slate-900">{formatCurrency(row.sales, currency)}</td>
                      <td
                        className={`px-6 py-4 text-right font-semibold ${
                          row.acos > 1 ? "text-red-600" : row.acos > 0.4 ? "text-amber-600" : "text-emerald-600"
                        }`}
                      >
                        {formatPercent(row.acos)}
                      </td>
                      <td className="px-6 py-4 text-right text-slate-600">{row.roas.toFixed(2)}x</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="px-6 py-8 text-center text-slate-400">
                      No ad format data available
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
