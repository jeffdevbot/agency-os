# 02 — Canonical Types & Domain Model (TypeScript)

## Scope

This micro-spec defines the **canonical TypeScript domain types** for Composer.

These types are the **single source of truth** for:

- Frontend state (React/Next.js)
- Backend DTOs (API handlers, services)
- AI orchestrator input/output contracts
- Supabase row mappers where needed

**In scope:**

- Core Composer entity types (projects, SKUs, groups, keywords, content, locales, review, jobs, usage)
- Shared enums / string unions
- ID and timestamp aliases
- Rules for how these types are used across the codebase

**Out of scope:**

- API route signatures
- React component props
- Zod/Valibot runtime validators (they should mirror these types, but are defined elsewhere)

Implementation lives in:

- `/lib/composer/types.ts` (primary)
- Optional `zod` schemas in `/lib/composer/validation/*` for runtime checks.

---

## Types-First Rules

1. **Do not redefine domain shapes** in components, hooks, or API handlers. Always import from `/lib/composer/types`.
2. Supabase row types should be **adapted to these domain types**, not vice versa (e.g., `DbComposerProject` → `ComposerProject`).
3. DTOs for API requests/responses should reuse domain types directly or extend/pick/omit from them—never ad-hoc shapes.
4. All AI orchestration functions must use these types as inputs and outputs (especially `ComposerGeneratedContent`, `ComposerBackendKeywords`, `ComposerUsageEvent`).

### Import Convention

- Frontend packages (e.g., `frontend-web`) must import canonical composer types via the shared alias `@agency/lib/composer/*` defined in `tsconfig.json`.
- Avoid relative paths like `../../../../lib/composer/types`; they are brittle and will break as files move deeper in the tree.
- If a new package needs these types, add/extend the alias rather than introducing a new copy of the domain model.

---

## Base Aliases

```ts
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

export type ISODateString = string; // e.g. 2025-11-17T10:00:00.000Z
```

---

## Shared Enums / String Unions

These must stay aligned with DB check constraints:

```ts
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

export type ComposerProjectStatus =
  | 'draft'
  | 'active'
  | 'completed'
  | 'archived';

export type UsageAction =
  | 'keyword_grouping'
  | 'theme_suggestion'
  | 'sample_generate'
  | 'bulk_generate'
  | 'backend_keywords'
  | 'locale_generate'
  | 'keyword_clean'
  | 'ai_lab';
```

If DB check constraints are tightened later, update these unions in sync.

---

## 1. Organizations & Projects

### ComposerOrganization

```ts
export interface ComposerOrganization {
  id: OrganizationId;
  name: string;
  plan: string | null;
  createdAt: ISODateString;
}
```

### ProductBrief

```ts
export interface ProductBrief {
  targetAudience?: string;
  useCases?: string;
  differentiators?: string;
  safetyNotes?: string;
  certifications?: string;
}
```

### ComposerProject

```ts
export type HighlightSurface = 'title' | 'bullets' | 'description' | 'backend_keywords';

export interface HighlightAttributePreference {
  key: string;
  surfaces: Record<HighlightSurface, boolean>;
}

export interface ComposerProject {
  id: ProjectId;
  organizationId: OrganizationId;
  createdBy: string | null;
  clientName: string | null;
  projectName: string;
  marketplaces: string[];
  category: string | null;
  strategyType: StrategyType | null;
  activeStep: string | null;
  status: string | null;
  brandTone: string | null;
  whatNotToSay: string[] | null;
  suppliedInfo: Record<string, unknown>;
  faq: Array<{ question: string; answer?: string }> | null;
  productBrief: ProductBrief;
  highlightAttributes: HighlightAttributePreference[];
  lastSavedAt: ISODateString | null;
  createdAt: ISODateString;
}
```

### ComposerProjectVersion

```ts
export interface ComposerProjectVersion {
  id: string;
  organizationId: OrganizationId;
  projectId: ProjectId;
  step: string;
  snapshot: Record<string, unknown>;
  createdAt: ISODateString;
}
```

---

## 2. SKUs & Groups

### ComposerSkuGroup

```ts
export interface ComposerSkuGroup {
  id: SkuGroupId;
  organizationId: OrganizationId;
  projectId: ProjectId;
  name: string;
  description: string | null;
  sortOrder: number;
  createdAt: ISODateString;
}
```

### ComposerSkuAttributes

```ts
export type ComposerSkuAttributes = Record<string, string | null>;
```

### ComposerSkuVariant

