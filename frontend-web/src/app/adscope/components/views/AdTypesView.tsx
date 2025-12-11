"use client";

import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    PieChart,
    Pie,
    Cell,
    Legend
} from "recharts";
import type { AdTypeMetric } from "../../types";
import { formatCurrency, formatNumber, formatPercent } from "../../utils/format";

interface AdTypesViewProps {
    data: AdTypeMetric[];
    currency: string;
}

const COLORS = ["#0077cc", "#f59e0b", "#10b981"]; // Blue (Primary), Amber, Emerald

export function AdTypesView({ data, currency }: AdTypesViewProps) {
    if (!data || data.length === 0) {
        return (
            <div className="flex h-full items-center justify-center text-slate-400">
                No ad type data available.
            </div>
        );
    }

    // Calculate totals for pie chart percentages
    const totalSpend = data.reduce((acc, curr) => acc + curr.spend, 0);
    const pieData = data.map(item => ({
        name: item.ad_type,
        value: item.spend,
        percent: totalSpend > 0 ? (item.spend / totalSpend) * 100 : 0
    }));

    // Sort data for consistent display
    const sortedData = [...data].sort((a, b) => b.spend - a.spend);

    return (
        <div className="space-y-6 p-6">
            {/* Top Row: Charts */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 h-[300px]">

                {/* Spend Distribution (Pie) */}
                <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col">
                    <h3 className="text-sm font-semibold text-slate-700 mb-4 uppercase tracking-wide">Spend Distribution</h3>
                    <div className="flex-1 min-h-0">
                        <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                                <Pie
                                    data={pieData}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={60}
                                    outerRadius={80}
                                    paddingAngle={5}
                                    dataKey="value"
                                >
                                    {pieData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                    ))}
                                </Pie>
                                <Tooltip
                                    formatter={(value: number) => formatCurrency(value, currency)}
                                    contentStyle={{ backgroundColor: "#ffffff", borderColor: "#e2e8f0", color: "#0f172a", borderRadius: "8px", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)" }}
                                    itemStyle={{ color: "#0f172a" }}
                                />
                                <Legend iconType="circle" />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* ACoS Comparison (Bar) */}
                <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col">
                    <h3 className="text-sm font-semibold text-slate-700 mb-4 uppercase tracking-wide">ACoS by Ad Type</h3>
                    <div className="flex-1 min-h-0">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={sortedData} layout="vertical" margin={{ top: 5, right: 30, left: 40, bottom: 5 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                                <XAxis type="number" stroke="#64748b" tickFormatter={(val) => `${val.toFixed(0)}%`} domain={[0, 'auto']} fontSize={12} />
                                <YAxis dataKey="ad_type" type="category" stroke="#64748b" width={100} fontSize={12} />
                                <Tooltip
                                    formatter={(value: number) => formatPercent(value)}
                                    cursor={{ fill: "#f1f5f9", opacity: 0.5 }}
                                    contentStyle={{ backgroundColor: "#ffffff", borderColor: "#e2e8f0", color: "#0f172a", borderRadius: "8px", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)" }}
                                    itemStyle={{ color: "#0f172a" }}
                                />
                                <Bar dataKey="acos" radius={[0, 4, 4, 0]} barSize={24}>
                                    {sortedData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.acos > 1 ? "#ef4444" : entry.acos > 0.4 ? "#f59e0b" : "#0077cc"} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>

            {/* Bottom Row: Data Table */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50">
                    <h3 className="text-sm font-semibold text-slate-800">Ad Type Performance</h3>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-slate-50 text-slate-500 uppercase text-xs font-semibold border-b border-slate-200">
                            <tr>
                                <th className="px-6 py-3 font-medium">Ad Type</th>
                                <th className="px-6 py-3 text-right font-medium">Active Camp.</th>
                                <th className="px-6 py-3 text-right font-medium">Spend</th>
                                <th className="px-6 py-3 text-right font-medium">Sales</th>
                                <th className="px-6 py-3 text-right font-medium">CPC</th>
                                <th className="px-6 py-3 text-right font-medium">CTR</th>
                                <th className="px-6 py-3 text-right font-medium">CVR</th>
                                <th className="px-6 py-3 text-right font-medium">ACoS</th>
                                <th className="px-6 py-3 text-right font-medium">ROAS</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {sortedData.map((row) => (
                                <tr key={row.ad_type} className="hover:bg-slate-50 transition-colors">
                                    <td className="px-6 py-4 font-medium text-slate-900">{row.ad_type}</td>
                                    <td className="px-6 py-4 text-right text-slate-600">{formatNumber(row.active_campaigns)}</td>
                                    <td className="px-6 py-4 text-right text-slate-900">{formatCurrency(row.spend, currency)}</td>
                                    <td className="px-6 py-4 text-right text-slate-900">{formatCurrency(row.sales, currency)}</td>
                                    <td className="px-6 py-4 text-right text-slate-600">{formatCurrency(row.cpc, currency)}</td>
                                    <td className="px-6 py-4 text-right text-slate-600">{formatPercent(row.ctr)}</td>
                                    <td className="px-6 py-4 text-right text-slate-600">{formatPercent(row.cvr)}</td>
                                    <td className={`px-6 py-4 text-right font-semibold ${row.acos > 1 ? "text-red-600" : row.acos > 0.4 ? "text-amber-600" : "text-emerald-600"
                                        }`}>
                                        {formatPercent(row.acos)}
                                    </td>
                                    <td className="px-6 py-4 text-right text-slate-600">{row.roas.toFixed(2)}x</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
