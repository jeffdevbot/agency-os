/**
 * AdScope type definitions matching backend JSON schema
 */

export interface AuditResponse {
  currency_code: string;
  date_range_mismatch: boolean;
  warnings: string[];
  views: AuditViews;
}

export interface AdTypeMetric {
  ad_type: string;
  active_campaigns: number;
  spend: number;
  sales: number;
  impressions: number;
  clicks: number;
  orders: number;
  acos: number;
  roas: number;
  cpc: number;
  ctr: number;
  cvr: number;
}

export interface AuditViews {
  overview: OverviewView;
  money_pits: MoneyPit[];
  waste_bin: WasteBinItem[];
  brand_analysis: BrandAnalysis;
  match_types: MatchType[];
  placements: Placement[];
  keyword_leaderboard: KeywordLeaderboard;
  budget_cappers: BudgetCapper[];
  campaign_scatter: CampaignScatter[];
  n_grams: NGram[];
  duplicates: Duplicate[];
  portfolios: Portfolio[];
  price_sensitivity: PriceSensitivity[];
  zombies: Zombies;
  ad_types: AdTypeMetric[];
}

export interface OverviewView {
  spend: number;
  sales: number;
  acos: number;
  roas: number;
  impressions: number;
  clicks: number;
  orders: number;
  ad_type_mix: AdTypeMix[];
  targeting_mix: TargetingMix;
}

export interface AdTypeMix {
  type: string;
  spend: number;
  percentage: number;
}

export interface TargetingMix {
  manual_spend: number;
  auto_spend: number;
  manual_percent: number;
}

export interface MoneyPit {
  asin: string;
  product_name: string;
  spend: number;
  sales: number;
  acos: number;
  state: string;
}

export interface WasteBinItem {
  search_term: string;
  spend: number;
  clicks: number;
}

export interface BrandAnalysis {
  branded: BrandMetrics;
  generic: BrandMetrics;
}

export interface BrandMetrics {
  spend: number;
  sales: number;
  acos: number;
}

export interface MatchType {
  type: string;
  spend: number;
  sales: number;
  acos: number;
  cpc: number;
}

export interface Placement {
  placement: string;
  spend: number;
  acos: number;
  cpc: number;
}

export interface KeywordLeaderboard {
  winners: KeywordEntry[];
  losers: KeywordEntry[];
}

export interface KeywordEntry {
  text: string;
  match_type: string;
  campaign: string;
  spend: number;
  sales: number;
  roas: number;
  state: string;
}

export interface BudgetCapper {
  campaign_name: string;
  daily_budget: number;
  avg_daily_spend: number;
  utilization: number;
  roas: number;
  state: string;
}

export interface CampaignScatter {
  id: string;
  name: string;
  spend: number;
  acos: number;
  ad_type: string;
}

export interface NGram {
  gram: string;
  type: "1-gram" | "2-gram";
  spend: number;
  sales: number;
  acos: number;
  count: number;
}

export interface Duplicate {
  keyword: string;
  match_type: string;
  campaign_count: number;
  campaigns: string[];
}

export interface Portfolio {
  name: string;
  spend: number;
  sales: number;
  acos: number;
}

export interface PriceSensitivity {
  asin: string;
  avg_price: number;
  cvr: number;
}

export interface Zombies {
  total_active_ad_groups: number;
  zombie_count: number;
  zombie_list: string[];
}

export type ViewId =
  | "overview"
  | "money_pits"
  | "waste_bin"
  | "brand_analysis"
  | "match_types"
  | "placements"
  | "keyword_leaderboard"
  | "budget_cappers"
  | "campaign_scatter"
  | "n_grams"
  | "duplicates"
  | "portfolios"
  | "price_sensitivity"
  | "zombies";
