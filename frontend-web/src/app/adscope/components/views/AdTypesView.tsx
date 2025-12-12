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
import { formatCurrency, formatNumber, formatPercent, formatCompact } from "../../utils/format";

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

    // Calculate totals from ad type data
    const totalSpend = data.reduce((acc, curr) => acc + curr.spend, 0);
    const totalSales = data.reduce((acc, curr) => acc + curr.sales, 0);
    const totalImpressions = data.reduce((acc, curr) => acc + curr.impressions, 0);
    const totalClicks = data.reduce((acc, curr) => acc + curr.clicks, 0);
    const totalOrders = data.reduce((acc, curr) => acc + curr.orders, 0);
    const overallAcos = totalSales > 0 ? totalSpend / totalSales : 0;
    const overallCtr = totalImpressions > 0 ? totalClicks / totalImpressions : 0;
    const overallCvr = totalClicks > 0 ? totalOrders / totalClicks : 0;

    // Prepare pie data
    const pieData = data.map(item => ({
        name: item.ad_type,
        value: item.spend,
        percent: totalSpend > 0 ? (item.spend / totalSpend) * 100 : 0
    }));

    // Sort data for consistent display
    const sortedData = [...data].sort((a, b) => b.spend - a.spend);

    // ACOS color helper
    const getAcosColor = (acos: number) => {
        if (acos > 1) return "text-red-600";
        if (acos > 0.4) return "text-amber-600";
        return "text-emerald-600";
    };

    const getAcosBgColor = (acos: number) => {
        if (acos > 1) return "bg-red-500";
        if (acos > 0.4) return "bg-amber-500";
        return "bg-emerald-500";
    };

    return (
        <div className="space-y-6 p-6">
            {/* Summary Cards Row */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Total Spend */}
                <div className="rounded-xl bg-white border border-slate-200 shadow-sm p-6">
                    <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Total Ad Spend</h3>
                    <p className="text-3xl font-bold text-slate-900">{formatCurrency(totalSpend, currency)}</p>
                    <p className="text-sm text-slate-500 mt-1">{formatNumber(totalClicks)} clicks</p>
                </div>

                {/* Total Sales */}
                <div className="rounded-xl bg-white border border-slate-200 shadow-sm p-6">
                    <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Total Ad Sales</h3>
                    <p className="text-3xl font-bold text-slate-900">{formatCurrency(totalSales, currency)}</p>
                    <p className="text-sm text-slate-500 mt-1">{formatNumber(totalOrders)} orders</p>
                </div>

                {/* Overall ACoS */}
                <div className="rounded-xl bg-white border border-slate-200 shadow-sm p-6">
                    <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Overall ACoS</h3>
                    <div className="flex items-baseline gap-3">
                        <p className={`text-3xl font-bold ${getAcosColor(overallAcos)}`}>{formatPercent(overallAcos)}</p>
                        <span className="text-sm text-slate-400">Target: 30%</span>
                    </div>
                    <div className="w-full bg-slate-100 rounded-full h-2 mt-3">
                        <div
                            className={`h-2 rounded-full ${getAcosBgColor(overallAcos)}`}
                            style={{ width: `${Math.min(overallAcos * 200, 100)}%` }}
                        ></div>
                    </div>
                </div>
            </div>

            {/* Funnel Section - Redesigned */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
                <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wide mb-6">Conversion Funnel</h3>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    {/* Custom SVG Funnel with Labels Inside */}
                    <div className="flex items-center justify-center">
                        <svg viewBox="0 0 300 220" className="w-full max-w-[320px] h-auto">
                            {/* Impressions - Top (widest) */}
                            <path
                                d="M 20 10 L 280 10 L 250 70 L 50 70 Z"
                                fill="#0077cc"
                            />
                            <text x="150" y="30" textAnchor="middle" fill="white" fontSize="11" fontWeight="500">IMPRESSIONS</text>
                            <text x="150" y="52" textAnchor="middle" fill="white" fontSize="18" fontWeight="700">{formatCompact(totalImpressions)}</text>

                            {/* Clicks - Middle */}
                            <path
                                d="M 50 75 L 250 75 L 210 135 L 90 135 Z"
                                fill="#3b82f6"
                            />
                            <text x="150" y="95" textAnchor="middle" fill="white" fontSize="11" fontWeight="500">CLICKS</text>
                            <text x="150" y="117" textAnchor="middle" fill="white" fontSize="18" fontWeight="700">{formatCompact(totalClicks)}</text>

                            {/* Orders - Bottom (narrowest) */}
                            <path
                                d="M 90 140 L 210 140 L 180 200 L 120 200 Z"
                                fill="#60a5fa"
                            />
                            <text x="150" y="160" textAnchor="middle" fill="white" fontSize="11" fontWeight="500">ORDERS</text>
                            <text x="150" y="182" textAnchor="middle" fill="white" fontSize="18" fontWeight="700">{formatNumber(totalOrders)}</text>
                        </svg>
                    </div>

                    {/* Funnel Metrics Cards */}
                    <div className="flex flex-col justify-center space-y-4">
                        {/* Impressions Card */}
                        <div className="p-4 bg-slate-50 rounded-xl">
                            <p className="text-xs font-semibold uppercase text-slate-500 mb-1">Impressions</p>
                            <p className="text-2xl font-bold text-slate-900">{formatCompact(totalImpressions)}</p>
                        </div>

                        {/* CTR Card */}
                        <div className="p-4 bg-slate-100 rounded-xl ml-4">
                            <p className="text-xs font-semibold uppercase text-slate-500 mb-1">CTR</p>
                            <p className="text-2xl font-bold text-[#0077cc]">{formatPercent(overallCtr)}</p>
                        </div>

                        {/* Clicks Card */}
                        <div className="p-4 bg-slate-50 rounded-xl">
                            <p className="text-xs font-semibold uppercase text-slate-500 mb-1">Clicks</p>
                            <p className="text-2xl font-bold text-slate-900">{formatCompact(totalClicks)}</p>
                        </div>

                        {/* CVR Card */}
                        <div className="p-4 bg-slate-100 rounded-xl ml-4">
                            <p className="text-xs font-semibold uppercase text-slate-500 mb-1">CVR</p>
                            <p className="text-2xl font-bold text-[#0077cc]">{formatPercent(overallCvr)}</p>
                        </div>

                        {/* Orders Card */}
                        <div className="p-4 bg-slate-50 rounded-xl">
                            <p className="text-xs font-semibold uppercase text-slate-500 mb-1">Orders</p>
                            <p className="text-2xl font-bold text-slate-900">{formatNumber(totalOrders)}</p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Ad Types Charts Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 h-[300px]">
                {/* Spend Distribution (Pie) */}
                <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col">
                    <h3 className="text-sm font-semibold text-slate-700 mb-4 uppercase tracking-wide">Spend by Ad Type</h3>
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
                                    formatter={(_value, _name, props) => {
                                        const pct = (props?.payload as { percent?: number })?.percent ?? 0;
                                        return `${pct.toFixed(1)}%`;
                                    }}
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
                                <XAxis type="number" stroke="#64748b" tickFormatter={(val) => `${(val * 100).toFixed(0)}%`} domain={[0, 'auto']} fontSize={12} />
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

            {/* Ad Type Performance Table */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50">
                    <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wide">Ad Type Performance</h3>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-slate-50 text-slate-500 uppercase text-xs font-semibold border-b border-slate-200">
                            <tr>
                                <th className="px-6 py-3 font-medium">Ad Type</th>
                                <th className="px-6 py-3 text-right font-medium">Campaigns</th>
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
                            {sortedData.map((row, index) => (
                                <tr key={row.ad_type} className="hover:bg-slate-50 transition-colors">
                                    <td className="px-6 py-4 font-medium text-slate-900 flex items-center gap-2">
                                        <span
                                            className="w-3 h-3 rounded-full"
                                            style={{ backgroundColor: COLORS[index % COLORS.length] }}
                                        />
                                        {row.ad_type}
                                    </td>
                                    <td className="px-6 py-4 text-right text-slate-600">{formatNumber(row.active_campaigns)}</td>
                                    <td className="px-6 py-4 text-right text-slate-900">{formatCurrency(row.spend, currency)}</td>
                                    <td className="px-6 py-4 text-right text-slate-900">{formatCurrency(row.sales, currency)}</td>
                                    <td className="px-6 py-4 text-right text-slate-600">{formatCurrency(row.cpc, currency)}</td>
                                    <td className="px-6 py-4 text-right text-slate-600">{formatPercent(row.ctr)}</td>
                                    <td className="px-6 py-4 text-right text-slate-600">{formatPercent(row.cvr)}</td>
                                    <td className={`px-6 py-4 text-right font-semibold ${getAcosColor(row.acos)}`}>
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
