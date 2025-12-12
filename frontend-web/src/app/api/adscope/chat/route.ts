import { NextResponse } from "next/server";
import { createChatCompletion, type ChatMessage, type Tool } from "@/lib/composer/ai/openai";
import { AUDIT_RULES_FOR_LLM } from "@/app/adscope/utils/auditRules";

const SYSTEM_PROMPT = `You are an expert Amazon Advertising auditor—opinionated, direct, and focused on actionable insights.

You have access to a comprehensive audit dataset with the following views:

**Dashboard**
- overview: Overall performance by ad type (SP, SB, SD) with spend breakdown, conversion funnel (impressions→clicks→orders), and key metrics (ACoS, ROAS, CTR, CVR)

**Sponsored Products**
- targeting_analysis: Auto vs Manual targeting breakdown, plus Match Types performance (Broad, Phrase, Exact, and auto types like Close-Match, Loose-Match, Substitutes, Complements, ASIN, Category)
- bidding_placements: Bidding strategy breakdown (Dynamic Down, Dynamic Up/Down, Fixed) and Placement performance (Top of Search, Product Pages, Rest of Search)

**Sponsored Brands**
- sponsored_brands_analysis: SB Match Types and Ad Formats (Video, Product Collection, Store Spotlight, Brand Video) performance

${AUDIT_RULES_FOR_LLM}

When users ask questions:
1. Be direct and opinionated—say "this needs attention" not "you might want to consider"
2. Use the switch_view tool if the user wants to see a specific view
3. Reference specific metrics and compare them to the benchmarks above
4. Explain WHY something is good or bad based on the rules
5. Suggest concrete next steps, not vague advice

Keep responses concise (2-4 sentences unless detail is needed). You're a veteran consultant, not a data reader.`;

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
        acos: number;
      }>;
      ad_formats: Array<{
        ad_format: string;
        spend: number;
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
  const overallAcos = totalSales > 0 ? (totalSpend / totalSales) * 100 : 0;

  // Ad type breakdown
  const adTypeBreakdown = views.ad_types
    .map(t => `${t.ad_type}: ${((t.spend / totalSpend) * 100).toFixed(0)}% spend, ${(t.acos * 100).toFixed(1)}% ACoS`)
    .join("; ");

  // SP Targeting breakdown
  const spTargeting = views.sponsored_products?.targeting_breakdown
    ?.map(t => `${t.targeting_type}: $${t.spend.toFixed(0)}, ${(t.acos * 100).toFixed(1)}% ACoS`)
    .join("; ") || "N/A";

  // Top match types by spend
  const topMatchTypes = views.sponsored_products?.match_types
    ?.slice(0, 5)
    .map(m => `${m.match_type}: $${m.spend.toFixed(0)}, ${(m.acos * 100).toFixed(1)}% ACoS`)
    .join("; ") || "N/A";

  // Bidding strategies
  const biddingStrategies = views.bidding_strategies
    ?.map(b => `${b.strategy}: ${b.spend_percent.toFixed(0)}% spend, ${(b.acos * 100).toFixed(1)}% ACoS`)
    .join("; ") || "N/A";

  // Placements
  const placements = views.placements
    ?.map(p => `${p.placement}: ${p.spend_percent.toFixed(0)}% spend, ${(p.acos * 100).toFixed(1)}% ACoS`)
    .join("; ") || "N/A";

  // SB Ad formats
  const sbFormats = views.sponsored_brands?.ad_formats
    ?.map(f => `${f.ad_format}: $${f.spend.toFixed(0)}, ${(f.acos * 100).toFixed(1)}% ACoS`)
    .join("; ") || "N/A";

  return `Current audit data summary:
- Currency: ${currency_code}
- Total Spend: $${totalSpend.toFixed(2)}
- Total Sales: $${totalSales.toFixed(2)}
- Overall ACoS: ${overallAcos.toFixed(1)}%

Ad Types: ${adTypeBreakdown}

SP Targeting (Auto vs Manual): ${spTargeting}
SP Match Types: ${topMatchTypes}

Bidding Strategies: ${biddingStrategies}
Placements: ${placements}

SB Ad Formats: ${sbFormats}`;
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
