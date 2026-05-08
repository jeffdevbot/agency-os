# MercatoPath Brief

**Status:** Draft — exploratory planning, pre-build
**Working name:** MercatoPath
**Domain:** MercatoPath.com
**Author:** Jeff
**Last updated:** 2026-05-07

---

## 1. Premise

Today's agency-os codebase is purpose-built for one Amazon agency (Ecomlabs). It pulls business, ads, search-term, and (partial) returns data, ingests P&L from CSV, drafts WBR and monthly P&L emails, and exposes everything to Claude via the Ecomlabs Tools MCP. It works, but it's locked to a single-tenant agency model with deprecated paths, plaintext token storage, admin-only RLS, ClickUp integration for task management (SOPs themselves live in ClickUp as docs, not yet first-party in agency-os), and an LWA app stuck in draft mode.

The opportunity: take what's been validated as useful inside the agency and rebuild it as a multi-tenant SaaS for sellers and other agencies. The differentiator is **not** "another Amazon dashboard." It's **opinionated execution + a strategic LLM partner** — the data sync is table stakes, the playbooks and the MCP are the moat.

Strategic direction: **MercatoPath absorbs the durable core of agency-os.** Ecomlabs becomes the first customer of MercatoPath: one organization with workspaces for each client. agency-os should shrink to a small private Ecomlabs extension layer for truly internal operations, not remain a parallel Amazon-data platform.

---

## 2. Target Users

### Primary persona: Mid-market Amazon sellers ($1M–$10M GMV)

This is the sweet spot. Below $1M, willingness to pay is fragile and customers churn fast. Above $20M, in-house teams roll their own or buy enterprise BI. Between $1M and $10M, sellers are sophisticated enough to value structured ops but too small to staff a full analytics + ops bench in-house.

**Seller bucket sizing:**

| GMV band | Profile | Fit |
|---|---|---|
| $200k–$500k | Solo / DIY | Cold — too price-sensitive, will use Helium 10 or cobble Sheets together |
| $500k–$1M | Hiring first VA | Warm — entry-tier candidate if priced low |
| **$1M–$5M** | **Owner-operated, 1–2 ops people** | **Hot — core target** |
| **$5M–$10M** | **Small team, considering or using an agency** | **Hot — biggest LTV potential** |
| $10M–$20M | Real ops team, may already have agency | Warm — buyer is the ops lead, not the founder |
| $20M–$50M | Brand operation, in-house team | Cold direct; warm via agency channel |
| $50M+ | Enterprise, custom needs | Out of scope v1 |

**Multi-country:** sellers in the $1M–$10M band are predominantly North America–only. Multi-marketplace becomes table stakes by $5M+ and is universal in the agency channel. The platform supports NA / EU / FE from day one (the current code already does), but the v1 onboarding flow and pricing should not assume multi-country.

### Secondary persona: Amazon agencies

Agencies are a high-leverage channel — one agency customer = 10–50 underlying seller workspaces. They have different requirements:

- **Workspace-per-client isolation.** Strict RLS, separate connections, separate billing visibility.
- **Multi-country by default.** Almost every agency book has at least one EU client.
- **White-label appetite.** Want their logo on the in-app inbox and outbound alerts. (v2, not v1.)
- **Bulk operations.** "Run this SOP across all 12 of my clients launching for Prime Day" is a real ask.

Agency size band: 5–50 clients is the realistic v1 fit. Sub-5 doesn't justify the workspace overhead. 50+ wants custom integrations.

### Buyer vs. user

- **Sellers:** buyer = founder / owner-operator. User = same person + maybe one VA.
- **Agencies:** buyer = agency owner or COO. Users = account leads + execution VAs. The buyer cares about margin and team productivity; the users care about not having to leave the tool.

### V1 Amazon account scope

MercatoPath v1 supports **Seller Central / third-party seller accounts only**. Vendor Central / 1P vendor workflows are out of scope for launch even if Amazon's umbrella terminology says "selling partner." This keeps sync, P&L, inventory, and playbook assumptions cleaner. Vendor support can be revisited later as a separate product expansion, not silently blended into the seller model.

---

## 3. The Five Pillars

Originally six in conversation; "dashboards" got demoted to utilitarian-only since the LLM-via-MCP experience is the actual differentiator.

### Pillar 1 — Sync (the data backbone)

Multi-marketplace, multi-tenant Amazon data pipeline. Larger surface than the current agency-os ingestion:

- Sales & Traffic by ASIN — exists in agency-os (reference shape)
- Ads campaign performance + search-term reports — exists
- **Returns** — partially exists (`WindsorReturnsSyncService` is implemented and wired into the Windsor business sync, but ingestion is from Windsor, not direct SP-API; needs to be migrated to SP-API Returns Reports for the new product)
- **Financial events / transactions** — SP-API helpers exist (`list_financial_event_groups`, `list_transactions`) but are not wired into a worker; this is the unlock for API-driven P&L without CSV upload
- **Inventory health** including FBA storage age buckets — not in current code; needed for LTSF alerts
- **Placement reports** (Amazon Ads) — not in current code
- Brand Analytics search query performance — separate auth, lower priority

Goal: a single seller workspace can be fully bootstrapped from OAuth — no CSV uploads, no Sheets gymnastics.

#### SP-API data surfaces and lookback

SP-API is not one monolithic data source. The docs page at `developer-docs.amazon.com/sp-api/docs/sp-api-models` is the model/API-family index. For MercatoPath v1, the important seller-only surfaces are:

- **Reports API (`/reports/2021-06-30`)** — current agency-os uses this via `SpApiReportsClient` to call `createReport`, poll `getReport`, download `getReportDocument`, and ingest report documents. Business sync uses `GET_SALES_AND_TRAFFIC_REPORT` with `dateGranularity` and `asinGranularity` options. Amazon's docs state this report's `dataStartTime` must not be more than two years before the request date. This is the likely source for 2-year Sales & Traffic backfill.
- **Data Kiosk API (`2023-11-15`)** — GraphQL-style seller sales and traffic data. Amazon positions it as schema-first and says it has the Reports API's functionality and more. It may be a cleaner future replacement for Sales & Traffic ingestion, but agency-os does not use it today.
- **Sellers API** — marketplace participation / account validation. Current auth validation already uses `getMarketplaceParticipations`.
- **Listings / Inventory reports** — current listing import uses Reports API report types such as `GET_MERCHANT_LISTINGS_ALL_DATA`; v1 inventory health needs a deliberate report/API selection.
- **Returns reports** — use SP-API Reports return report types such as `GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE`; current agency-os returns ingestion is Windsor-derived and must move.
- **Finances API (`2024-06-19`)** — current helpers exist for financial event groups / transactions, but there is no worker yet. This is separate from Reports API settlement reports and is the likely path for API-driven P&L.

Do not conflate SP-API retention with Amazon Ads retention. Sales & Traffic can likely backfill up to two years via SP-API Reports, while Sponsored Ads report lookback is much shorter by report type unless a newer Ads data surface is verified.

#### Target Amazon API portfolio

The customer experience should hide this complexity. Users authorize **Seller Central** and **Amazon Ads**; MercatoPath decides which underlying Amazon APIs and reports to call, schedules the right sync jobs, and exposes simple readiness states.

Target surfaces for v1 / v1.x:

