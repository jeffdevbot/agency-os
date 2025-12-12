"use client";

import { useState } from "react";
import type { AuditResponse, ViewId } from "../types";
import { AdTypesView } from "./views/AdTypesView";
import { TargetingAnalysisView } from "./views/TargetingAnalysisView";
import { ChatPane } from "./ChatPane";
import { ExplorerPane } from "./ExplorerPane";

interface WorkspaceScreenProps {
  auditData: AuditResponse;
  onReset: () => void;
}

export function WorkspaceScreen({ auditData, onReset }: WorkspaceScreenProps) {
  const [activeView, setActiveView] = useState<ViewId>("overview");

  const renderView = () => {
    const { views, currency_code } = auditData;

    switch (activeView) {
      case "overview":
        return <AdTypesView data={views.ad_types} currency={currency_code} />;
      case "targeting_analysis":
        return <TargetingAnalysisView data={views.sponsored_products} currency={currency_code} />;
      default:
        return <AdTypesView data={views.ad_types} currency={currency_code} />;
    }
  };

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden text-slate-900 font-sans">
      {/* 3-Pane Layout: [Explorer 200px] [Canvas Flex] [Chat 640px] */}

      {/* Pane 1: Explorer (Left) */}
      <div className="w-[200px] flex-shrink-0 border-r border-slate-200 bg-white">
        <ExplorerPane
          activeView={activeView}
          onViewChange={setActiveView}
          onReset={onReset}
        />
      </div>

      {/* Pane 2: Canvas (Center) */}
      <div className="flex-1 flex flex-col min-w-0 bg-slate-50">
        {/* View Content */}
        <div className="flex-1 overflow-auto p-0">
          {renderView()}
        </div>
      </div>

      {/* Pane 3: Chat (Right) */}
      <div className="w-[640px] flex-shrink-0 border-l border-slate-200 bg-white shadow-xl z-10">
        <ChatPane
          auditData={auditData}
          onViewChange={setActiveView}
        />
      </div>
    </div>
  );
}
