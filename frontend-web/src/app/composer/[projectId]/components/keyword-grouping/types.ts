export interface KeywordGroup {
  id?: string;
  groupIndex: number;
  label: string;
  phrases: string[];
  metadata?: Record<string, unknown>;
}

export interface GroupingConfig {
  basis: 'single' | 'per_sku' | 'attribute' | 'custom';
  attributeName?: string;
  groupCount?: number;
  phrasesPerGroup?: number;
}

export interface GroupingPlan {
  groups: KeywordGroup[];
  config: GroupingConfig;
}

export type PoolStatus = 'empty' | 'uploaded' | 'cleaned' | 'grouped';