| Surface | Priority | Use | Notes |
|---|---:|---|---|
| **SP-API Reports API** | P0 | Sales & Traffic, listings, FBA inventory/fee reports, returns reports | Current agency-os already uses Reports API for `GET_SALES_AND_TRAFFIC_REPORT` and listings. Keep as the reliable baseline. |
| **Data Kiosk API** | P0 | Sales & Traffic replacement for new ingestion | GraphQL-style Seller Sales and Traffic data. Amazon says Data Kiosk has the Reports API's functionality and more, and that Reports API reports will be deprecated after they are onboarded to Data Kiosk. Since the live probe worked, prioritize Data Kiosk for MercatoPath's new Sales & Traffic ingestion and keep Reports API as a fallback / compatibility path. |
| **Sellers API** | P0 | Account validation, marketplace participation discovery | Current SP-API validation uses this. Needed immediately after OAuth. |
| **Finances API (`2024-06-19`)** | P0 | API-driven P&L, transaction ledger, settlement/payment mapping | This is the unlock for replacing CSV P&L uploads. Current helpers exist (`listFinancialEventGroups`, `listTransactions`) but no production worker exists. Requires Finance and Accounting role. |
| **FBA Inventory API** | P0/P1 | Current FBA quantities and availability | Useful for fast current inventory snapshots. It returns fulfillment-network availability such as fulfillable, inbound, reserved, unfulfillable, and researching quantities. Current agency-os does **not** use this directly; WBR inventory comes from Windsor feeds. |
| **FBA reports via Reports API** | P0/P1 | Inventory planning, aged inventory, storage-fee risk, restock signals | Important report types include `GET_FBA_INVENTORY_PLANNING_DATA`, `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA`, `GET_RESTOCK_INVENTORY_RECOMMENDATIONS_REPORT`, `GET_FBA_STORAGE_FEE_CHARGES_DATA`, `GET_FBA_OVERAGE_FEE_CHARGES_DATA`, and `GET_FBA_FULFILLMENT_LONGTERM_STORAGE_FEE_CHARGES_DATA`. |
| **Returns reports via Reports API** | P1 | Units returned by ASIN/SKU/date | Use return report types such as `GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE` and FBA customer returns reports. Current agency-os returns sync is Windsor-derived and should move here. |
| **Customer Feedback API** | P1/P2 | Review/return topics, browse-node and ASIN feedback insights | This is **not** the raw returns ledger. It is useful for understanding why customers return/review negatively: topics, trends, snippets, and impact. Good for playbooks and listing-quality alerts, but not a replacement for returns reports or Finances data. |
| **Product Fees API** | P1 | Estimated referral/FBA fees by ASIN/SKU and price | Useful for margin modeling, fee sanity checks, price/planning workflows. Estimates are not guaranteed actuals; actual P&L still comes from Finances / settlement data. |
| **Product Pricing API** | P1 | Competitive pricing, featured-offer context, pricing alerts | Useful for Buy Box / pricing-position alerts and margin recommendations. Requires Pricing role. |
| **Sales API** | P2 | Aggregated order metrics | Likely overlaps with Sales & Traffic for our v1 use cases. Re-evaluate after Reports/Data Kiosk tests; may be useful for lightweight aggregate metrics but not a replacement for ASIN-level business facts. |
| **Catalog / Listings Items APIs** | P1 | Product metadata, listing status, content fields | Needed for MCP context, suppressed/listing-quality alerts, and SKU/ASIN mapping. Current code has SP-API listings preview/import via Reports API, but SaaS may need richer Listings Items calls. |

Data Kiosk live probe (2026-05-07): using the current agency-os SP-API app and Distex CA marketplace (`A2EUQ1WTGCTBG2`), `createQuery` accepted an `analytics_salesAndTraffic_2024_04_24.salesAndTrafficByAsin` query for `2026-05-01`, finished successfully, and returned 85 JSONL rows. Returned fields included `marketplaceId`, `childAsin`, `parentAsin`, `startDate`, `endDate`, `sales.orderedProductSales`, `sales.unitsOrdered`, `sales.totalOrderItems`, `sales.unitsRefunded`, `traffic.pageViews`, `traffic.sessions`, `traffic.buyBoxPercentage`, and `traffic.unitSessionPercentage`. This confirms Data Kiosk can return the same core ASIN-level Sales & Traffic shape we currently get from Reports API, with a cleaner query-selected schema and extra traffic metrics. Treat Data Kiosk as the preferred new business-facts ingestion path unless follow-up testing finds material gaps.

Data Kiosk caveats:

- It still uses async query processing and SP-API-like rate/concurrency limits, so the worker architecture remains necessary.
- Query results are JSONL documents, not normal synchronous API responses.
- Each requested field can have its own result-retention directive; query retention uses the shortest requested field retention. Keep queries narrow and versioned.
- Keep Reports API support for report families not yet available in Data Kiosk, for regression comparison during the rebuild, and as a fallback if Data Kiosk roles/access are missing for a tenant.

Storage-fee and long-term-storage alerting should combine:

- **Forward-looking risk:** `GET_FBA_INVENTORY_PLANNING_DATA` for aged units, estimated storage / long-term storage fees, excess units, sales velocity, and recommended actions.
- **Actual charges:** `GET_FBA_STORAGE_FEE_CHARGES_DATA`, `GET_FBA_OVERAGE_FEE_CHARGES_DATA`, `GET_FBA_FULFILLMENT_LONGTERM_STORAGE_FEE_CHARGES_DATA`, and Finances transactions for booked charges.
- **Action context:** FBA Inventory API current quantities plus sales velocity from Sales & Traffic / Data Kiosk.

The API roadmap should stay role-aware. Public-app review and app permissions should request enough roles to support the v1 sync backbone without overreaching into sensitive PII. If an API requires restricted or sensitive access, isolate it behind a clear product reason and security posture.

#### First sync experience (must feel productized, not admin-operated)

The first sync is a product surface, not just a worker implementation detail. A Pacvue-style onboarding experience works because the customer authorizes once, leaves the app if they want, and the platform quietly moves the workspace through clear readiness states over the next few hours.

The v1 contract should be:

1. **Connect.** User authorizes SP-API and Amazon Ads. The platform immediately discovers seller accounts, marketplaces, Ads profiles, accessible report scopes, and missing permissions.
2. **Build a sync manifest.** For each workspace / marketplace / source, create explicit jobs by report type and date window. Jobs are idempotent on `(workspace_id, source, marketplace, report_type, date_from, date_to, grain)` so retries cannot double-count.
3. **Fast lane first.** Prioritize the last 30 days of high-utility data:
   - Sales & Traffic by ASIN
   - Ads campaign performance
   - Sponsored Products + Sponsored Brands search terms
   - catalog/listing metadata
   - current inventory health snapshot
   - basic financial-event availability checks
4. **Mark the workspace usable early.** Once the fast lane completes, the user can use MCP tools, freshness-aware reports, and core alerts while deep history continues in the background. The product should not block on a full historical backfill.
5. **Deep backfill second.** Continue with older windows after recent data is ready: longer business-history windows, returns, financial events / transactions, inventory history where available, and all allowable Ads/search-term history.
6. **Show source-level readiness.** Every dataset exposes `empty`, `queued`, `syncing`, `ready_recent`, `ready_full`, `partial_error`, `stale`, or `reauth_required`. The connection screen should say things like "Ads: last 30 days ready; 4 historical chunks remaining."
7. **Make MCP freshness-aware.** `get_sync_freshness_status` is part of the launch experience, not an internal diagnostic. LLM tools should include coverage warnings when answering questions from partial data.
8. **Notify on completion or action needed.** In-app and email notifications fire when the first usable dataset is ready, when full backfill completes, or when a source needs reauth / permission repair / manual attention.

This is the customer-experience difference between "we have sync code" and "your account is setting itself up."

#### Re-sync, repair, and missed-date recovery

Users and support staff need a safe way to repair data without database surgery:

