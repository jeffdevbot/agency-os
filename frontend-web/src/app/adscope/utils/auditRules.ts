/**
 * AdScope Audit Rules
 *
 * Single source of truth for Amazon Advertising benchmarks and thresholds.
 * Used by:
 * - Client-side hot takes generator (zero tokens, instant render)
 * - LLM system prompt (consistent chat responses)
 */

import type { AuditResponse, ViewId } from "../types";

// =============================================================================
// BENCHMARKS & THRESHOLDS
// =============================================================================

export const ACOS_THRESHOLDS = {
  EXCELLENT: 0.20,      // <20% = excellent
  VERY_GOOD: 0.25,      // 20-25% = very good
  AVERAGE: 0.30,        // 25-30% = average
  ACCEPTABLE: 0.40,     // 30-40% = acceptable but watch it
  // >40% = needs attention
} as const;

export const AD_TYPE_MIX = {
  // Ideal ratio for mature accounts
  SP_TARGET: 0.50,      // Sponsored Products ~50%
  SB_TARGET: 0.40,      // Sponsored Brands ~40%
  SD_TARGET: 0.10,      // Sponsored Display ~10%
  // If SP > 70%, likely missing brand visibility opportunities
  SP_OVERSPEND_THRESHOLD: 0.70,
} as const;

export const SP_TARGETING_MIX = {
  // New/discovery campaigns: more auto is fine
  NEW_AUTO_ACCEPTABLE: 0.70,    // 70% auto / 30% manual
  // Mature campaigns: should be mostly manual
  MATURE_AUTO_TARGET: 0.20,     // 20% auto / 80% manual
  MATURE_MANUAL_TARGET: 0.80,
} as const;

export const MATCH_TYPE_BENCHMARKS = {
  // Broad should be low % in mature accounts (discovery only)
  BROAD_MAX_HEALTHY: 0.10,      // <10% of spend
  // Exact should have majority of investment in mature accounts
  EXACT_MIN_HEALTHY: 0.40,      // >40% of spend
} as const;

export const WASTED_SPEND_BUCKETS = [
  {
    id: "too_low",
    minInclusive: 0.0,
    maxExclusive: 0.20,
    rangeLabel: "< 20%",
    verdict: "⚠️ Too Low",
    meaning: "Very conservative testing. May slow down keyword discovery and growth.",
  },
  {
    id: "slightly_low",
    minInclusive: 0.20,
    maxExclusive: 0.33,
    rangeLabel: "20–33%",
    verdict: "⚠️ Slightly Low",
    meaning: "A bit conservative — more exploration could uncover new converting targets.",
  },
  {
    id: "healthy",
    minInclusive: 0.33,
    maxExclusive: 0.50,
    rangeLabel: "33–50%",
    verdict: "✅ Healthy",
    meaning: "Good mix of testing and efficiency. Most strong accounts land here.",
  },
  {
    id: "heavy_testing",
    minInclusive: 0.50,
    maxExclusive: 0.60,
    rangeLabel: "50–60%",
    verdict: "✔️ Still Healthy, Heavy Testing",
    meaning: "Aggressive testing. Fine as long as performance stays stable.",
  },
  {
    id: "high",
    minInclusive: 0.60,
    maxExclusive: 0.70,
    rangeLabel: "60–70%",
    verdict: "❌ High Waste",
    meaning: "Large share of spend went to targets that never converted. Optimization needed.",
  },
  {
    id: "severe",
    minInclusive: 0.70,
    maxExclusive: 1.01,
    rangeLabel: "> 70%",
    verdict: "🔥 Severe Waste",
    meaning: "Budget is being burned on non-converting targets. Strong immediate opportunity.",
  },
] as const;

export type WastedSpendBucketId = (typeof WASTED_SPEND_BUCKETS)[number]["id"];

export function getWastedSpendBucket(wastedSpendPct: number) {
  const pct = Number.isFinite(wastedSpendPct) ? wastedSpendPct : 0;
  const clamped = Math.max(0, Math.min(1, pct));
  return (
    WASTED_SPEND_BUCKETS.find(
      (b) => clamped >= b.minInclusive && clamped < b.maxExclusive
    ) || WASTED_SPEND_BUCKETS[0]
  );
}

// =============================================================================
// HOT TAKE TYPES
// =============================================================================

export type HotTakeSeverity = "success" | "warning" | "error" | "info";

export interface HotTake {
  id: string;
  severity: HotTakeSeverity;
  emoji: string;
  headline: string;
  body: string;
  ctaText: string;
  targetView: ViewId;
  kpi?: {
    valueText: string;
    verdictText: string;
  };
}

