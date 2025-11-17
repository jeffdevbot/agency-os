/**
 * Canonical Composer domain types.
 * Mirrors /docs/composer/02_types_canonical.md so all layers import from here.
 */

export type OrganizationId = string;
export type ProjectId = string;
export type SkuVariantId = string;
export type SkuGroupId = string;
export type KeywordPoolId = string;
export type KeywordGroupId = string;
export type TopicId = string;
export type GeneratedContentId = string;
export type BackendKeywordsId = string;
export type LocaleId = string;
export type ClientReviewId = string;
export type CommentId = string;
export type ExportId = string;
export type JobId = string;
export type UsageEventId = string;

export type ISODateString = string;

export type StrategyType = 'variations' | 'distinct';
export type KeywordPoolType = 'body' | 'titles';
export type ContentType =
  | 'title'
  | 'bullets'
  | 'description'
  | 'sample_title'
  | 'sample_bullets'
  | 'sample_description';
export type LocaleMode = 'translate' | 'fresh';
export type ClientReviewStatus =
  | 'draft'
  | 'shared'
  | 'approved'
  | 'changes_requested';
export type AuthorType = 'internal' | 'client';
export type JobStatus = 'pending' | 'running' | 'success' | 'error';
export type JobType =
  | 'bulk_generate'
  | 'locale_generate'
  | 'export_flatfile'
  | 'export_master_csv'
  | 'export_json'
  | 'backend_keywords_generate'
  | 'sample_generate'
  | 'themes_suggest'
  | 'keywords_group'
  | 'keywords_clean';
export type ComposerProjectStatus = 'draft' | 'active' | 'completed' | 'archived';
export type UsageAction =
  | 'keyword_grouping'
  | 'theme_suggestion'
  | 'sample_generate'
  | 'bulk_generate'
  | 'backend_keywords'
  | 'locale_generate'
  | 'keyword_clean'
  | 'ai_lab';

export interface ComposerOrganization {
  id: OrganizationId;
  name: string;
  plan: string | null;
  createdAt: ISODateString;
}

export interface ProductBrief {
  targetAudience?: string;
  useCases?: string;
  differentiators?: string;
  safetyNotes?: string;
  certifications?: string;
}

export interface ComposerProject {
  id: ProjectId;
  organizationId: OrganizationId;
  createdBy: string | null;
  clientName: string;
  projectName: string;
  marketplaces: string[];
  category: string | null;
  strategyType: StrategyType;
  activeStep: string | null;
  status: string;
  brandTone: string | null;
  whatNotToSay: string[] | null;
  suppliedInfo: Record<string, unknown>;
  faq: Array<{ question: string; answer?: string }> | null;
  productBrief: ProductBrief;
  lastSavedAt: ISODateString;
  createdAt: ISODateString;
}

export interface ComposerProjectVersion {
  id: string;
  organizationId: OrganizationId;
  projectId: ProjectId;
  step: string;
  snapshot: Record<string, unknown>;
  createdAt: ISODateString;
}

export interface ComposerSkuGroup {
  id: SkuGroupId;
  organizationId: OrganizationId;
  projectId: ProjectId;
  name: string;
  description: string | null;
  sortOrder: number;
  createdAt: ISODateString;
}

export type ComposerSkuAttributes = Record<string, string | null>;

export interface ComposerSkuVariant {
  id: SkuVariantId;
  organizationId: OrganizationId;
  projectId: ProjectId;
  groupId: SkuGroupId | null;
  sku: string;
  asin: string | null;
  parentSku: string | null;
  attributes: ComposerSkuAttributes;
  notes: string | null;
  createdAt: ISODateString;
}

export interface ComposerSkuSummary {
  id: SkuVariantId;
  sku: string;
  asin: string;
  parentSku: string | null;
  groupId: SkuGroupId | null;
  attributePreview: string;
}

export interface RemovedKeywordEntry {
  term: string;
  reason: string;
}

export interface KeywordCleanSettings {
  removeColors?: boolean;
  removeSizes?: boolean;
  removeBrandTerms?: boolean;
  removeCompetitorTerms?: boolean;
}

export interface GroupingConfig {
  basis?: 'single' | 'per_sku' | 'attribute' | 'custom';
  attributeName?: string;
  groupCount?: number;
  phrasesPerGroup?: number;
}

