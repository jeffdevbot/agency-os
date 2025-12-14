"use client";

import { useState } from "react";
import { Menu, X } from "lucide-react";
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
  const [explorerOpen, setExplorerOpen] = useState(false);

  const activeViewLabel = activeView
    .replaceAll("_", " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());

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
    <div className="flex h-screen bg-slate-50 overflow-hidden text-slate-900 font-sans flex-col lg:flex-row">
      {/* Desktop Explorer (left) */}
      <div className="hidden xl:block w-[240px] flex-shrink-0 border-r border-slate-200 bg-white">
        <ExplorerPane
          activeView={activeView}
          onViewChange={setActiveView}
          showBrandVsCategory={Boolean(auditData.views.brand_vs_category)}
        />
      </div>

      {/* Laptop Explorer rail (icons only) */}
      <div className="hidden lg:block xl:hidden w-[72px] flex-shrink-0 border-r border-slate-200 bg-white">
        <ExplorerPane
          activeView={activeView}
          onViewChange={setActiveView}
          showBrandVsCategory={Boolean(auditData.views.brand_vs_category)}
          variant="rail"
        />
      </div>

      {/* Mobile top bar (Explorer hamburger) */}
      <div className="lg:hidden flex items-center justify-between px-4 py-3 bg-white border-b border-slate-200">
        <button
          onClick={() => setExplorerOpen(true)}
          className="inline-flex items-center justify-center rounded-md border border-slate-200 bg-white px-3 py-2 text-slate-700 hover:bg-slate-50"
          aria-label="Open Explorer"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div className="text-sm font-semibold text-slate-700 truncate max-w-[70%]">
          {activeViewLabel}
        </div>
      </div>

      {/* Pane 2: Canvas (Center) */}
      <div className="flex-1 flex flex-col min-w-0 bg-slate-50">
        <div className="flex-1 overflow-auto p-0">{renderView()}</div>
      </div>

      {/* Pane 3: Chat (right on desktop, bottom on mobile) */}
      <div className="w-full lg:w-[420px] xl:w-[520px] 2xl:w-[600px] flex-shrink-0 border-t lg:border-t-0 lg:border-l border-slate-200 bg-white shadow-xl z-10 h-[42vh] md:h-[45vh] lg:h-full">
        <ChatPane
          auditData={auditData}
          onViewChange={setActiveView}
          activeView={activeView}
        />
      </div>

      {/* Mobile Explorer drawer */}
      {explorerOpen && (
        <div className="lg:hidden fixed inset-0 z-50">
          <div
            className="absolute inset-0 bg-black/30"
            onClick={() => setExplorerOpen(false)}
          />
          <div className="absolute left-0 top-0 bottom-0 w-[280px] bg-white border-r border-slate-200 shadow-2xl">
            <div className="flex items-center justify-between px-3 py-3 border-b border-slate-200">
              <div className="text-xs font-bold uppercase tracking-wider text-slate-400">Explorer</div>
              <button
                onClick={() => setExplorerOpen(false)}
                className="inline-flex items-center justify-center rounded-md border border-slate-200 bg-white px-2 py-2 text-slate-700 hover:bg-slate-50"
                aria-label="Close Explorer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <ExplorerPane
              activeView={activeView}
              onViewChange={(viewId) => {
                setActiveView(viewId);
                setExplorerOpen(false);
              }}
              showBrandVsCategory={Boolean(auditData.views.brand_vs_category)}
            />
          </div>
        </div>
      )}
    </div>
  );
}