// =============================================================================
// HOT TAKE GENERATOR
// =============================================================================

export function generateHotTakes(auditData: AuditResponse): HotTake[] {
  const hotTakes: HotTake[] = [];
  const { views } = auditData;

  // Calculate totals
  const totalSpend = views.ad_types.reduce((sum, t) => sum + t.spend, 0);
  const totalSales = views.ad_types.reduce((sum, t) => sum + t.sales, 0);
  const overallAcos = totalSales > 0 ? totalSpend / totalSales : 0;

  // ==========================================================================
  // 1. OVERALL ACOS ASSESSMENT
  // ==========================================================================
  if (overallAcos < ACOS_THRESHOLDS.EXCELLENT) {
    hotTakes.push({
      id: "acos-excellent",
      severity: "success",
      emoji: "🎯",
      headline: "Outstanding ACoS Performance",
      body: `Your blended ACoS of ${(overallAcos * 100).toFixed(1)}% is excellent. You're running a tight ship—focus on scaling what's working.`,
      ctaText: "View Overall Performance",
      targetView: "overview",
      kpi: {
        valueText: `${(overallAcos * 100).toFixed(1)}%`,
        verdictText: "✅ Excellent",
      },
    });
  } else if (overallAcos < ACOS_THRESHOLDS.AVERAGE) {
    hotTakes.push({
      id: "acos-good",
      severity: "success",
      emoji: "✅",
      headline: "ACoS is Solid With Room to Optimize",
      body: `Your blended ACoS of ${(overallAcos * 100).toFixed(1)}% looks reasonable for most categories, but there's still room to trim waste and push it lower.`,
      ctaText: "View Overall Performance",
      targetView: "overview",
      kpi: {
        valueText: `${(overallAcos * 100).toFixed(1)}%`,
        verdictText: "✅ Solid",
      },
    });
  } else if (overallAcos < ACOS_THRESHOLDS.ACCEPTABLE) {
    hotTakes.push({
      id: "acos-watch",
      severity: "warning",
      emoji: "⚠️",
      headline: "ACoS is Creeping Up",
      body: `At ${(overallAcos * 100).toFixed(1)}%, your ACoS is in acceptable territory but many sellers can't be profitable here. Time to audit your keywords and bids.`,
      ctaText: "View Overall Performance",
      targetView: "overview",
      kpi: {
        valueText: `${(overallAcos * 100).toFixed(1)}%`,
        verdictText: "⚠️ Needs Work",
      },
    });
  } else {
    hotTakes.push({
      id: "acos-high",
      severity: "error",
      emoji: "🚨",
      headline: "ACoS Needs Immediate Attention",
      body: `Your blended ACoS of ${(overallAcos * 100).toFixed(1)}% is too high. You're likely bidding on keywords that aren't converting. An N-Gram analysis would help identify waste.`,
      ctaText: "View Overall Performance",
      targetView: "overview",
      kpi: {
        valueText: `${(overallAcos * 100).toFixed(1)}%`,
        verdictText: "🚨 Red Alert",
      },
    });
  }

  // ==========================================================================
  // 2. AD TYPE MIX ASSESSMENT
  // ==========================================================================
  const spType = views.ad_types.find(t => t.ad_type === "Sponsored Products");
  const sbType = views.ad_types.find(t => t.ad_type === "Sponsored Brands");
  const spPercent = spType ? spType.spend / totalSpend : 0;
  const sbPercent = sbType ? sbType.spend / totalSpend : 0;

  if (spPercent > AD_TYPE_MIX.SP_OVERSPEND_THRESHOLD) {
    hotTakes.push({
      id: "sp-heavy",
      severity: "warning",
      emoji: "📊",
      headline: "Heavily Weighted Toward Sponsored Products",
      body: `${(spPercent * 100).toFixed(0)}% of your spend is in SP. You may be missing brand visibility opportunities in Sponsored Brands, which can drive conversions too.`,
      ctaText: "View Ad Type Breakdown",
      targetView: "overview",
      kpi: {
        valueText: `${(spPercent * 100).toFixed(0)}%`,
        verdictText: "⚠️ SP-Heavy",
      },
    });
  }

  if (sbPercent < 0.10 && sbType && sbType.spend > 0) {
    hotTakes.push({
      id: "sb-underutilized",
      severity: "info",
      emoji: "💡",
      headline: "Sponsored Brands Looks Underutilized",
      body: `SB is only ${(sbPercent * 100).toFixed(0)}% of spend. The ideal mix is closer to 40%. SB can be a major driver of brand awareness and conversions.`,
      ctaText: "Review SB Performance",
      targetView: "sponsored_brands_analysis",
      kpi: {
        valueText: `${(sbPercent * 100).toFixed(0)}%`,
        verdictText: "💡 Underutilized",
      },
    });
  }

  // ==========================================================================
  // 3. SP TARGETING MIX (AUTO VS MANUAL)
  // ==========================================================================
  const targeting = views.sponsored_products?.targeting_breakdown || [];
  const autoRow = targeting.find(t => t.targeting_type === "Auto");
  const manualRow = targeting.find(t => t.targeting_type === "Manual");
  const spTotalSpend = targeting.reduce((sum, t) => sum + t.spend, 0);

  if (spTotalSpend > 0 && autoRow && manualRow) {
    const autoPercent = autoRow.spend / spTotalSpend;
    const manualPercent = manualRow.spend / spTotalSpend;

    if (autoPercent > SP_TARGETING_MIX.NEW_AUTO_ACCEPTABLE) {
      hotTakes.push({
        id: "auto-heavy",
        severity: "warning",
        emoji: "🔄",
        headline: "Auto Campaigns Are Dominating",
        body: `${(autoPercent * 100).toFixed(0)}% Auto / ${(manualPercent * 100).toFixed(0)}% Manual. If this is a mature account, you should be closer to 20/80. Too much auto means less control over where your money goes.`,
        ctaText: "Open SP Targeting Analysis",
        targetView: "targeting_analysis",
        kpi: {
          valueText: `${(autoPercent * 100).toFixed(0)}% Auto`,
          verdictText: "⚠️ Too Auto-Heavy",
        },
      });
    } else if (manualPercent > 0.90) {
      hotTakes.push({
        id: "manual-heavy",
        severity: "info",
        emoji: "🧪",
        headline: "Consider More Auto Discovery",
        body: `${(manualPercent * 100).toFixed(0)}% Manual is great for control, but some auto campaigns help discover new converting keywords. Even mature accounts benefit from ~20% auto.`,
        ctaText: "Open SP Targeting Analysis",
        targetView: "targeting_analysis",
        kpi: {
          valueText: `${(manualPercent * 100).toFixed(0)}% Manual`,
          verdictText: "💡 Add Some Auto",
        },
      });
    }
  }

  // ==========================================================================
  // 4. MATCH TYPE DISTRIBUTION
  // ==========================================================================
  const matchTypes = views.sponsored_products?.match_types || [];
  const matchTotalSpend = matchTypes.reduce((sum, m) => sum + m.spend, 0);

  if (matchTotalSpend > 0) {
    const broadRow = matchTypes.find(m => m.match_type === "Broad");
    const exactRow = matchTypes.find(m => m.match_type === "Exact");

    const broadPercent = broadRow ? broadRow.spend / matchTotalSpend : 0;
    const exactPercent = exactRow ? exactRow.spend / matchTotalSpend : 0;

    if (broadPercent > MATCH_TYPE_BENCHMARKS.BROAD_MAX_HEALTHY) {
      const broadAcos = broadRow?.acos ?? 0;
      hotTakes.push({
        id: "broad-heavy",
        severity: broadAcos > ACOS_THRESHOLDS.ACCEPTABLE ? "error" : "warning",
        emoji: "🎯",
        headline: "Broad Match is Eating Your Budget",
        body: `Broad is ${(broadPercent * 100).toFixed(0)}% of SP spend at ${(broadAcos * 100).toFixed(1)}% ACoS. In mature accounts, Broad should be <10%—it's for discovery, not scaling.`,
        ctaText: "Review Match Types",
        targetView: "targeting_analysis",
        kpi: {
          valueText: `${(broadPercent * 100).toFixed(0)}% Broad`,
          verdictText: broadAcos > ACOS_THRESHOLDS.ACCEPTABLE ? "🚨 High Waste" : "⚠️ Too High",
        },
      });
    }

    if (exactPercent < MATCH_TYPE_BENCHMARKS.EXACT_MIN_HEALTHY && exactRow) {
      hotTakes.push({
        id: "exact-underweight",
        severity: "info",
        emoji: "🎯",
        headline: "Exact Match Looks Underweighted",
        body: `Only ${(exactPercent * 100).toFixed(0)}% in Exact. Mature, well-run accounts invest most heavily in Exact—these are your proven converters.`,
        ctaText: "Review Match Types",
        targetView: "targeting_analysis",
        kpi: {
          valueText: `${(exactPercent * 100).toFixed(0)}% Exact`,
          verdictText: "💡 Underweighted",
        },
      });
    }
  }

  // ==========================================================================
  // 5. BIDDING & PLACEMENTS
  // ==========================================================================
  const placements = views.placements || [];
  const topOfSearch = placements.find(p => p.placement.toLowerCase().includes("top of search"));

  if (topOfSearch && topOfSearch.acos > ACOS_THRESHOLDS.ACCEPTABLE) {
    hotTakes.push({
      id: "tos-expensive",
      severity: "warning",
      emoji: "💰",
      headline: "Top of Search is Expensive",
      body: `Top of Search placement is running at ${(topOfSearch.acos * 100).toFixed(1)}% ACoS. The premium position comes at a cost—consider if the visibility is worth it.`,
      ctaText: "Review Placements",
      targetView: "bidding_placements",
      kpi: {
        valueText: `${(topOfSearch.acos * 100).toFixed(1)}% ACoS`,
        verdictText: "⚠️ Expensive",
      },
    });
  }

  // ==========================================================================
  // 6. SB VS SP EFFICIENCY
  // ==========================================================================
  if (sbType && spType && sbType.spend > 0 && spType.spend > 0) {
    if (sbType.acos > spType.acos * 1.5) {
      hotTakes.push({
        id: "sb-inefficient",
        severity: "warning",
        emoji: "📉",
        headline: "Sponsored Brands is Underperforming",
        body: `SB ACoS (${(sbType.acos * 100).toFixed(1)}%) is significantly higher than SP (${(spType.acos * 100).toFixed(1)}%). Your SB campaigns may need tighter keyword targeting or creative refresh.`,
        ctaText: "Open SB Analysis",
        targetView: "sponsored_brands_analysis",
        kpi: {
          valueText: `${(sbType.acos * 100).toFixed(1)}% SB ACoS`,
          verdictText: "⚠️ Underperforming",
        },
      });
    }
  }

  return hotTakes;
}

