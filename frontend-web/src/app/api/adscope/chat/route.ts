import { NextResponse } from "next/server";
import { createChatCompletion, type ChatMessage, type Tool } from "@/lib/composer/ai/openai";
import { AUDIT_RULES_FOR_LLM } from "@/app/adscope/utils/auditRules";

const SYSTEM_PROMPT = `You are an expert Amazon Advertising auditor—opinionated, direct, and focused on actionable insights.

You have access to a comprehensive audit dataset. The data summary below contains the actual numbers.

**Available Views:**
- overview: Ad type breakdown (SP, SB, SD), conversion funnel, key metrics
- targeting_analysis: SP Auto vs Manual breakdown, Match Types performance
- bidding_placements: Bidding strategies and Placement performance
- sponsored_brands_analysis: SB Match Types and Ad Formats

${AUDIT_RULES_FOR_LLM}

**CRITICAL INSTRUCTIONS:**
1. ALWAYS answer the user's question with specific numbers from the data summary. Never just switch views without answering.
2. If the user asks for a metric (ROAS, ACoS, spend, etc.), calculate or quote it from the data.
3. You MAY also switch views to help them visualize—but ALWAYS provide the answer in your message first.
4. When switching views, tell them which view you're showing and what to look at.
5. Be direct and opinionated. Say "Your SB ROAS is 2.8x—solid but there's room to improve" not just "2.8x".
6. Suggest concrete next steps when relevant.

Example good response: "Your Sponsored Brands ROAS is 2.8x, which is decent but below your SP ROAS of 3.5x. I've opened the SB Analysis view—look at the ad format breakdown to see if Video is dragging down performance."

Keep responses concise (2-4 sentences). You're a veteran consultant who answers questions with data.`;

const VIEW_SWITCHING_TOOL: Tool = {
  type: "function",
  function: {
    name: "switch_view",
    description: "Switch to a specific view in the audit workspace. Use this when the user wants to see a particular analysis view.",
    parameters: {
      type: "object",
      properties: {
        view_id: {
          type: "string",
          enum: [
            "overview",
            "targeting_analysis",
            "bidding_placements",
            "sponsored_brands_analysis",
          ],
          description: "The ID of the view to switch to",
        },
        reason: {
          type: "string",
          description: "Brief explanation of why this view is relevant to the user's question",
        },
      },
      required: ["view_id"],
    },
  },
};

type AuditResponse = {
  currency_code: string;
  views: {
    ad_types: Array<{
      ad_type: string;
      spend: number;
      sales: number;
      impressions: number;
      clicks: number;
      orders: number;
      acos: number;
      ctr: number;
      cvr: number;
    }>;
    sponsored_products: {
      targeting_breakdown: Array<{
        targeting_type: string;
        spend: number;
        sales: number;
        acos: number;
      }>;
      match_types: Array<{
        match_type: string;
        spend: number;
        sales: number;
        acos: number;
      }>;
    };
    bidding_strategies: Array<{
      strategy: string;
      spend: number;
      spend_percent: number;
      acos: number;
    }>;
    placements: Array<{
      placement: string;
      spend: number;
      spend_percent: number;
      acos: number;
    }>;
    sponsored_brands: {
      match_types: Array<{
        match_type: string;
        spend: number;
        sales: number;
        acos: number;
      }>;
      ad_formats: Array<{
        ad_format: string;
        spend: number;
        sales: number;
        acos: number;
      }>;
    };
  };
};

