"use client";

import {
    LayoutDashboard,
    Target,
    DollarSign,
    Megaphone,
    Monitor,
    SlidersHorizontal,
    ChevronRight
} from "lucide-react";
import type { ViewId } from "../types";

interface ExplorerPaneProps {
    activeView: ViewId;
    onViewChange: (viewId: ViewId) => void;
}

const SECTIONS = [
    {
        title: "Dashboard",
        items: [
            { id: "overview", label: "Overview", icon: LayoutDashboard },
            { id: "wasted_spend", label: "Wasted Ad Spend", icon: Target },
        ]
    },
    {
        title: "Sponsored Products",
        items: [
            { id: "targeting_analysis", label: "Targeting Analysis", icon: Target },
            { id: "bidding_placements", label: "Bidding & Placements", icon: DollarSign },
        ]
    },
    {
        title: "Sponsored Brands",
        items: [
            { id: "sponsored_brands_analysis", label: "Match Types & Formats", icon: Megaphone },
            { id: "sponsored_brands_landing_pages", label: "Landing Pages", icon: Megaphone },
        ]
    },
    {
        title: "Sponsored Display",
        items: [
            { id: "sponsored_display_targeting", label: "Match Type & Targeting", icon: Monitor },
            { id: "sponsored_display_bidding_strategies", label: "Bidding Strategies", icon: SlidersHorizontal },
        ]
    },
];

export function ExplorerPane({ activeView, onViewChange }: ExplorerPaneProps) {
    return (
        <div className="flex flex-col h-full bg-white text-slate-600 font-medium text-sm">
            {/* Header */}
            <div className="p-3 border-b border-slate-200 flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    Explorer
                </span>
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
                                        className={`w-full flex items-center gap-2 px-3 py-1.5 pl-7 transition-colors border-l-2 text-left
                                            ${isActive
                                                ? "bg-blue-50 border-[#0077cc] text-[#0077cc]"
                                                : "border-transparent hover:bg-slate-50 hover:text-slate-900"
                                            } `}
                                    >
                                        <Icon className={`w-4 h-4 flex-shrink-0 ${isActive ? "text-[#0077cc]" : "text-slate-400"}`} />
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