- **Manual re-sync by source and date range.** A user can re-sync business, Ads, search terms, returns, financial events, or inventory for a selected date window. Re-sync creates replacement jobs using the same idempotent job keys as the initial backfill.
- **Gap detection.** Nightly checks scan fact tables for missing dates, incomplete chunks, failed report jobs, and stale sources. Detected gaps enqueue repair jobs automatically when credentials are valid.
- **Replace-window semantics.** For daily-grain fact tables, successful jobs replace the exact date window they own, then insert fresh rows. This avoids duplicate facts and makes retry behavior explainable.
- **Retry policy.** Transient Amazon errors, rate limits, and report-pending states back off automatically. Permanent errors move the source to `partial_error` or `reauth_required` with a human-readable reason.
- **Coverage ledger.** Store sync coverage separately from fact rows: report type, date range, status, row count, run id, error, started/completed timestamps, and last verified timestamp. The UI and MCP read from this ledger.
- **Support override.** Internal admins can force re-run, cancel stuck jobs, or mark a known-empty date as verified-empty.

For v1, this can be utilitarian. It does not need a full BI dashboard, but it does need to prevent the common "one date failed six weeks ago and nobody noticed" problem.

#### Ads history reality: API lookback + retained warehouse data

Current agency-os treats Amazon Ads reporting as a short-retention source. The live code uses an observed 60-day inclusive guardrail for Ads backfills, but a 2026-05-07 live probe found the current Sponsored Products campaign report retention start at `2026-02-01`, roughly ~95 days. The exact lookback appears report-type-specific and should be discovered per source, not hardcoded globally.

The Pacvue comparison now looks less mysterious: Distex onboarded into Pacvue in January 2026. Pacvue shows no data for June 2025 and no data for October 1-4, 2025. Its first visible campaign-level history starting around mid-October 2025 is consistent with "Amazon's available API lookback at onboarding + Pacvue-retained warehouse data from then forward," not a fresh 12-month Ads pull.

This is the product lesson: **once a customer connects, the SaaS must never let Ads history disappear.** Initial backfill only gets whatever Amazon still exposes. Long-term history is created by our own warehouse retention.

Live probe result (2026-05-07): using the current agency-os Amazon Ads app and Distex CA Ads profile, a direct Sponsored Products campaign report request to `POST /reporting/reports` for `2025-06-01` → `2025-06-30` failed with Amazon's response: `startDate (2025-06-01) must be equal to or after report type data retention start date (2026-02-01)`. That means the current v3 Sponsored Ads reporting endpoint allows roughly ~95 days for that report type today. This matches the corrected Pacvue observation better than the earlier assumption of a longer hidden backfill.

Second probe result (2026-05-07): likely unified/report-builder discovery paths were not publicly discoverable from the current Ads API base URL. Trial report type IDs such as `campaigns`, `campaignMetrics`, `campaignPerformance`, `sponsoredAdsCampaigns`, `unifiedCampaigns`, and `crossProgramCampaigns` all returned `configuration reportTypeId is unknown or invalid` on `POST /reporting/reports`. Legacy `POST /v2/sp/campaigns/report` returned `Method Not Found`, while legacy `POST /v2/hsa/campaigns/report` explicitly returned `Report date is too far in the past. Reports are only available for 60 days.` Current app access is not enough to identify the unified reporting API contract by guessing endpoints.

Amazon announced a new unified reporting experience in open beta at unBoxed 2025 with longer history: up to 15 months of daily/weekly-grain data and up to six years of monthly/yearly/summary-grain data through the report builder UI, reporting API, and Amazon Marketing Stream. This is still worth investigating, but it is not required to explain the observed Pacvue / Distex behavior.

Implementation implications:

- On first connect, backfill each Ads report type to its real Amazon retention boundary, not a single hardcoded 60-day value.
- Persist all daily Ads facts indefinitely after connection; the SaaS warehouse becomes the long-term history.
- Show the customer their coverage start date per source: e.g. "Sponsored Products campaign history starts on 2025-10-13 because that is the earliest data available when this profile connected."
- Re-sync can repair dates inside the Amazon retention window. Older dates can only be repaired if they already exist in our warehouse or if the user provides a historical import.
- Do not market 12-24 months of Ads history for newly connected accounts unless we have verified a source that can actually retrieve it.

Remaining Ads-history spike:

1. Confirm the current max historical window for each Sponsored Ads report type we need: campaign, search term, placement, advertised product, purchased product, budget, targeting.
2. Find the unified reporting / report builder API contract, beta access path, endpoint names, report templates, dimensions, and rate limits.
3. Separately verify campaign-level Sponsored Products history; this may have a materially longer window than search-term or placement reports.
4. Confirm whether the Ads console can export older data than the public API for the same report types, and whether any API endpoint can generate the same report.
5. Ask Amazon Ads support / partner contacts directly about unified reporting API access for public third-party apps.
6. Evaluate AMC as an optional v1.5 / v2 data source for longer-lookback advertising analysis, noting that AMC is not a drop-in replacement for campaign daily fact tables.
7. Decide whether to support manual historical import for customers coming from Pacvue / Perpetua / Quartile / Sellerboard / their own warehouse.
8. Make the onboarding copy honest: "We can backfill whatever Amazon still exposes at connection time; from then on, we retain your history indefinitely."

### Pillar 2 — SOP & Playbook Library

The current Ecomlabs SOPs and Playbooks (in ClickUp) are well-structured already: trigger types (A/B/C/D), execution variables, gotchas, cadence. The platform hosts them first-party:

- Versioned Markdown with structured frontmatter (`trigger`, `cadence`, `tags`, `loom_url`, `status`)
- A shared canonical library with customer overrides (a customer can fork the Sale Price SOP without losing upstream updates)
- Exposed via MCP (`read_sop`, `list_sops(filters)`, `read_playbook`)
- Playbooks orchestrate multi-track engagements; SOPs execute within them — this distinction is preserved

ClickUp is fine as a draft surface during build, but cannot be the long-term system of record.

### Pillar 3 — MCP

The conversational and analytical surface. Customers connect their preferred LLM client (Claude.ai, Claude Desktop, etc.) to the platform's MCP server and get:

**Tools that already exist in agency-os today (port and adapt):**
- `resolve_client`, `query_business_facts`, `query_ads_facts`, `query_search_term_facts`, `query_catalog_context`
- `query_monthly_pnl_detail`, `get_monthly_pnl_report`, `get_monthly_pnl_email_brief`, `draft_monthly_pnl_email`, `list_monthly_pnl_profiles`
- `get_wbr_summary`, `draft_wbr_email`, `list_wbr_profiles`
- `get_sync_freshness_status`, `list_child_asins_for_row`, `get_asin_sales_window`

**Tools that need to be built for the new product:**
- `query_returns_facts`, `query_financial_events`, `query_inventory_health` (depend on Pillar 1 sync expansion)
- `read_sop`, `list_sops`, `read_playbook` (depend on Pillar 2 SOP/Playbook migration out of ClickUp)
- `propose_aged_inventory_clearance` and similar action tools (later)
- `datadive_niche_dive`, `datadive_get_mkl`, `datadive_get_competitors` (Pillar 5 external research adapter)

The MCP is where the strategic LLM partner experience lives. It is **not** rebuilt inside the platform UI — customers bring their own LLM client. See Appendix B for the validated tool surface that exists today.

#### MCP onboarding and context delivery

Current agency-os MCP usage depends on Claude Project setup: paste `project_instructions.md`, upload WBR / Monthly P&L / analyst playbooks, and keep those files refreshed manually. That is acceptable for an internal pilot but not for SaaS. A customer should be able to connect the MCP server from Claude, ChatGPT, or another MCP-capable client and ask a normal question without being told to upload prompt files first.

The SaaS MCP should package its own operating context:

