"use client";

import {
    FileText,
    LayoutDashboard,
    Trash2,
    DollarSign,
    PieChart,
    Target,
    BarChart2,
    List,
    Fingerprint,
    Ghost,
    Search,
    Users,
    AlertTriangle,
    Copy,
    FolderOpen
} from "lucide-react";
import type { ViewId } from "../types";

interface ExplorerPaneProps {
    activeView: ViewId;
    onViewChange: (viewId: ViewId) => void;
    onReset: () => void;
}

const SECTIONS = [
    {
        title: "Dashboard",
        items: [
            { id: "overview", label: "Overview", icon: LayoutDashboard },
        ]
    },
    {
        title: "Performance",
        items: [
            { id: "ad_types", label: "Ad Types", icon: PieChart },
        ]
    },
    {
        title: "Optimization",
        items: [
            { id: "money_pits", label: "Money Pits", icon: DollarSign },
            { id: "waste_bin", label: "Waste Bin", icon: Trash2 },
            { id: "budget_cappers", label: "Budget Cappers", icon: Target },
            { id: "zombies", label: "Zombies", icon: Ghost },
        ]
    },
    {
        title: "Analysis",
        items: [
            { id: "brand_analysis", label: "Brand vs Generic", icon: PieChart },
            { id: "placements", label: "Placements", icon: BarChart2 },
            { id: "match_types", label: "Match Types", icon: Fingerprint },
            { id: "price_sensitivity", label: "Price Sensitivity", icon: DollarSign },
            { id: "campaign_scatter", label: "Campaign Dist.", icon: FolderOpen },
        ]
    },
    {
        title: "Deep Dive",
        items: [
            { id: "keyword_leaderboard", label: "Leaderboard", icon: List },
            { id: "n_grams", label: "N-Grams", icon: Search },
            { id: "duplicates", label: "Duplicates", icon: Copy },
            { id: "portfolios", label: "Portfolios", icon: Users },
        ]
    }
];

export function ExplorerPane({ activeView, onViewChange, onReset }: ExplorerPaneProps) {
    return (
        <div className="flex flex-col h-full bg-slate-900 border-r border-slate-700 text-slate-300">
            {/* Header */}
            <div className="p-3 border-b border-slate-700 flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Explorer
                </span>
                <button
                    onClick={onReset}
                    className="text-[10px] bg-slate-800 hover:bg-slate-700 text-slate-400 px-2 py-1 rounded transition-colors"
                    title="Start New Audit"
                >
                    NEW
                </button>
            </div>

            {/* File Tree */}
            <div className="flex-1 overflow-y-auto py-2">
                {SECTIONS.map((section, idx) => (
                    <div key={idx} className="mb-4 px-2">
                        <h3 className="mb-1 px-2 text-[10px] font-bold uppercase text-slate-500">
                            {section.title}
                        </h3>
                        <div className="space-y-[1px]">
                            {section.items.map((item) => {
                                const Icon = item.icon || FileText;
                                const isActive = activeView === item.id;

                                return (
                                    <button
                                        key={item.id}
                                        onClick={() => onViewChange(item.id as ViewId)}
                                        className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-sm transition-colors ${isActive
                                            ? "bg-blue-600/20 text-blue-400 hover:bg-blue-600/30"
                                            : "hover:bg-slate-800 text-slate-400 hover:text-slate-200"
                                            }`}
                                    >
                                        <Icon size={14} className={isActive ? "text-blue-400" : "text-slate-500"} />
                                        <span className="truncate">{item.label}</span>
                                    </button>
                                );
                            })}
                        </div>
                    </div>
                ))}
            </div>


        </div>
    );
}
