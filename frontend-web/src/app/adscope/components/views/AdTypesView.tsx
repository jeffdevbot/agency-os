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

const COLORS = ["#3b82f6", "#10b981", "#f59e0b"];

export function AdTypesView({ data, currency }: AdTypesViewProps) {
    if (!data || data.length === 0) {
        return (
            <div className="flex h-full items-center justify-center text-slate-500">
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
                <div className="bg-slate-900 rounded-lg p-4 border border-slate-800 flex flex-col">
                    <h3 className="text-sm font-medium text-slate-400 mb-4">Ad Spend Distribution</h3>
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
                                    contentStyle={{ backgroundColor: "#1e293b", borderColor: "#334155", color: "#f8fafc" }}
                                />
                                <Legend />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* ACoS Comparison (Bar) */}
                <div className="bg-slate-900 rounded-lg p-4 border border-slate-800 flex flex-col">
                    <h3 className="text-sm font-medium text-slate-400 mb-4">ACoS by Ad Type</h3>
                    <div className="flex-1 min-h-0">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={sortedData} layout="vertical" margin={{ top: 5, right: 30, left: 40, bottom: 5 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
                                <XAxis type="number" stroke="#94a3b8" tickFormatter={(val) => `${val.toFixed(0)}%`} domain={[0, 'auto']} />
                                <YAxis dataKey="ad_type" type="category" stroke="#94a3b8" width={100} />
                                <Tooltip
                                    formatter={(value: number) => formatPercent(value)}
                                    cursor={{ fill: "#334155", opacity: 0.2 }}
                                    contentStyle={{ backgroundColor: "#1e293b", borderColor: "#334155", color: "#f8fafc" }}
                                />
                                <Bar dataKey="acos" fill="#3b82f6" radius={[0, 4, 4, 0]} barSize={20}>
                                    {sortedData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.acos > 1 ? "#ef4444" : entry.acos > 0.4 ? "#f59e0b" : "#10b981"} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>

            {/* Bottom Row: Data Table */}
            <div className="bg-slate-900 rounded-lg border border-slate-800">
                <div className="px-6 py-4 border-b border-slate-800">
                    <h3 className="text-sm font-medium text-slate-200">Ad Type Performance</h3>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-slate-950 text-slate-400 uppercase text-xs font-semibold">
                            <tr>
                                <th className="px-6 py-3">Ad Type</th>
                                <th className="px-6 py-3 text-right">Active Camp.</th>
                                <th className="px-6 py-3 text-right">Spend</th>
                                <th className="px-6 py-3 text-right">Sales</th>
                                <th className="px-6 py-3 text-right">CPC</th>
                                <th className="px-6 py-3 text-right">CTR</th>
                                <th className="px-6 py-3 text-right">CVR</th>
                                <th className="px-6 py-3 text-right">ACoS</th>
                                <th className="px-6 py-3 text-right">ROAS</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800">
                            {sortedData.map((row) => (
                                <tr key={row.ad_type} className="hover:bg-slate-800/50 transition-colors">
                                    <td className="px-6 py-4 font-medium text-slate-200">{row.ad_type}</td>
                                    <td className="px-6 py-4 text-right text-slate-400">{formatNumber(row.active_campaigns)}</td>
                                    <td className="px-6 py-4 text-right text-slate-200">{formatCurrency(row.spend, currency)}</td>
                                    <td className="px-6 py-4 text-right text-slate-200">{formatCurrency(row.sales, currency)}</td>
                                    <td className="px-6 py-4 text-right text-slate-400">{formatCurrency(row.cpc, currency)}</td>
                                    <td className="px-6 py-4 text-right text-slate-400">{formatPercent(row.ctr)}</td>
                                    <td className="px-6 py-4 text-right text-slate-400">{formatPercent(row.cvr)}</td>
                                    <td className={`px-6 py-4 text-right font-medium ${row.acos > 1 ? "text-red-400" : row.acos > 0.4 ? "text-amber-400" : "text-green-400"
                                        }`}>
                                        {formatPercent(row.acos)}
                                    </td>
                                    <td className="px-6 py-4 text-right text-slate-400">{row.roas.toFixed(2)}x</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