export interface ComposerKeywordPool {
  id: KeywordPoolId;
  organizationId: OrganizationId;
  projectId: ProjectId;
  groupId: SkuGroupId | null;
  poolType: KeywordPoolType;
  rawKeywords: string[];
  cleanedKeywords: string[];
  removedKeywords: RemovedKeywordEntry[];
  cleanSettings: KeywordCleanSettings;
  groupingConfig: GroupingConfig;
  approvedAt: ISODateString | null;
  createdAt: ISODateString;
}

export interface ComposerKeywordGroup {
  id: KeywordGroupId;
  organizationId: OrganizationId;
  keywordPoolId: KeywordPoolId;
  groupIndex: number;
  label: string | null;
  phrases: string[];
  metadata: Record<string, unknown>;
  createdAt: ISODateString;
}

export interface ComposerTopic {
  id: TopicId;
  organizationId: OrganizationId;
  projectId: ProjectId;
  groupId: SkuGroupId | null;
  title: string;
  explanation: string | null;
  orderIndex: number;
  source: 'ai' | 'manual';
  approvedAt: ISODateString | null;
  createdAt: ISODateString;
}

export interface ContentFlags {
  tooLong?: boolean;
  tooShort?: boolean;
  overBytes?: boolean;
  bannedTerms?: string[];
  missingKeywords?: string[];
  duplicateWithSku?: string | null;
  [key: string]: unknown;
}

export interface ComposerGeneratedContent {
  id: GeneratedContentId;
  organizationId: OrganizationId;
  projectId: ProjectId;
  skuVariantId: SkuVariantId;
  locale: string;
  contentType: ContentType;
  body: string;
  source: 'ai' | 'manual';
  version: number;
  flags: ContentFlags;
  approvedAt: ISODateString | null;
  createdAt: ISODateString;
}

export interface BackendKeywordFlags {
  overLimit?: boolean;
  underUtilized?: boolean;
  bannedTerms?: string[];
  [key: string]: unknown;
}

export interface ComposerBackendKeywords {
  id: BackendKeywordsId;
  organizationId: OrganizationId;
  projectId: ProjectId;
  skuVariantId: SkuVariantId;
  locale: string;
  keywordsString: string | null;
  lengthChars: number | null;
  lengthBytes: number | null;
  flags: BackendKeywordFlags;
  source: 'ai' | 'manual';
  approvedAt: ISODateString | null;
  createdAt: ISODateString;
}

export interface ComposerLocale {
  id: LocaleId;
  organizationId: OrganizationId;
  projectId: ProjectId;
  localeCode: string;
  mode: LocaleMode;
  settings: Record<string, unknown>;
  approvedAt: ISODateString | null;
  createdAt: ISODateString;
}

export interface ComposerClientReview {
  id: ClientReviewId;
  organizationId: OrganizationId;
  projectId: ProjectId;
  token: string;
  enabled: boolean;
  status: ClientReviewStatus;
  approvedAt: ISODateString | null;
  createdAt: ISODateString;
}

export interface ComposerComment {
  id: CommentId;
  organizationId: OrganizationId;
  projectId: ProjectId;
  authorType: AuthorType;
  authorId: string | null;
  authorName: string | null;
  body: string;
  skuVariantId: SkuVariantId | null;
  locale: string | null;
  createdAt: ISODateString;
}

export interface ComposerExport {
  id: ExportId;
  organizationId: OrganizationId;
  projectId: ProjectId;
  format: 'flatfile' | 'master_csv' | 'json' | 'pdf';
  marketplace: string | null;
  triggeredBy: string | null;
  metadata: Record<string, unknown>;
  createdAt: ISODateString;
}

export interface ComposerJob {
  id: JobId;
  organizationId: OrganizationId;
  projectId: ProjectId;
  jobType: JobType;
  status: JobStatus;
  payload: Record<string, unknown>;
  result: Record<string, unknown>;
  errorMessage: string | null;
  createdAt: ISODateString;
  updatedAt: ISODateString;
}

export interface ComposerUsageEvent {
  id: UsageEventId;
  organizationId: OrganizationId;
  projectId: ProjectId | null;
  jobId: JobId | null;
  action: UsageAction;
  model: string;
  tokensIn: number;
  tokensOut: number;
  tokensTotal: number;
  costUsd: number | null;
  durationMs: number | null;
  meta: Record<string, unknown>;
  createdAt: ISODateString;
}
