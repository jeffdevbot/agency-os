"use client";

import {
    PieChart,
    Pie,
    Cell,
    Tooltip,
    ResponsiveContainer,
    Legend
} from "recharts";
import type { BiddingStrategy, Placement } from "../../types";
import { formatCurrency, formatNumber, formatPercent } from "../../utils/format";

interface BiddingPlacementsViewProps {
    biddingStrategies: BiddingStrategy[];
    placements: Placement[];
    currency: string;
}

const STRATEGY_COLORS = ["#0077cc", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];
const PLACEMENT_COLORS = ["#0077cc", "#3b82f6", "#60a5fa", "#93c5fd"];

export function BiddingPlacementsView({ biddingStrategies, placements, currency }: BiddingPlacementsViewProps) {
    // Prepare pie data for bidding strategies
    const totalStrategySpend = biddingStrategies.reduce((acc, curr) => acc + curr.spend, 0);
    const strategyPieData = biddingStrategies.map(item => ({
        name: item.strategy,
        value: item.spend,
        percent: totalStrategySpend > 0 ? (item.spend / totalStrategySpend) * 100 : 0
    }));

    // Prepare pie data for placements
    const totalPlacementSpend = placements.reduce((acc, curr) => acc + curr.spend, 0);
    const placementPieData = placements.map(item => ({
        name: item.placement,
        value: item.spend,
        percent: totalPlacementSpend > 0 ? (item.spend / totalPlacementSpend) * 100 : 0
    }));

    // ACOS color helper
    const getAcosColor = (acos: number) => {
        if (acos > 1) return "text-red-600";
        if (acos > 0.4) return "text-amber-600";
        return "text-emerald-600";
    };

    return (
        <div className="space-y-6 p-6">
            {/* Section 1: Bidding Strategy */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50">
                    <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wide">Bidding Strategy</h3>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-10 gap-0">
                    {/* Pie Chart - 30% */}
                    <div className="lg:col-span-3 p-6 border-b lg:border-b-0 lg:border-r border-slate-100">
                        <div className="h-[220px]">
                            {strategyPieData.length > 0 ? (
                                <ResponsiveContainer width="100%" height="100%">
                                    <PieChart>
                                        <Pie
                                            data={strategyPieData}
                                            cx="50%"
                                            cy="50%"
                                            innerRadius={50}
                                            outerRadius={70}
                                            paddingAngle={5}
                                            dataKey="value"
                                            label={({ percent }) => `${(percent ?? 0).toFixed(0)}%`}
                                            labelLine={false}
                                        >
                                            {strategyPieData.map((entry, index) => (
                                                <Cell key={`cell-${index}`} fill={STRATEGY_COLORS[index % STRATEGY_COLORS.length]} />
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
                                        <Legend iconType="circle" wrapperStyle={{ fontSize: "12px" }} />
                                    </PieChart>
                                </ResponsiveContainer>
                            ) : (
                                <div className="flex h-full items-center justify-center text-slate-400 text-sm">
                                    No bidding strategy data
                                </div>
                            )}
                        </div>
                    </div>
                    {/* Table - 70% */}
                    <div className="lg:col-span-7 overflow-x-auto">
                        <table className="w-full text-sm text-left">
                            <thead className="bg-slate-50 text-slate-500 uppercase text-xs font-semibold border-b border-slate-200">
                                <tr>
                                    <th className="px-6 py-3 font-medium">Strategy</th>
                                    <th className="px-6 py-3 text-right font-medium"># Active</th>
                                    <th className="px-6 py-3 text-right font-medium">Spend %</th>
                                    <th className="px-6 py-3 text-right font-medium">Spend</th>
                                    <th className="px-6 py-3 text-right font-medium">Sales</th>
                                    <th className="px-6 py-3 text-right font-medium">CPC</th>
                                    <th className="px-6 py-3 text-right font-medium">CTR</th>
                                    <th className="px-6 py-3 text-right font-medium">CVR</th>
                                    <th className="px-6 py-3 text-right font-medium">ACoS</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {biddingStrategies.length > 0 ? (
                                    biddingStrategies.map((row, index) => (
                                        <tr key={row.strategy} className="hover:bg-slate-50 transition-colors">
                                            <td className="px-6 py-4 font-medium text-slate-900 flex items-center gap-2">
                                                <span
                                                    className="w-3 h-3 rounded-full flex-shrink-0"
                                                    style={{ backgroundColor: STRATEGY_COLORS[index % STRATEGY_COLORS.length] }}
                                                />
                                                {row.strategy}
                                            </td>
                                            <td className="px-6 py-4 text-right text-slate-600">{formatNumber(row.count)}</td>
                                            <td className="px-6 py-4 text-right text-slate-600">{formatPercent(row.spend_percent)}</td>
                                            <td className="px-6 py-4 text-right text-slate-900">{formatCurrency(row.spend, currency)}</td>
                                            <td className="px-6 py-4 text-right text-slate-900">{formatCurrency(row.sales, currency)}</td>
                                            <td className="px-6 py-4 text-right text-slate-600">{formatCurrency(row.cpc, currency)}</td>
                                            <td className="px-6 py-4 text-right text-slate-600">{formatPercent(row.ctr)}</td>
                                            <td className="px-6 py-4 text-right text-slate-600">{formatPercent(row.cvr)}</td>
                                            <td className={`px-6 py-4 text-right font-semibold ${getAcosColor(row.acos)}`}>
                                                {formatPercent(row.acos)}
                                            </td>
                                        </tr>
                                    ))
                                ) : (
                                    <tr>
                                        <td colSpan={9} className="px-6 py-8 text-center text-slate-400">
                                            No bidding strategy data available
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            {/* Section 2: Placements */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50">
                    <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wide">Placements</h3>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-10 gap-0">
                    {/* Pie Chart - 30% */}
                    <div className="lg:col-span-3 p-6 border-b lg:border-b-0 lg:border-r border-slate-100">
                        <div className="h-[220px]">
                            {placementPieData.length > 0 ? (
                                <ResponsiveContainer width="100%" height="100%">
                                    <PieChart>
                                        <Pie
                                            data={placementPieData}
                                            cx="50%"
                                            cy="50%"
                                            innerRadius={50}
                                            outerRadius={70}
                                            paddingAngle={5}
                                            dataKey="value"
                                            label={({ percent }) => `${(percent ?? 0).toFixed(0)}%`}
                                            labelLine={false}
                                        >
                                            {placementPieData.map((entry, index) => (
                                                <Cell key={`cell-${index}`} fill={PLACEMENT_COLORS[index % PLACEMENT_COLORS.length]} />
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
                                        <Legend iconType="circle" wrapperStyle={{ fontSize: "12px" }} />
                                    </PieChart>
                                </ResponsiveContainer>
                            ) : (
                                <div className="flex h-full items-center justify-center text-slate-400 text-sm">
                                    No placement data
                                </div>
                            )}
                        </div>
                    </div>
                    {/* Table - 70% */}
                    <div className="lg:col-span-7 overflow-x-auto">
                        <table className="w-full text-sm text-left">
                            <thead className="bg-slate-50 text-slate-500 uppercase text-xs font-semibold border-b border-slate-200">
                                <tr>
                                    <th className="px-6 py-3 font-medium">Placement</th>
                                    <th className="px-6 py-3 text-right font-medium"># Active</th>
                                    <th className="px-6 py-3 text-right font-medium">Spend %</th>
                                    <th className="px-6 py-3 text-right font-medium">Spend</th>
                                    <th className="px-6 py-3 text-right font-medium">Sales</th>
                                    <th className="px-6 py-3 text-right font-medium">CPC</th>
                                    <th className="px-6 py-3 text-right font-medium">CTR</th>
                                    <th className="px-6 py-3 text-right font-medium">CVR</th>
                                    <th className="px-6 py-3 text-right font-medium">ACoS</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {placements.length > 0 ? (
                                    placements.map((row, index) => (
                                        <tr key={row.placement} className="hover:bg-slate-50 transition-colors">
                                            <td className="px-6 py-4 font-medium text-slate-900 flex items-center gap-2">
                                                <span
                                                    className="w-3 h-3 rounded-full flex-shrink-0"
                                                    style={{ backgroundColor: PLACEMENT_COLORS[index % PLACEMENT_COLORS.length] }}
                                                />
                                                {row.placement}
                                            </td>
                                            <td className="px-6 py-4 text-right text-slate-600">{formatNumber(row.count)}</td>
                                            <td className="px-6 py-4 text-right text-slate-600">{formatPercent(row.spend_percent)}</td>
                                            <td className="px-6 py-4 text-right text-slate-900">{formatCurrency(row.spend, currency)}</td>
                                            <td className="px-6 py-4 text-right text-slate-900">{formatCurrency(row.sales, currency)}</td>
                                            <td className="px-6 py-4 text-right text-slate-600">{formatCurrency(row.cpc, currency)}</td>
                                            <td className="px-6 py-4 text-right text-slate-600">{formatPercent(row.ctr)}</td>
                                            <td className="px-6 py-4 text-right text-slate-600">{formatPercent(row.cvr)}</td>
                                            <td className={`px-6 py-4 text-right font-semibold ${getAcosColor(row.acos)}`}>
                                                {formatPercent(row.acos)}
                                            </td>
                                        </tr>
                                    ))
                                ) : (
                                    <tr>
                                        <td colSpan={9} className="px-6 py-8 text-center text-slate-400">
                                            No placement data available
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
