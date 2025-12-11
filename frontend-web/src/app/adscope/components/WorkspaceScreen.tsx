"use client";

import { useState } from "react";
import type { AuditResponse, ViewId } from "../types";
import { OverviewView } from "./views/OverviewView";
import { MoneyPitsView } from "./views/MoneyPitsView";
import { WasteBinView } from "./views/WasteBinView";
import { BrandAnalysisView } from "./views/BrandAnalysisView";
import { MatchTypesView } from "./views/MatchTypesView";
import { PlacementsView } from "./views/PlacementsView";
import { KeywordLeaderboardView } from "./views/KeywordLeaderboardView";
import { BudgetCappersView } from "./views/BudgetCappersView";
import { CampaignScatterView } from "./views/CampaignScatterView";
import { NGramsView } from "./views/NGramsView";
import { DuplicatesView } from "./views/DuplicatesView";
import { PortfoliosView } from "./views/PortfoliosView";
import { PriceSensitivityView } from "./views/PriceSensitivityView";
import { ZombiesView } from "./views/ZombiesView";
import { AdTypesView } from "./views/AdTypesView";
import { SponsoredProductsView } from "./views/SponsoredProductsView";
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
        return <OverviewView data={views.overview} currency={currency_code} warnings={auditData.warnings} dateRangeMismatch={auditData.date_range_mismatch} />;
      case "money_pits":
        return <MoneyPitsView data={views.money_pits} currency={currency_code} />;
      case "waste_bin":
        return <WasteBinView data={views.waste_bin} currency={currency_code} />;
      case "brand_analysis":
        return <BrandAnalysisView data={views.brand_analysis} currency={currency_code} />;
      case "match_types":
        return <MatchTypesView data={views.match_types} currency={currency_code} />;
      case "placements":
        return <PlacementsView data={views.placements} currency={currency_code} />;
      case "keyword_leaderboard":
        return <KeywordLeaderboardView data={views.keyword_leaderboard} currency={currency_code} />;
      case "budget_cappers":
        return <BudgetCappersView data={views.budget_cappers} currency={currency_code} />;
      case "campaign_scatter":
        return <CampaignScatterView data={views.campaign_scatter} currency={currency_code} />;
      case "n_grams":
        return <NGramsView data={views.n_grams} currency={currency_code} />;
      case "duplicates":
        return <DuplicatesView data={views.duplicates} />;
      case "portfolios":
        return <PortfoliosView data={views.portfolios} currency={currency_code} />;
      case "price_sensitivity":
        return <PriceSensitivityView data={views.price_sensitivity} currency={currency_code} />;
      case "zombies":
        return <ZombiesView data={views.zombies} />;
      case "ad_types":
        return <AdTypesView data={views.ad_types} currency={currency_code} />;
      case "sponsored_products":
        return <SponsoredProductsView data={views.sponsored_products} currency={currency_code} />;
      default:
        return <OverviewView data={views.overview} currency={currency_code} warnings={auditData.warnings} dateRangeMismatch={auditData.date_range_mismatch} />;
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