```ts
export interface ComposerSkuVariant {
  id: SkuVariantId;
  organizationId: OrganizationId;
  projectId: ProjectId;
  groupId: SkuGroupId | null;
  sku: string;
  asin: string;
  parentSku: string | null;
  attributes: ComposerSkuAttributes;
  notes: string | null;
  createdAt: ISODateString;
}
```

### Derived Helper Types (read models)

```ts
export interface ComposerSkuSummary {
  id: SkuVariantId;
  sku: string;
  asin: string;
  parentSku: string | null;
  groupId: SkuGroupId | null;
  attributePreview: string;
}
```

---

## 3. Keyword Pools & Groups

### RemovedKeywordEntry

```ts
export interface RemovedKeywordEntry {
  term: string;
  reason: string;
}
```

### KeywordPoolStatus

```ts
export type KeywordPoolStatus = 'empty' | 'uploaded' | 'cleaned' | 'grouped';
```

### KeywordCleanSettings

```ts
export interface KeywordCleanSettings {
  removeColors?: boolean;
  removeSizes?: boolean;
  removeBrandTerms?: boolean;
  removeCompetitorTerms?: boolean;
}
```

### GroupingConfig

```ts
export interface GroupingConfig {
  basis?: 'single' | 'per_sku' | 'attribute' | 'custom';
  attributeName?: string;
  groupCount?: number;
  phrasesPerGroup?: number;
}
```

### ComposerKeywordPool

```ts
export interface ComposerKeywordPool {
  id: KeywordPoolId;
  organizationId: OrganizationId;
  projectId: ProjectId;
  groupId: SkuGroupId | null;
  poolType: KeywordPoolType;
  status: KeywordPoolStatus;
  rawKeywords: string[];
  rawKeywordsUrl?: string | null;
  cleanedKeywords: string[];
  removedKeywords: RemovedKeywordEntry[];
  cleanSettings: KeywordCleanSettings;
  groupingConfig: GroupingConfig;
  cleanedAt: ISODateString | null;
  groupedAt: ISODateString | null;
  approvedAt: ISODateString | null;
  createdAt: ISODateString;
}
```

### ComposerKeywordGroup

```ts
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
```

### ComposerKeywordGroupOverride

```ts
export type KeywordGroupOverrideAction = 'move' | 'remove' | 'add';

export interface ComposerKeywordGroupOverride {
  id: string;
  organizationId: OrganizationId;
  keywordPoolId: KeywordPoolId;
  sourceGroupId: KeywordGroupId | null;
  phrase: string;
  action: KeywordGroupOverrideAction;
  targetGroupLabel: string | null;
  targetGroupIndex: number | null;
  createdAt: ISODateString;
}
```

---

## 4. Themes, Samples & Bulk Content

### ComposerTopic

```ts
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
```

### ContentFlags

```ts
export interface ContentFlags {
  tooLong?: boolean;
  tooShort?: boolean;
  overBytes?: boolean;
  bannedTerms?: string[];
  missingKeywords?: string[];
  duplicateWithSku?: string | null;
  [key: string]: unknown;
}
```

### ComposerGeneratedContent

```ts
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
```

Rule: one row per `(organizationId, projectId, skuVariantId, locale, contentType)`.

---

## 5. Backend Keywords

### BackendKeywordFlags

```ts
export interface BackendKeywordFlags {
  overLimit?: boolean;
  underUtilized?: boolean;
  bannedTerms?: string[];
  [key: string]: unknown;
}
```

### ComposerBackendKeywords

```ts
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
```

---

## 6. Localization

### ComposerLocale

```ts
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
```

Localized titles/bullets/descriptions/backend strings live in `ComposerGeneratedContent` and `ComposerBackendKeywords` with `locale` set accordingly.

---

## 7. Client Review & Comments

### ComposerClientReview

```ts
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
```

### ComposerComment

```ts
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

---

## 8. Exports & Jobs

### ComposerExport

```ts
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
```

### ComposerJob

```ts
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
```

---

## 9. LLM Usage Tracking

### ComposerUsageEvent

```ts
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
```

Rule: The central LLM wrapper populates `tokensIn`, `tokensOut`, `tokensTotal`, estimates `costUsd` (optional), attaches `projectId`/`jobId`, and records relevant metadata (locale, skuCount, poolType, etc.).

---

## Acceptance Criteria

- `/lib/composer/types.ts` defines and exports the types above (or equivalent).
- React components, hooks, and API handlers import these types instead of redefining shapes.
- Supabase row types are adapted to these domain types via a single mapping layer (if needed).
- AI orchestration modules use these types as input/output contracts.
- Whenever the DB schema changes, this file and `01_schema_tenancy.md` are updated together.