- **Server instructions.** The MCP server's `instructions` should contain the short universal behavior contract: resolve workspace/client first, prefer canonical IDs, check freshness, use narrow tools, surface warnings, never invent unavailable data, and treat mutating tools as approval-required.
- **First-call bootstrap tool.** Add a read-only tool such as `get_mcp_capabilities` or `get_started` that returns the current tenant/workspace capabilities, available datasets, freshness states, common workflows, and examples. Tool descriptions should nudge clients to call this when context is missing.
- **As-needed workflow guides.** Replace static Claude Project files with MCP resources or tools such as `read_workflow_guide("wbr")`, `read_workflow_guide("monthly_pnl")`, `read_workflow_guide("ads_analysis")`, and later `read_sop`. The LLM can fetch the relevant guide only when the user asks for that workflow.
- **Context in tool responses.** Resolution and freshness tools should return compact routing/context hints directly: which profile to use, what data exists, what is stale, which next tools are appropriate, and what caveats should be included in answers.
- **Workflow-aware tool descriptions.** Tool descriptions should carry enough usage guidance that a generic MCP client can choose correctly without external project instructions. Avoid relying on hidden Claude-specific prompt state.
- **Tenant-configured voice and policies.** Customer-specific preferences (draft tone, sender identity, markets, approval policy, terminology) should live in SaaS settings and be returned by capability/context tools, not stored in a user's local Claude project.
- **Versioned prompt/context bundles.** Store playbook and workflow-guide versions in the SaaS, log which version informed each generated draft, and expose changelog metadata for support/debugging.

Do not assume every MCP client handles server instructions, resources, or prompts identically. The robust pattern is redundant but compact: put universal rules in server instructions, encode tool-choice guidance in descriptions, expose a bootstrap tool, and include freshness/routing hints in normal tool outputs. Manual project-file setup should be optional power-user polish, not required onboarding.

### Pillar 4 — Proactive alerts (agentic, but not LLM-on-send)

Per-tenant cron jobs evaluate deterministic rules against the warehouse and emit structured alerts. **No LLM inference on send** — alerts are dumb on purpose, both to control costs and because re-creating a chat experience inside a notification channel was tried (Slack DM era, pre-MCP) and was meaningfully worse than letting users open Claude with the right context.

Alert design:
- Deterministic rule decides whether to fire
- Alert payload includes a **deep-link or copyable prompt** that bootstraps a Claude session with full context (ASINs, dates, relevant SOP slugs)
- Channels: in-app inbox (primary, always on), email (default push), Slack (optional v2)

Initial alert catalog (sketch):
- Long-term storage fee risk by date
- SP-API / Ads API reauthorization expiring (T-30, T-7, T-1)
- Monthly P&L ready on the 1st
- Ad spend or ACoS anomaly
- Suppressed listings detected
- Buy Box loss

### Pillar 5 — External research integrations

DataDive first (paid API, $149/mo Standard or $490/mo Enterprise gating). Wrapped as MCP tools mirroring the Ahimsa Essentials copy workflow already documented internally. Pattern is reusable: each external research source becomes its own auth + adapter + MCP tool surface. Helium 10, Keepa, etc. follow if demand justifies the integration cost.

### (Demoted) Dashboards

Build only the minimum needed for: account settings, connection management, alert inbox, billing. No charts, no exploratory BI surface — that work belongs in the LLM client via the MCP.

---

## 4. Architecture & Key Decisions

### Current agency-os shape (one-paragraph overview)

agency-os is a Python (FastAPI) + Next.js + Supabase monorepo. A separate `worker-sync/` process runs an async loop that orchestrates nightly Amazon syncs (default 2 AM in a configurable timezone, 60-second poll cadence) — pulling business reports via SP-API, polling Amazon Ads reporting endpoints until ready, and writing fact rows to Postgres tables (`wbr_business_facts`, `wbr_ads_campaign_daily`, `wbr_ads_search_term_facts`). An MCP server (`backend-core/app/mcp/`) exposes a tool surface across five domains (clients, analyst, P&L, WBR, ClickUp). RLS is admin-only today. The new product preserves the substrate (Supabase + Next + Python workers + TS-MCP) but rebuilds the schema, tenancy, and auth posture.

### Greenfield, not a fork

New repo, new database. agency-os has too much agency-specific tenancy (`agency_clients`), deprecated tooling (Windsor pipeline), and structural decisions (admin-only RLS, plaintext tokens, CSV-driven P&L) that would be cheaper to rebuild than to refactor in place.

### Strategic split: MercatoPath becomes the core product

The prior framing of "agency-os connects to MercatoPath via API for Amazon data" understates the move. The actual decision is bigger: MercatoPath should absorb roughly 80% of what agency-os does today, while agency-os becomes a small bespoke layer for Ecomlabs-only workflows.

**Lives in MercatoPath:**

- All Amazon ingestion: SP-API, Ads API, Finances API, FBA reports, returns reports, and future seller-data connectors
- Encrypted token storage, OAuth, public-app review, permission repair, and reauthorization alerts
- Fact warehouse for business, ads, search terms, returns, inventory, and financial events
- Sync manifest, source readiness states, coverage ledger, freshness API, re-sync, and missed-date repair
- WBR snapshots, scoring, and email drafts
- Monthly P&L: CSV ingest fallback at first, Finances API as the long-term source
- MCP server: the generalized, multi-tenant version of the Ecomlabs Tools MCP
- Reauth alerts, long-term-storage-fee alerts, anomaly alerts, and other deterministic alert surfaces

**Stays in agency-os / `tools.ecomlabs.ca` for now:**

- ClickUp integration for Ecomlabs daily ops: SOPs, playbooks, tasks, task prep, and internal execution flow
- Pacvue tag mapping, unless MercatoPath generalizes this into "custom WBR row groupings"
- Internal-only operational tools that do not make sense as SaaS features
- Team, hours, VA tracking, and command-center-style Ecomlabs management surfaces
- Internal Slack tooling, including `theclaw` and draft-message workflows

This makes Ecomlabs customer-zero for MercatoPath, not the owner of a second copy of the same product. agency-os sits alongside MercatoPath as a private extension layer only where the SaaS product should not carry Ecomlabs-specific complexity.

### What gets rebuilt in MercatoPath using agency-os as reference

The following pieces should be read carefully, but not copy-pasted blindly:

