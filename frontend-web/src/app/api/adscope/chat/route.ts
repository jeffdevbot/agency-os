import { NextResponse } from "next/server";
import { createChatCompletion, type ChatMessage, type Tool } from "@/lib/composer/ai/openai";

const SYSTEM_PROMPT = `You are an expert Amazon Advertising auditor. You help users navigate and understand their ad audit results.

You have access to a comprehensive audit dataset with the following views:
- overview: Overall performance metrics (spend, sales, ACOS, ROAS, ad type mix, targeting mix, conversion funnel)
- money_pits: Top 20% spenders by ASIN (products consuming most budget)
- waste_bin: Search terms with spend >$50 but zero sales
- brand_analysis: Branded vs generic keyword performance comparison
- match_types: Performance breakdown by match type (exact, phrase, broad)
- placements: Performance by placement (top of search, product pages, rest of search)
- keyword_leaderboard: Top performers (winners) and bottom performers (losers)
- budget_cappers: Campaigns with >90% budget utilization
- campaign_scatter: Campaign-level spend vs ACOS analysis
- n_grams: Most common 1-grams and 2-grams in search terms
- duplicates: Keywords appearing in multiple campaigns
- portfolios: Portfolio-level performance breakdown
- price_sensitivity: ASIN average price vs conversion rate
- zombies: Active ad groups with zero impressions

When users ask questions:
1. Provide concise, actionable insights based on the data
2. Use the switch_view tool if the user wants to see a specific view
3. Reference specific metrics when available
4. Highlight concerning patterns (high ACOS, wasted spend, budget constraints)
5. Suggest optimizations when relevant

Keep responses conversational and helpful. Focus on insights, not just data recitation.`;

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
            "money_pits",
            "waste_bin",
            "brand_analysis",
            "match_types",
            "placements",
            "keyword_leaderboard",
            "budget_cappers",
            "campaign_scatter",
            "n_grams",
            "duplicates",
            "portfolios",
            "price_sensitivity",
            "zombies",
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
    overview: {
      spend: number;
      sales: number;
      acos: number;
      roas: number;
    };
    money_pits: unknown[];
    waste_bin: unknown[];
    budget_cappers: unknown[];
    zombies: { zombie_count: number };
    duplicates: unknown[];
  };
};

function buildDataSummary(auditData: AuditResponse): string {
  const { views, currency_code } = auditData;

  return `Current audit data summary:
- Currency: ${currency_code}
- Total Spend: ${views.overview.spend.toFixed(2)}
- Total Sales: ${views.overview.sales.toFixed(2)}
- ACOS: ${(views.overview.acos * 100).toFixed(1)}%
- ROAS: ${views.overview.roas.toFixed(2)}
- Money Pits: ${views.money_pits.length} ASINs consuming top 20% of budget
- Waste Bin: ${views.waste_bin.length} terms with spend but no sales
- Budget Cappers: ${views.budget_cappers.length} campaigns at >90% budget utilization
- Zombies: ${views.zombies?.zombie_count ?? 0} ad groups with zero impressions
- Duplicates: ${views.duplicates.length} keywords in multiple campaigns`;
}

export async function POST(request: Request) {
  try {
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
