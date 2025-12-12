"use client";

import { useState } from "react";
import type { AuditResponse, ViewId } from "../types";
import { AdTypesView } from "./views/AdTypesView";
import { TargetingAnalysisView } from "./views/TargetingAnalysisView";
import { BiddingPlacementsView } from "./views/BiddingPlacementsView";
import { SponsoredBrandsAnalysisView } from "./views/SponsoredBrandsAnalysisView";
import { WastedAdSpendView } from "./views/WastedAdSpendView";
import { SponsoredBrandsLandingPagesView } from "./views/SponsoredBrandsLandingPagesView";
import { SponsoredDisplayTargetingView } from "./views/SponsoredDisplayTargetingView";
import { BrandVsCategoryView } from "./views/BrandVsCategoryView";
import { ChatPane } from "./ChatPane";
import { ExplorerPane } from "./ExplorerPane";

interface WorkspaceScreenProps {
  auditData: AuditResponse;
  onReset: () => void;
}

export function WorkspaceScreen(props: WorkspaceScreenProps) {
  const { auditData } = props;
  const [activeView, setActiveView] = useState<ViewId>("overview");

  const renderView = () => {
    const { views, currency_code } = auditData;

    switch (activeView) {
      case "overview":
        return <AdTypesView data={views.ad_types} currency={currency_code} />;
      case "wasted_spend":
        return <WastedAdSpendView data={views.wasted_spend} currency={currency_code} />;
      case "brand_vs_category":
        return views.brand_vs_category ? (
          <BrandVsCategoryView data={views.brand_vs_category} currency={currency_code} />
        ) : (
          <AdTypesView data={views.ad_types} currency={currency_code} />
        );
      case "targeting_analysis":
        return <TargetingAnalysisView data={views.sponsored_products} currency={currency_code} />;
      case "bidding_placements":
        return <BiddingPlacementsView biddingStrategies={views.bidding_strategies} placements={views.placements} currency={currency_code} />;
      case "sponsored_brands_analysis":
        return <SponsoredBrandsAnalysisView data={views.sponsored_brands} currency={currency_code} />;
      case "sponsored_brands_landing_pages":
        return <SponsoredBrandsLandingPagesView data={views.sponsored_brands_landing_pages} currency={currency_code} />;
      case "sponsored_display_targeting":
        return <SponsoredDisplayTargetingView data={views.sponsored_display_targeting} currency={currency_code} />;
      default:
        return <AdTypesView data={views.ad_types} currency={currency_code} />;
    }
  };

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden text-slate-900 font-sans">
      {/* 3-Pane Layout: [Explorer 240px] [Canvas Flex] [Chat 640px] */}

      {/* Pane 1: Explorer (Left) */}
      <div className="w-[240px] flex-shrink-0 border-r border-slate-200 bg-white">
        <ExplorerPane
          activeView={activeView}
          onViewChange={setActiveView}
          showBrandVsCategory={Boolean(auditData.views.brand_vs_category)}
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
          activeView={activeView}
        />
      </div>
    </div>
  );
}
