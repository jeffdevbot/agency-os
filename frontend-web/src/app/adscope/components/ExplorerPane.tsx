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
    FolderOpen,
    ChevronRight
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
            { id: "sponsored_products", label: "Sponsored Products", icon: Target },
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
        <div className="flex flex-col h-full bg-white text-slate-600 font-medium text-sm">
            {/* Header */}
            <div className="p-3 border-b border-slate-200 flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    Explorer
                </span>
                <button
                    onClick={onReset}
                    className="text-[10px] bg-blue-50 hover:bg-blue-100 text-blue-600 font-semibold px-2 py-1 rounded transition-colors"
                    title="Start New Audit"
                >
                    NEW
                </button>
            </div>

            {/* File Tree */}
            <div className="flex-1 overflow-y-auto py-2">
                {SECTIONS.map((section, idx) => (
                    <div key={idx} className="mb-4">
                        <div className="px-3 py-1 flex items-center gap-1 text-slate-400 mb-1">
                            <span className="w-3 h-3 transition-transform">
                                <ChevronRight className="w-3 h-3" />
                            </span>
                            <span className="text-xs font-bold uppercase tracking-wider">{section.title}</span>
                        </div>
                        <div className="space-y-0.5">
                            {section.items.map((item) => {
                                const isActive = activeView === item.id;
                                const Icon = item.icon;
                                return (
                                    <button
                                        key={item.id}
                                        onClick={() => onViewChange(item.id as ViewId)}
                                        className={`w - full flex items - center gap - 2 px - 3 py - 1.5 pl - 7 transition - colors border - l - 2
                                            ${isActive
                                                ? "bg-blue-50 border-[#0077cc] text-[#0077cc]"
                                                : "border-transparent hover:bg-slate-50 hover:text-slate-900"
                                            } `}
                                    >
                                        <Icon className={`w - 4 h - 4 ${isActive ? "text-[#0077cc]" : "text-slate-400"} `} />
                                        <span>{item.label}</span>
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