function buildDataSummary(auditData: AuditResponse): string {
  const { views, currency_code } = auditData;

  // Calculate totals from ad_types
  const totalSpend = views.ad_types.reduce((sum, t) => sum + t.spend, 0);
  const totalSales = views.ad_types.reduce((sum, t) => sum + t.sales, 0);
  const totalImpressions = views.ad_types.reduce((sum, t) => sum + t.impressions, 0);
  const totalClicks = views.ad_types.reduce((sum, t) => sum + t.clicks, 0);
  const totalOrders = views.ad_types.reduce((sum, t) => sum + t.orders, 0);
  const overallAcos = totalSales > 0 ? (totalSpend / totalSales) : 0;
  const overallRoas = totalSpend > 0 ? (totalSales / totalSpend) : 0;
  const overallCtr = totalImpressions > 0 ? (totalClicks / totalImpressions) : 0;
  const overallCvr = totalClicks > 0 ? (totalOrders / totalClicks) : 0;

  // Ad type breakdown with ROAS
  const adTypeBreakdown = views.ad_types
    .map(t => {
      const roas = t.spend > 0 ? (t.sales / t.spend).toFixed(2) : "0";
      return `${t.ad_type}: $${t.spend.toFixed(0)} spend, $${t.sales.toFixed(0)} sales, ${(t.acos * 100).toFixed(1)}% ACoS, ${roas}x ROAS`;
    })
    .join("\n  ");

  // SP Targeting breakdown
  const spTargeting = views.sponsored_products?.targeting_breakdown
    ?.map(t => {
      const roas = t.spend > 0 ? (t.sales / t.spend).toFixed(2) : "0";
      return `${t.targeting_type}: $${t.spend.toFixed(0)} spend, ${(t.acos * 100).toFixed(1)}% ACoS, ${roas}x ROAS`;
    })
    .join("; ") || "N/A";

  // Top match types by spend
  const topMatchTypes = views.sponsored_products?.match_types
    ?.slice(0, 5)
    .map(m => {
      const roas = m.spend > 0 ? (m.sales / m.spend).toFixed(2) : "0";
      return `${m.match_type}: $${m.spend.toFixed(0)}, ${(m.acos * 100).toFixed(1)}% ACoS, ${roas}x ROAS`;
    })
    .join("; ") || "N/A";

  // Bidding strategies
  const biddingStrategies = views.bidding_strategies
    ?.map(b => `${b.strategy}: ${b.spend_percent.toFixed(0)}% spend, ${(b.acos * 100).toFixed(1)}% ACoS`)
    .join("; ") || "N/A";

  // Placements
  const placements = views.placements
    ?.map(p => `${p.placement}: ${p.spend_percent.toFixed(0)}% spend, ${(p.acos * 100).toFixed(1)}% ACoS`)
    .join("; ") || "N/A";

  // SB Ad formats with ROAS
  const sbFormats = views.sponsored_brands?.ad_formats
    ?.map(f => {
      const roas = f.spend > 0 ? (f.sales / f.spend).toFixed(2) : "0";
      return `${f.ad_format}: $${f.spend.toFixed(0)} spend, ${(f.acos * 100).toFixed(1)}% ACoS, ${roas}x ROAS`;
    })
    .join("; ") || "N/A";

  return `AUDIT DATA (use these numbers to answer questions):
Currency: ${currency_code}

OVERALL METRICS:
- Total Spend: $${totalSpend.toFixed(2)}
- Total Sales: $${totalSales.toFixed(2)}
- Overall ACoS: ${(overallAcos * 100).toFixed(1)}%
- Overall ROAS: ${overallRoas.toFixed(2)}x
- CTR: ${(overallCtr * 100).toFixed(2)}%
- CVR: ${(overallCvr * 100).toFixed(2)}%

AD TYPES (with individual ROAS):
  ${adTypeBreakdown}

SP TARGETING (Auto vs Manual): ${spTargeting}
SP MATCH TYPES: ${topMatchTypes}

BIDDING STRATEGIES: ${biddingStrategies}
PLACEMENTS: ${placements}

SB AD FORMATS: ${sbFormats}`;
}

import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { logUsage } from "@/lib/ai/usageLogger";

export async function POST(request: Request) {
  try {
    const supabase = await createSupabaseRouteClient();
    const { data: { user } } = await supabase.auth.getUser();

    const body = await request.json().catch(() => null);
    if (!body || !body.userMessage || !body.auditData || !Array.isArray(body.conversationHistory)) {
      return NextResponse.json({ detail: "Invalid request body" }, { status: 400 });
    }

    const userMessage = String(body.userMessage);
    const auditData = body.auditData as AuditResponse;
    const conversationHistory = body.conversationHistory as ChatMessage[];

    const messages: ChatMessage[] = [
      { role: "system", content: SYSTEM_PROMPT },
      { role: "system", content: buildDataSummary(auditData) },
      ...conversationHistory,
      { role: "user", content: userMessage },
    ];

    const result = await createChatCompletion(messages, {
      model: process.env.OPENAI_MODEL_PRIMARY || "gpt-4o-mini",
      temperature: 0.7,
      maxTokens: 500,
      tools: [VIEW_SWITCHING_TOOL],
    });

    let switchToView: string | undefined;
    if (result.toolCalls && result.toolCalls.length > 0) {
      const switchViewCall = result.toolCalls.find((tc) => tc.function.name === "switch_view");
      if (switchViewCall) {
        try {
          const args = JSON.parse(switchViewCall.function.arguments);
          switchToView = args.view_id;
        } catch (e) {
          console.error("Failed to parse tool call arguments:", e);
        }
      }
    }

    // Log usage if user is authenticated
    if (user) {
      await logUsage({
        tool: "adscope",
        userId: user.id,
        projectId: undefined, // AdScope audits are currently ephemeral
        promptTokens: result.tokensIn,
        completionTokens: result.tokensOut,
        totalTokens: result.tokensTotal,
        model: result.model,
        meta: {
          has_audit_data: true,
          switch_to_view: switchToView
        }
      });
    }

    const assistantMessage = result.content || "I've switched to that view for you.";

    return NextResponse.json({
      response: assistantMessage,
      switchToView,
      model: result.model,
      tokensIn: result.tokensIn,
      tokensOut: result.tokensOut,
      tokensTotal: result.tokensTotal,
      durationMs: result.durationMs,
    });
  } catch (error) {
    console.error("AdScope chat API error:", error);
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Chat request failed" },
      { status: 500 },
    );
  }
}