// =============================================================================
// RULES AS TEXT (for LLM system prompt)
// =============================================================================

export const AUDIT_RULES_FOR_LLM = `
## Amazon Advertising Benchmarks & Rules

You are an opinionated Amazon Advertising veteran. Use these benchmarks when analyzing accounts:

### Overall ACoS Thresholds
- <20% = Excellent. Rare and impressive.
- 20-25% = Very good. Well-optimized account.
- 25-30% = Average. Room for improvement.
- 30-40% = Acceptable but watch it. Many sellers can't be profitable here.
- >40% = Needs attention. Likely bidding on non-converting keywords.

### Ad Type Mix (Ideal for Mature Accounts)
- Sponsored Products: ~50% of spend
- Sponsored Brands: ~40% of spend (many underutilize this)
- Sponsored Display: ~10% of spend
- If SP is >70% of spend, the account is missing brand visibility opportunities.

### SP Targeting Mix (Auto vs Manual)
- New/Discovery phase: 70% Auto / 30% Manual is acceptable
- Mature accounts: Should be 20% Auto / 80% Manual
- If Auto >70% in a mature account, they have poor control over spend
- Some Auto is always good for keyword discovery, even in mature accounts

### Match Type Distribution
- Broad: Should be <10% of spend. It's for discovery, not scaling.
- Phrase: Good for discovery, moderate investment
- Exact: Should have majority of investment (>40%). These are proven converters.
- ASIN/Category/Product Targeting: Often has higher spend and lower ACoS

### Key Principles
1. High ACoS usually means bidding on keywords that don't convert
2. A mature account has harvested keywords from Auto into Manual campaigns
3. Exact match keywords are where profitable accounts invest most
4. Sponsored Brands drives brand awareness AND conversions—don't neglect it
5. Top of Search placements are premium but expensive—verify ROI

### Wasted Spend % (SP-only)
Wasted Spend % = (SP spend with 0 orders) / (total SP spend).

| Wasted Spend % | Verdict                         | Meaning                                                             |
| -------------- | ------------------------------- | ------------------------------------------------------------------- |
| < 20%          | ⚠️ Too Low                      | Very conservative, poor exploration. Stuck-growth pattern.          |
| 20–33%         | ⚠️ Slightly Low                 | Under-testing. Could grow faster with broader discovery.            |
| 33–50%         | ✅ Healthy                       | Balanced testing & efficient spend. Most strong accounts land here. |
| 50–60%         | ✔️ Still Healthy, Heavy Testing | Aggressive experimentation, usually fine unless sales soft.         |
| 60–70%         | ❌ High Waste                    | Inefficient targets or relevance issues; optimization needed.       |
| > 70%          | 🔥 Severe Waste                 | Budget is being burned; immediate action required.                  |

Be direct and opinionated. Say "this needs attention" not "you might want to consider".
`;