- SP-API and Ads API LWA flow logic (state signing, token exchange, region routing)
- Sync orchestration shape (worker polling Amazon's async report-ready pattern)
- Fact-table column choices for business / ads / search-term reports (these evolved through real pain)
- The Ecomlabs Tools MCP tool surface (effectively the v1 MCP spec for the new product)

### What gets left behind or deleted after cutover

- `agency_clients` tenancy model
- Windsor-derived ingestion paths
- Dual-write legacy auth tables (`wbr_amazon_ads_connections` etc.)
- Plaintext token storage
- Admin-only RLS posture
- CSV-only P&L as the long-term model
- ClickUp coupling for MercatoPath SOPs and playbooks
- Amazon warehouse / WBR / P&L / MCP code in agency-os once each domain has reached parity in MercatoPath

### Likely stack (TBD pending a closer look)

- Supabase (Postgres + Auth + RLS) — works well today, no reason to switch for v1
- Render for web/API/worker hosting — acceptable for v1 if long-running work is isolated to background workers and not request handlers
- Next.js for the web app
- Python workers for sync (FastAPI + worker process pattern, mirroring what's working today)
- TypeScript for the MCP server
- Monorepo: `web/`, `worker/`, `mcp/`, `shared/`

### Durable sync queue, not request-time backfills

Hard rule for MercatoPath: **anything that takes longer than about five seconds runs in a worker. HTTP routes only validate, discover, enqueue, and return. No sync, backfill, report polling, file download, or retry loop runs inline in a request handler.**

agency-os currently violates this in WBR backfill routes: the FastAPI route awaits `svc.run_backfill(...)`, so the browser request stays open for the entire backfill. That can work for an internal tool by luck, but it fails as a SaaS pattern: gateways time out, UI state lies, deploys or worker restarts can kill in-flight work, and there is no durable recovery point.

MercatoPath day-1 sync architecture:

1. **OAuth / connect route returns fast.** Seller Central and Ads OAuth callbacks create encrypted connection rows, validate tokens, discover marketplaces/profiles, and return. They do not start data sync directly.
2. **Manifest route enqueues jobs.** For each `(workspace, source, marketplace, report_type, date_window, grain)`, insert into `sync_jobs` with:
   - `priority` (`fast_lane` > `deep_backfill`)
   - deterministic `idempotency_key` with a unique constraint
   - `status = queued`
   - `attempts = 0`
   - `next_attempt_at = now()`
3. **Workers claim jobs transactionally.** Use Postgres row locking (`FOR UPDATE SKIP LOCKED`) via a direct Postgres connection or a database function/RPC, not ordinary Supabase REST calls. Claim transaction should be short: mark one job running, set `worker_id`, `claimed_at`, `lease_expires_at`, commit, then call Amazon outside the lock.
4. **Workers write facts idempotently.** Successful jobs replace the exact fact window they own, then insert fresh rows. Job idempotency prevents duplicate queue rows; replace-window writes prevent duplicate facts.
5. **Rate-limit at the upstream boundary.** Use per-source token buckets before Amazon calls. Rate-limit keys should be specific enough for reality, e.g. `spapi:reports:create_report:na`, `spapi:data_kiosk:create_query:na`, `ads:reporting:create_report:<profile_id>`, and `ads:reporting:get_report:<profile_id>`.
6. **Coverage ledger is product truth.** `sync_jobs` is the execution queue. `sync_coverage` is what the UI and MCP read for readiness: `empty`, `queued`, `syncing`, `ready_recent`, `ready_full`, `partial_error`, `stale`, `reauth_required`.
7. **Stale-claim reaper is mandatory.** Jobs need `lease_expires_at` / `heartbeat_at`. A scheduled reaper returns expired running jobs to queued or failed based on retry policy. This is what makes deploys, crashes, OOMs, and worker restarts survivable.
8. **Notify from readiness events.** When all fast-lane jobs for a workspace succeed or are verified-empty, emit `workspace.ready_recent`; when deep backfill completes, emit `workspace.ready_full`. Notifications should come from worker/event processing, not the original HTTP request.

Postgres-backed queues are acceptable for v1 and fit Supabase well. If queue throughput becomes the bottleneck, move execution to Redis/BullMQ, Temporal, or a managed queue later. Do not prematurely add infrastructure, but do design the job/coverage schema so the execution engine can change without changing product semantics.

Supabase implementation note:

- **Direct Postgres connection is supported.** A Render background worker can use Supabase's normal Postgres connection string with `psycopg`, `asyncpg`, or SQLAlchemy and run normal transactions, including `FOR UPDATE SKIP LOCKED`. This is the preferred worker pattern when available.
- **Network caveat.** Supabase direct database connections use IPv6 by default. If the host environment has IPv6 issues, use Supavisor session mode or Supabase's IPv4 add-on. Avoid relying on transaction-pooler behavior unless the database library is configured correctly, especially around prepared statements.
- **RPC alternative is supported.** The worker can call a Postgres function through Supabase `.rpc()` where the function performs the atomic claim/update in one database-side transaction. This keeps the claim primitive narrow and avoids exposing arbitrary SQL to the worker.
- **Do not claim jobs with separate REST calls.** A `select queued job` followed by `update job running` through normal Supabase REST/Data API calls is race-prone under concurrent workers. Claiming must be one atomic SQL statement/function.

Later improvements:

- Per-workspace fairness / round-robin so one large seller cannot starve other tenants' deep backfills.
- User-visible sync cancellation for unwanted deep backfills.
- Queue observability: depth, age, throughput, retry rate, error rate by source/report type, and oldest queued fast-lane job.
- Worker autoscaling based on queue depth and upstream rate-limit headroom.

### Lessons from agency-os: build for AI-maintainability

agency-os validated the product thesis, but it also shows the cost of fast exploratory/vibe-coded evolution: large files, overlapping service responsibilities, legacy paths kept alive, docs from multiple product eras, and routes/services that know too much about each other. MercatoPath should treat AI coding agents as a permanent part of the engineering process and design guardrails accordingly.

Repo scan snapshot (2026-05-07):

- 569 app/source files under `backend-core/app` and `frontend-web/src`.
- 87 app/source files are over 400 lines.
- 31 app/source files are over 700 lines.
- Several current hotspots exceed 1,500 lines: `analyst_query_tools.py`, `frontend-web/src/app/ngram-2/page.tsx`, `aiPrefill.ts`, `adscope/views.py`, `routers/wbr.py`, and `amazon_ads_sync.py`.
- Docs are useful but noisy: many long planning docs remain from deprecated or superseded eras. The new repo needs current docs and archived docs to be visibly separated.

The answer is **not** a rigid "every file under 70 lines" rule. That is too extreme for real systems: schemas, test fixtures, generated types, route definitions, and cohesive parsers can reasonably exceed 70 lines. The useful rule is smaller ownership boundaries:

- Prefer files under ~300 lines for normal application modules.
- Treat 400+ lines as a review smell.
- Treat 700+ lines as a refactor ticket unless the file is generated, declarative config, or a deliberately dense test fixture.
- Prefer functions under ~40-80 lines, with one reason to change.
- Split by responsibility, not by arbitrary line count. A 120-line cohesive parser is better than ten 20-line files that require constant jumping.

MercatoPath engineering guardrails:

- **Conventional domain module shape.** Every domain should look familiar:

  ```
  services/<domain>/
    repository.py    # DB access only, no business logic
    service.py       # business logic; orchestrates repositories + external clients
    schema.py        # Pydantic models for I/O
    mcp_tools.py     # MCP tool surface for this domain, if any
    tests/
      test_service.py
      test_repository.py
  ```

  Use bounded domains such as `auth`, `tenancy`, `amazon_connections`, `sync`, `datasets`, `mcp`, `alerts`, `billing`, `workspaces`, and `playbooks`. Avoid dumping cross-domain logic into generic `services/` or giant route files.
- **Import rules enforced by linting.** Routers may import from `services/<domain>/service.py` only, never directly from `repository.py` or raw database clients. MCP tools should call service-layer methods, not query tables directly. This kills the common "I'll just add it here for now" growth pattern.
- **Thin routes, explicit service layer.** API routes validate auth/input and call one use-case/service. Business rules, sync logic, and mapping logic live outside route handlers. Every route endpoint requires verified auth, a typed request/response model where applicable, and at least one integration test for non-trivial behavior.
- **Source adapters separate from warehouse logic.** Amazon API clients create/poll/download raw source payloads. Transform/mapping modules convert payloads to canonical facts. Store modules write facts idempotently. Do not mix all three in one class.
- **Canonical data contracts first.** Define versioned fact schemas and coverage-ledger schemas before building UI. Every sync writes coverage metadata, row counts, source window, source API/report type, and transform version. Generate a single `schema.py` / `schema.ts` reference from migrations or canonical models so AI agents are not guessing from migrations, ad hoc query code, and frontend types that drift apart.
- **Type-safe boundaries.** Use Pydantic on backend boundaries, Zod or generated TypeScript types on frontend boundaries, and generated TS types from backend contracts where practical. No untyped JSON should cross API, worker, or MCP boundaries without an explicit parser.
- **Idempotency by design.** Every sync job has a deterministic key: `(workspace_id, source, marketplace_id, dataset, grain, date_from, date_to, version)`. Retries replace the owned window and cannot double-count.
- **Small MCP tools, self-describing outputs.** Tools return structured data with freshness, caveats, next-tool hints, and version metadata. Do not rely on local Claude Project files to explain behavior. New MCP tools must follow a template and ship with at least one integration test.
- **Tests at module seams.** Unit-test transforms and idempotency heavily. Integration-test API client happy/error paths with fixtures. End-to-end test only the few critical onboarding/sync flows. Every new feature should have at least one happy-path integration test that hits the actual database, because that is the best defense against plausible-looking AI code with wrong side effects.
- **Golden fixtures for Amazon payloads.** Store small sanitized real payloads for Data Kiosk, Reports API, Ads reports, Finances transactions, FBA inventory, returns, and fee reports. These are the regression harness for AI edits.
- **Docs as contracts, not archaeology.** Keep `docs/current/` for live architecture/decisions and `docs/archive/` for superseded planning. Every major domain has a short `README.md` with purpose, boundaries, key tables, and owner workflows. No `*_plan.md` should survive past feature merge: convert the decision into an ADR or move the planning doc to archive.
- **Architectural decision records.** Add `docs/adr/` for decisions like Data Kiosk over Reports API, org/workspace tenancy, encrypted token storage, MCP context delivery, and sync idempotency. Each ADR captures the decision, alternatives considered, and why this choice won. This gives AI agents a stable decision trail.
- **Deprecation registry.** Maintain `DEPRECATED.md` with every deprecated module/table/path, deprecation date, replacement, and removal target. AI agents should read this before extending old code. Do not rely on comments buried inside old files.
- **CI guardrails.** Enforce lint, typecheck, tests, migration checks, and file-size warnings. Warn when a file passes 600 lines; fail only after agreed thresholds. Make the smell visible before 2,000-line files become normal.
- **AI agent instructions in repo.** Ship a strict, prescriptive `AGENTS.md`: read domain README first, keep changes scoped, update tests/fixtures, do not edit archived docs unless asked, do not create new cross-domain god files, and add ADRs for architecture changes.
- **Repo-level AI tooling.** Add `.claude/` or equivalent repo-owned AI context with repeatable commands (`add-fact-table`, `add-mcp-tool`), a code-review checklist, an architecture overview, and a glossary for terms like `organization`, `workspace`, `connection`, `sync run`, and `fact`. This makes the workflow shared across AI coders instead of living in one local memory.
- **When-in-doubt rules for AI agents.** If something might be deprecated, ask before extending it. If file ownership is unclear, propose a split instead of adding to a large file. If an existing pattern is unclear, find the most recent equivalent and copy its shape before inventing a new one.
- **No hidden production behavior.** Feature flags, cron schedules, sync windows, retention assumptions, and API role requirements should be config/schema/docs, not scattered constants.
- **Deprecation path required.** If a module is replaced, mark the old module frozen, move it behind a compatibility adapter, and create a deletion issue/date. Do not let "legacy but still imported" become the default state.

Meta-lesson: vibe coding can produce genuinely useful features, but without structure it also produces architecture debt at the same speed. MercatoPath should not rely on everyone being more disciplined in the moment; it should make the correct path the easiest path through templates, lint rules, tests, ADRs, and explicit AI-agent instructions.

### Tenant model

Use one tenant model for all customer types:

```
Organization
  Members
  Workspaces
    Amazon Connections
    Marketplaces
    Brands
    Sync Jobs / Coverage Ledger
    MCP Context
```

The **organization** is the billing, security, and team container. The **workspace** is the operating data container: one Amazon business, client, or account cluster with its own connections, marketplaces, datasets, alerts, and MCP context.

Do not make users choose a hard product fork between "agency" and "brand" during signup. The homepage can speak to both agencies and brands, but the product model should simply let any organization create one or many workspaces and assign team members to them. A brand operator with one Amazon business starts with one workspace. A holding company or multi-account seller can add more. An agency creates one workspace per client. The same schema supports all of them.

Team access is organization-level membership plus workspace-level permissions. Suggested roles:

- `owner` — billing, org settings, all workspaces
- `admin` — manage workspaces, connections, members
- `operator` — use tools, run syncs, create drafts for assigned workspaces
- `viewer` — read-only access to assigned workspaces

This avoids embedding agency-specific concepts into the core schema while still supporting agency workflows cleanly.

---

## 5. Amazon auth reality (what SaaS requires)

These are non-negotiable for a public product and worth surfacing here:

- **Token storage must be encrypted at rest.** Column-level encryption (Supabase Vault or app-layer AES-GCM with a KMS key). No plaintext.
- **365-day reauthorization.** Sellers must reconsent annually. Without proactive T-30/T-7/T-1 notifications, syncs silently die for a chunk of customers each renewal cycle. This is the #1 churn risk if ignored.
- **Public-app review.** Both SP-API (Selling Partner Appstore listing review) and Amazon Ads API public-app review are required to onboard arbitrary sellers. Each has its own review process. Plan 4–8 weeks elapsed time minimum, with privacy policy, security questionnaire, working production OAuth, etc. The product **name** is locked in during this review, so it ripples back to branding decisions.
- **Auth code expiry: 5 minutes.** Existing pattern respects this; flag if exchange ever gets queued.
- **RDT (Restricted Data Token) handling.** Required for any PII-sensitive report (e.g., orders with buyer info). Not implemented today. May or may not be needed v1 depending on which reports ship.

---

## 6. Open decisions (in suggested order)

1. **Branding follow-through.** Working name is now **MercatoPath** and `MercatoPath.com` is owned. Still decide final logo/visual identity, OAuth app display name, privacy-policy company language, repo name, and marketing-site copy before public-app review. The product name is effectively no longer TBD, but Amazon review will lock the submitted app display name.
2. **Tenant schema details.** Direction is org → workspaces → connections with workspace-level team permissions. Still decide exact table names, role matrix, billing ownership, and whether Amazon connections can ever be shared across workspaces.
3. **Long-term agency-os shape.** Not a launch blocker. After MercatoPath absorbs sync, warehouse, WBR, P&L, and MCP, choose between:
   - agency-os survives as a small private app for ClickUp, Pacvue mapping if not absorbed, VA/team tooling, and Slack drafts. This keeps SaaS complexity lower but leaves Ecomlabs with two URLs, two auth flows, and ongoing two-product maintenance.
   - Ecomlabs-specific tools become private/org-scoped MercatoPath features. This is more SaaS-side complexity, but it may be useful for future agency-tier customers and could eliminate agency-os entirely.
4. **Stack final call.** Default stick with Supabase + Next + Python + TS-MCP. Confirm or pivot.
5. **Repo layout.** Monorepo recommended.
6. **v1 alert catalog.** Which 3–5 alerts ship at launch.
7. **Pricing tiers.** Mapped against seller GMV bands and agency client counts. *Initial structure drafted in Section 7 — actively under discussion.*

---

## 7. Pricing (DRAFT — open discussion)

> **Status:** Working draft. Numbers, bands, and inclusions are starting points to react to, not committed pricing. Revisit after public-app review timing is clearer and after a direct conversation with DataDive about reseller / partner terms.

### Pricing dimension

GMV is the primary lever. Reasoning:
- Industry norm — customers expect revenue-based pricing from ecommerce tools.
- Auto-verifiable from SP-API the moment a customer connects (no honor system).
- Customers know their own GMV cold; it's the easiest number for them to anchor on.
- Auto-expansion built in: a $3M customer becomes a $7M customer next year and bumps tiers without a sales conversation.
- Loosely tracks cost drivers (transaction count, ASIN count, ad spend) without exposing those gnarly dimensions to the buyer.

Order volume is more cost-correlated but customers don't carry that number in their head. SKU count punishes long-tail catalogs and tracks neither cost nor value cleanly.

**Marketplace count** is the orthogonal multiplier — captures multi-country sellers without forcing them into a higher GMV bracket they don't belong in.

### Cost reality check

Marginal infra cost per tenant is small (~$2–6/month even at Jade scale, $26M GMV). Pricing is about value capture, not cost recovery. Real variable costs per customer are support time, DataDive API quota (if pooled), and onboarding hand-holding — not Supabase rows.

### Tier structure (draft)

| GMV band | Price/mo (draft) | Marketplaces | DataDive | Support | Proactive alerts |
|---|---|---|---|---|---|
| **$0–500k** | $29 | 1 (+$15 each) | None | Self-serve | Reauth only |
| **$500k–1M** | $79 | 1 (+$15 each) | Pooled (light cap) | Email, 48h | Core set |
| **$1M–5M** | $199 | 2 (+$25 each) | Pooled | Email, 24h | Full |
| **$5M–10M** | $499 | 3 (+$25 each) | BYO or Pooled | Slack, 12h | Full |
| **$10M–20M** | $999 | Unlimited | BYO | Priority Slack, 4h | Full + custom |
| **$20M+** | Custom ($1,500+) | Unlimited | BYO Enterprise | Dedicated CSM | Full + custom |
| **Agency** | $99/workspace × N (volume discount past 10) | Per workspace | BYO at agency level | Priority | Full |

### Design principles baked into the structure

1. **Priority support is the explicit upgrade benefit at $5M+.** Single biggest differentiator at the top of the funnel; easiest line item for buyers to justify internally.
2. **DataDive transitions from pooled → BYO** at the price point where customers can comfortably justify their own $149+ license. Clean economic logic, no awkward conversations.
3. **Marketplace add-on is orthogonal to GMV tier.** A $1M seller with three marketplaces shouldn't pay $499 just for the third marketplace.
4. **Agency tier is per-workspace, not GMV-banded.** A 30-client agency doesn't fit any single GMV bucket. Per-workspace × volume discount captures real MRR (~$2,000/mo at 30 clients).
5. **$29 entry tier is a customer acquisition cost, not a profit center.** Self-serve only, no DataDive, sync throttled, alerts limited to reauth. Works only if onboarding is dirt-cheap and graduation to higher tiers is automatic via SP-API GMV signal.

### Open questions

- **Should the $29 tier exist at all?** It's strategically defensible (positions next to Helium 10 / Jungle Scout pricing) but consumes disproportionate support and signals low value. Alternative: start at $79 with a 14-day trial, kill the entry tier entirely.
- **DataDive partner terms.** Pooled-Standard usage may violate their TOS. Need a direct conversation with DataDive about a partner / reseller arrangement. Until resolved, treat "pooled DataDive" as conditional.
- **Annual discount?** Standard 2-months-free annual prepay is industry norm and improves cashflow predictability, but increases churn risk concentration.
- **Trial structure.** 14-day full-feature trial vs. permanent free tier vs. demo-only. Probably 14-day trial; revisit after first 10 customers.
- **Agency volume discount curve.** Linear past 10 workspaces? Step-function? Negotiated above 50? Needs modeling against expected agency book size distribution.
- **Currency / international pricing.** USD-only for v1 likely fine; Canadian / EU pricing parity becomes a question once non-NA sellers are a real % of MRR.

### Revisit triggers

Re-open the pricing conversation when:
- Public-app review approval lands (changes timeline assumptions)
- DataDive partner conversation completes (changes pooled vs. BYO economics)
- First 10 paying customers in (real signal on price elasticity per band)
- Agency channel produces first 3 deals (real signal on per-workspace economics)

---

## 8. Suggested sequencing

This is not an incremental "swap agency-os ingestion sources" project. MercatoPath should rebuild the warehouse, WBR, P&L, sync ledger, and MCP greenfield. agency-os should stay mostly static during the build so Ecomlabs does not spend months maintaining two half-migrated systems.

| Phase | Focus |
|---|---|
| Phase 0 | MercatoPath branding follow-through, schema, repo, Supabase setup, encrypted token store, durable `sync_jobs` / `sync_coverage` schema, worker claim/retry/reaper pattern, public-app review submitted |
| Phase 1 | Self-serve OAuth onboarding (SP-API + Ads API). Productized first-sync orchestration via durable workers: fast-lane 30-day sync, source readiness states, re-sync / repair jobs, rate-limited job execution, and core sync (business, ads, search terms, returns, financial events, inventory health). MCP v1 with freshness-aware tools and self-contained onboarding context (no required Claude Project file uploads). |
| Phase 2 | WBR and Monthly P&L rebuilt against MercatoPath facts. CSV P&L ingest exists as fallback; Finances API worker advances toward replacing it. SOP/Playbook library migrated out of ClickUp, exposed via MCP. DataDive adapter. Reauth notifications. In-app inbox. |
| Phase 3 | Proactive alert engine + initial alert catalog (LTSF, reauth, monthly P&L ready, ad anomalies). Email push. |
| Phase 4 | Agency-tier features (multi-workspace, white-label inbox, bulk SOP execution). Slack push. Additional research adapters. |

Public-app review runs in parallel with Phase 1; if it's not approved by end of Phase 2, soft-launch is gated.

Ecomlabs migration happens domain-by-domain after parity, not mid-flight:

1. **WBR cutover.** Run MercatoPath WBR outputs against current agency-os WBR for several clients and weeks. Cut over Ecomlabs workspaces when numbers, row groupings, and draft quality match or improve.
2. **P&L cutover.** Run CSV-backed P&L and Finances-backed P&L in parallel until line items reconcile well enough for client use. Keep CSV fallback until Finances coverage is proven.
3. **MCP cutover.** Point the Ecomlabs Claude/ChatGPT MCP workflow at MercatoPath once core analyst, WBR, and P&L tools reach parity.
4. **Delete moved agency-os code.** After each domain cutover, remove the moved code from agency-os in a deliberate cleanup PR instead of leaving duplicate production surfaces alive.

---

## 9. Risks & unknowns

- **Public-app review timing.** Could be 4 weeks, could be 12. Hard external dependency.
- **PnL-from-API completeness.** Reconstructing P&L from `list_transactions` is genuinely hard — refunds, reserves, LTSF, returns processing fees, FBA fulfillment, removal orders all map differently. Realistic v1 may still need CSV fallback for certain line items.
- **Amazon Ads historical depth.** Current agency-os uses Sponsored Ads reporting endpoints with an observed short backfill window (~95 days in a 2026-05-07 live Sponsored Products campaign-report probe). Pacvue's Distex behavior now appears consistent with limited API lookback at onboarding plus Pacvue-retained warehouse data afterward, not a fresh 12-month pull. Do not promise 1-2 years of Ads history for newly connected accounts until each report type's source and lookback are verified.
- **DataDive API stability.** Single external dependency for Pillar 5 v1. Worth a contingency plan if their API changes or their pricing shifts again.
- **Self-serve onboarding UX for non-technical sellers.** OAuth into two separate Amazon apps (SP-API + Ads), then profile selection, then first-sync wait. This flow is the #1 conversion bottleneck and deserves UX investment. The fast-lane sync exists specifically to shorten time-to-value while deeper history cooks in the background.
- **Inline long-running work.** agency-os has request-time backfills that can outlive gateway timeouts and die on deploy/restart. MercatoPath must not copy this pattern. Long-running work requires durable queued jobs, worker leases, retry/reaper logic, idempotent writes, and coverage-ledger-driven UI state.
- **Customer-zero parity risk.** Ecomlabs will depend on MercatoPath for real client work after cutover. WBR, P&L, and MCP migrations need explicit parity checks against agency-os before moved code is deleted.
- **Two-product gravity.** If Ecomlabs-specific workflows linger in both places, maintenance cost doubles and the SaaS product inherits confused boundaries. Decide domain ownership clearly: Amazon data, WBR, P&L, and MCP live in MercatoPath; truly internal ops remain in agency-os unless intentionally rebuilt as private/org-scoped MercatoPath features.
- **LLM client lock-in concern.** v1 leans on Claude.ai as the primary surface. Other MCP-capable clients are emerging — design the MCP to be client-neutral so this is a non-issue.
- **Pricing model.** Initial structure drafted in Section 7 (GMV bands, marketplace add-on, support tiering, agency per-workspace). Still actively under discussion — numbers and inclusions not committed. Pooled DataDive economics are conditional on partner-terms conversation.

---

## 10. What this is NOT

- Not "another Helium 10 / Jungle Scout." Those sell research data. This sells judgment + execution leverage.
- Not a dashboard product. Charts are commodity; the LLM-via-MCP partner is the product.
- Not a chatbot inside Slack. The conversational surface lives in the user's preferred LLM client.
- Not v1-targeted at sub-$1M sellers or $50M+ enterprises. Mid-market focus, expand later.

---

## Appendix A — Reference: agency-os auth implementation map

For implementers building the new repo, the agency-os files worth reading as reference:

- `backend-core/app/services/reports/amazon_spapi_auth.py` — SP-API OAuth, state signing, token exchange/refresh
- `backend-core/app/services/wbr/amazon_ads_auth.py` — Ads API OAuth equivalent
- `backend-core/app/routers/amazon_spapi_oauth.py` and `amazon_ads_oauth.py` — callback handlers
- `backend-core/app/services/reports/api_access.py` — token retrieval/storage logic
- `backend-core/app/services/wbr/nightly_sync.py` — sync orchestration
- `backend-core/app/services/wbr/amazon_ads_sync.py`, `windsor_business_sync.py` — report ingestion patterns
- `supabase/migrations/20260318123000_add_report_api_connections.sql` — current connection schema (reference, will be redesigned with encryption)

These files are point-in-time reference as of the agency-os branch on 2026-05-04. Verify against current code before relying on specific line numbers.

---

## Appendix B — What's validated today (Ecomlabs Tools MCP)

The single strongest piece of evidence that the platform thesis works is the Ecomlabs Tools MCP — already in production daily use inside the agency, with the following tool surface across five domains. This is not a separate long-term agency-os MCP; it is the validated prototype for MercatoPath's v1 MCP, generalized for org/workspace tenancy, self-serve onboarding, source freshness, and public SaaS permissions.

**Client resolution (`clients.py`):**
- `resolve_client` — free-text → canonical client lookup with capabilities, brands, team assignments, marketplace coverage

**Analyst / data drill-down (`analyst.py`):**
- `query_business_facts` — Sales & Traffic by ASIN, grouped by day / child_asin / row
- `query_ads_facts` — Amazon Ads campaign daily metrics (spend, sales, impressions, clicks, orders)
- `query_search_term_facts` — search-term performance with ad product / campaign / keyword filters
- `query_catalog_context` — catalog metadata for ASINs/SKUs
- `list_child_asins_for_row` — parent → active descendants resolver
- `get_asin_sales_window` — sales over a defined date window
- `get_sync_freshness_status` — latest available data dates per profile, with warnings

**Monthly P&L (`pnl.py`):**
- `list_monthly_pnl_profiles`
- `get_monthly_pnl_report` — full P&L envelope for a profile and month window
- `query_monthly_pnl_detail` — drill-down by line_item or month, scoped by section
- `get_monthly_pnl_email_brief`, `draft_monthly_pnl_email` — synthesized brief and draft

**Weekly Business Review (`wbr.py`):**
- `list_wbr_profiles`
- `get_wbr_summary` — current snapshot envelope (creates one if missing)
- `draft_wbr_email`

**Task management (`clickup.py`):**
- `list_clickup_tasks`, `get_clickup_task`, `update_clickup_task`, `prepare_clickup_task`, `create_clickup_task`, `resolve_team_member`

**What this validates:**
1. The MCP-as-strategic-surface thesis is not speculative. This tool set is in daily use by the agency for client work — drafting emails, drilling into anomalies, running ad-hoc analytics conversations through Claude.ai.
2. The data tools (`query_business_facts`, `query_ads_facts`, `query_search_term_facts`) work over real production warehouse tables with millions of rows across multiple clients and have proven query shapes.
3. The action tools (`draft_*_email`) demonstrate that LLM-via-MCP can produce client-quality deliverables, not just analytical answers.

**What is NOT yet validated and remains the v1 risk:**
- Self-serve onboarding for non-Ecomlabs sellers (the tool today assumes admin-mediated setup)
- Multi-tenant isolation at scale
- Public-app review approval and timing
- Pricing elasticity at the tier boundaries

---

## Appendix C — Day-to-day engineering guardrail workflow

Companion implementation handoff: `docs/mercatopath/coding_agent_onboarding.md`. Use that file with this brief when starting a fresh AI coding session for the MercatoPath repo.

When a future agent uses this brief to scaffold MercatoPath, it should turn the AI-maintainability principles into repo mechanics immediately. The goal is to make the right path the default path during ordinary coding, not a set of nice ideas people remember only during architecture reviews.

### Initial scaffold checklist

Create these before meaningful feature work starts:

- `AGENTS.md` — prescriptive coding contract, not a project tour.
- `docs/current/architecture-overview.md` — one-page repo map and domain boundaries.
- `docs/adr/` — permanent decision records.
- `docs/archive/` — home for superseded planning docs.
- `DEPRECATED.md` — registry of deprecated modules, tables, paths, replacements, and removal targets.
- `services/<domain>/` template with `repository.py`, `service.py`, `schema.py`, optional `mcp_tools.py`, and tests.
- MCP tool template with standard metadata, freshness/caveat output shape, and integration-test pattern.
- Fact-table / sync-source template with migration, canonical schema, repository, transform test, fixture, and coverage-ledger write.
- `.claude/` or equivalent repo-owned AI context with commands, code-review checklist, architecture overview, and glossary.
- `make verify` or `just verify` to run lint, typecheck, tests, migration checks, and file-size warnings.
- CI checks for import boundaries, tests, file-size warnings, deprecated-path edits, and stale planning docs.

### Daily coding loop

For every task:

1. **Identify the domain first.** Decide whether the work belongs in `sync`, `mcp`, `amazon_connections`, `pnl`, `alerts`, `workspaces`, etc. Read that domain's README and relevant ADRs before editing.
2. **Use a template or create one.** Common changes such as `add-mcp-tool`, `add-fact-table`, `add-api-route`, and `add-sync-source` should follow repeatable scaffolds. Do not hand-roll new shapes because they feel faster.
3. **Respect import boundaries.** Routers call services. MCP tools call services. Services orchestrate repositories and external clients. Repositories own DB access. External API clients do not write facts directly.
4. **Add tests with the change.** Unit-test transforms and business logic. Add integration tests for DB/API/MCP behavior. Add or update sanitized fixtures for Amazon payload parsing.
5. **Run verification locally.** `make verify` / `just verify` should be the normal stop point before calling work done.
6. **Update contracts when behavior changes.** If a change alters schema, tenancy, sync semantics, API shape, MCP tool behavior, or product architecture, update the relevant schema, README, ADR, or deprecation registry.
7. **Pause when the change sprawls.** If a task wants to touch four or more domains, extend a 600+ line file, add a table plus worker plus MCP tool, or modify a deprecated path, write a mini plan or ADR first.

### Pull request / review checklist

Every meaningful change should answer:

- What domain changed?
- Which README, ADR, or template guided the implementation?
- What tests or fixtures were added?
- Did this touch a deprecated path?
- Did this add or change a public contract: DB schema, API response, MCP tool, sync dataset, alert payload, or billing behavior?
- Did this create or extend a large file? If yes, why is that still the right shape?

### AI coder prompt contract

When asking an AI coding agent to work in MercatoPath, prepend something like:

> Follow `AGENTS.md`. Identify the domain first, read its README and relevant ADRs, use existing templates, keep changes scoped, do not extend files over 600 lines without calling it out, do not edit deprecated paths without asking, add tests/fixtures, update contracts if behavior changes, and run `make verify` before finalizing.

### When-in-doubt rules

- If something might be deprecated, ask before extending it.
- If ownership is unclear, propose a split instead of adding to a large existing file.
- If there are multiple patterns, copy the most recent equivalent pattern unless an ADR says otherwise.
- If the feature needs a new architectural rule, write an ADR instead of burying the decision in code.
- If the implementation cannot be tested cleanly, stop and improve the seam rather than merging untested glue.
