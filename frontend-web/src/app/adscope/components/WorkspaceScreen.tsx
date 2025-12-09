"use client";

import { useState, useCallback } from "react";
import type { AuditResponse, ViewId } from "../types";
import { sendChatMessage } from "../services/chat";
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

interface WorkspaceScreenProps {
  auditData: AuditResponse;
  onReset: () => void;
}

export function WorkspaceScreen({ auditData, onReset }: WorkspaceScreenProps) {
  const [activeView, setActiveView] = useState<ViewId>("overview");
  const [chatMessages, setChatMessages] = useState<Array<{ role: "user" | "assistant"; content: string }>>([
    {
      role: "assistant",
      content: "👋 I'm your Ad Auditor. I can help you navigate your audit results. Try asking:\n• Show me money pits\n• What's in the waste bin?\n• Compare branded vs generic performance\n• Show budget cappers"
    }
  ]);
  const [input, setInput] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);

  const handleViewChange = (viewId: ViewId) => {
    setActiveView(viewId);
  };

  const handleSendMessage = useCallback(async () => {
    if (!input.trim() || isProcessing) return;

    const userMessage = input.trim();
    setInput("");
    setChatMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsProcessing(true);

    try {
      const conversationHistory = chatMessages.map((msg) => ({
        role: msg.role as "user" | "assistant",
        content: msg.content,
      }));

      const result = await sendChatMessage(userMessage, auditData, conversationHistory);

      setChatMessages((prev) => [...prev, { role: "assistant", content: result.response }]);

      if (result.switchToView) {
        setActiveView(result.switchToView);
      }
    } catch (error) {
      console.error("Chat error:", error);
      setChatMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, I encountered an error processing your request. Please try again.",
        },
      ]);
    } finally {
      setIsProcessing(false);
    }
  }, [input, isProcessing, chatMessages, auditData]);

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
      default:
        return <OverviewView data={views.overview} currency={currency_code} warnings={auditData.warnings} dateRangeMismatch={auditData.date_range_mismatch} />;
    }
  };

  return (
    <div className="flex h-screen bg-slate-900">
      {/* Left Panel - AI Chat */}
      <div className="w-96 border-r border-slate-700 flex flex-col bg-slate-900/50">
        {/* Header */}
        <div className="border-b border-slate-700 p-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-200">Ad Auditor</h2>
          <button
            onClick={onReset}
            className="text-xs text-slate-400 hover:text-slate-200 transition-colors"
          >
            New Audit
          </button>
        </div>

        {/* Quick Chips */}
        <div className="border-b border-slate-700 p-3 flex flex-wrap gap-2">
          <button
            onClick={() => handleViewChange("money_pits")}
            className="text-xs px-3 py-1 rounded-full bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors"
          >
            Money Pits
          </button>
          <button
            onClick={() => handleViewChange("waste_bin")}
            className="text-xs px-3 py-1 rounded-full bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors"
          >
            Waste Bin
          </button>
          <button
            onClick={() => handleViewChange("budget_cappers")}
            className="text-xs px-3 py-1 rounded-full bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors"
          >
            Budget Cappers
          </button>
          <button
            onClick={() => handleViewChange("keyword_leaderboard")}
            className="text-xs px-3 py-1 rounded-full bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors"
          >
            Leaderboard
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {chatMessages.map((msg, idx) => (
            <div key={idx} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[80%] rounded-lg px-4 py-2 text-sm ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white"
                    : "bg-slate-800 text-slate-200"
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Input */}
        <div className="border-t border-slate-700 p-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about your audit..."
              className="flex-1 rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !isProcessing) {
                  handleSendMessage();
                }
              }}
            />
            <button
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 transition-colors disabled:bg-slate-700 disabled:cursor-not-allowed"
              disabled={!input.trim() || isProcessing}
              onClick={handleSendMessage}
            >
              {isProcessing ? "..." : "Send"}
            </button>
          </div>
        </div>
      </div>

      {/* Right Panel - Canvas */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar */}
        <div className="border-b border-slate-700 bg-slate-900/50 p-4">
          <div className="flex items-center gap-3 overflow-x-auto">
            {[
              { id: "overview", label: "Overview" },
              { id: "money_pits", label: "Money Pits" },
              { id: "waste_bin", label: "Waste Bin" },
              { id: "brand_analysis", label: "Brand Analysis" },
              { id: "match_types", label: "Match Types" },
              { id: "placements", label: "Placements" },
              { id: "keyword_leaderboard", label: "Leaderboard" },
              { id: "budget_cappers", label: "Budget Cappers" },
              { id: "campaign_scatter", label: "Campaign Scatter" },
              { id: "n_grams", label: "N-Grams" },
              { id: "duplicates", label: "Duplicates" },
              { id: "portfolios", label: "Portfolios" },
              { id: "price_sensitivity", label: "Price Sensitivity" },
              { id: "zombies", label: "Zombies" },
            ].map((view) => (
              <button
                key={view.id}
                onClick={() => handleViewChange(view.id as ViewId)}
                className={`whitespace-nowrap rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                  activeView === view.id
                    ? "bg-slate-700 text-slate-100"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {view.label}
              </button>
            ))}
          </div>
        </div>

        {/* Canvas Content */}
        <div className="flex-1 overflow-auto bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
          {renderView()}
        </div>
      </div>
    </div>
  );
}
