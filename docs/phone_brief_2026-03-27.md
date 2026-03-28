# Agency OS Phone Brief

_Date: 2026-03-27 (ET)_

This is a compact briefing file for discussing the project with another LLM
that does **not** have repo or GitHub access.

## One-line summary

Agency OS is an internal operating system for an Amazon/e-commerce marketing
agency. It combines reporting, analysis, workflow tooling, and LLM-assisted
operations into one authenticated app, while gradually replacing manual
exports and ad-hoc spreadsheets with native data pipelines and safer internal
workflows.

## Stack

1. Frontend: Next.js 16 + React 19 + Tailwind + TypeScript
2. Backend: FastAPI + Python
3. Database/Auth: Supabase
4. Deploy: Render
5. Internal AI surfaces:
   - Claude remote MCP connector
   - web-app AI workflows
   - internal tool-specific LLM helpers

## Main shipped product areas

1. N-Gram Processor
   - classic route: `/ngram`
   - current legacy workflow: upload search-term file, get workbook, review,
     re-upload, get cleaned workbook for negatives workflow
2. N-Gram 2.0
   - new route: `/ngram-2`
   - separate experimental/native replacement path
3. N-PAT
   - ASIN-focused inverse/complement to N-Gram
4. WBR
   - weekly business review system by client + marketplace profile
5. Monthly P&L
   - month-level profitability reporting from Amazon transaction imports
6. AdScope
   - Amazon Ads audit workspace
7. Scribe
   - listing-copy generation workflow
8. Root Keywords
   - hierarchical campaign rollup workbook
9. Command Center
   - internal admin/org structure layer
10. Debrief
   - meeting notes to tasks workflow

## Claude / MCP / tools context

Agency OS has a real Claude-facing tool surface, not just app pages.

### What exists today

There is a private Claude connector called `Agency OS` that authenticates
through Supabase OAuth and exposes MCP-style backend tools.

Current live Claude tool families include:

1. WBR tools
   - client resolution
   - WBR profile discovery
   - summary retrieval
   - WBR email drafting
2. Monthly P&L tools
   - profile discovery
   - report retrieval
   - structured P&L brief generation
   - persisted P&L email drafting
3. ClickUp tools
   - list tasks
   - inspect mapped tasks
   - resolve assignees
   - prepare/create/update tasks
4. Analyst-query tools
   - direct reporting queries and drill-down helpers

### Important design principle

This is **not** “Claude can do anything in the codebase.”

It is a narrow, curated tool surface:

1. shared `resolve_client` entrypoint
2. safe read-only reporting tools first
3. mutating tools only where needed and usually with approval
4. small Claude Project file bundle rather than dumping the whole repo into
   Claude

### What is customized here

The Claude tool surface is customized to the agency’s operating model:

1. client/brand/team routing comes from Agency OS data
2. tool outputs are shaped around the agency’s reporting habits
3. WBR and P&L drafting flows reflect real operator deliverables
4. ClickUp task routing is constrained to mapped internal destinations

So this is not a generic “chat with your database” system. It is an
agency-specific operator surface.

## WBR: what it is and how customized it is

### What WBR is

WBR is a marketplace-specific weekly business review system.

One WBR profile represents one client + marketplace combination, with:

1. a row tree
2. source mappings
3. sync settings
4. reporting cadence assumptions

Data sources currently include:

1. Windsor business data
2. Amazon Ads campaign data
3. inventory / returns support data
4. downstream search-term facts

### How customized WBR is

WBR is **highly customized** to how this agency runs Amazon accounts.

Examples:

1. Custom row tree
   - not a generic BI dashboard
   - rows are manually structured the way the agency wants to review a business
2. Custom mapping layer
   - ASIN-to-row mapping
   - campaign-to-row mapping
   - exclusions
3. Custom reporting semantics
   - weekly structure
   - sectioned report layout
   - email-draft workflows
4. Operational sync model
   - nightly syncs
   - rolling rewrite windows
   - snapshot refresh behavior

### Generic vs custom

Generic platform pieces:

1. profiles
2. sync runs
3. fact tables
4. report snapshots

Agency-specific pieces:

1. row-tree structure
2. mapping/exclusion rules
3. section layout and presentation
4. how WBR summaries/emails are written

So WBR is not a reusable commodity reporting app. It is a codification of how
this team actually reviews Amazon businesses.

## Monthly P&L: what it is and how customized it is

### What Monthly P&L is

Monthly P&L is a month-level profitability/reporting system built primarily
from Amazon transaction imports today, with a longer-term direction toward
shared Seller API access.

It includes:

1. month import handling
2. transaction mapping rules
3. SKU-based COGS support
4. payout rows / transfer handling
5. YoY mode
6. Claude-facing brief + draft tools

### How customized it is

Monthly P&L is **moderately to highly customized**.

It is more generic than WBR structurally, but still shaped by agency-specific
Amazon finance operations.

Customized areas:

1. Mapping rules
   - how Amazon transaction lines map into internal P&L buckets
2. SKU-based COGS
   - explicit internal cost model
3. Payout / transfer handling
   - agency-specific reporting expectations
4. Reporting outputs
   - how the team wants to read and explain P&L performance

Less customized / more reusable parts:

1. import-month model
2. ledger-entry storage
3. month-bucket totals
4. YoY comparison layer

### Bottom line

WBR is more tightly coupled to “how this agency runs Amazon accounts.”

Monthly P&L is still tailored, but parts of it are closer to a reusable
commerce-accounting/reporting foundation.

## ClickUp: what it is and how customized it is

### What ClickUp support is

Agency OS has a Claude-facing ClickUp tool surface rather than a large
full-featured ClickUp UI replacement.

Current capabilities include:

1. listing mapped tasks
2. inspecting mapped tasks
3. resolving assignees
4. preparing task payloads
5. creating tasks
6. updating tasks

### How customized it is

This is **moderately customized** to the agency.

Customized areas:

1. task access is scoped to mapped Agency OS destinations
2. client/brand resolution feeds task routing
3. assignee resolution follows internal team-member mapping
4. Claude task flows are designed around agency backlog operations, not
   generic project management

Not customized in the same way as WBR:

1. it is not a fully bespoke task system
2. ClickUp remains the actual task platform
3. Agency OS acts as a constrained operator layer on top

### Bottom line

ClickUp support is not the core product, but it is an important internal ops
bridge. It is narrower and safer than WBR/P&L, and intentionally avoids
turning Agency OS into a full project-management clone.

## Legacy N-Gram: what it is and why it matters

### What legacy N-Gram does

Legacy `/ngram` is one of the most operationally important existing tools.

Current flow:

1. user uploads a search-term report, historically often from Pacvue
2. Agency OS generates an Excel workbook organized by campaign with
   monograms/bigrams/trigrams and raw search-term tables
3. analyst manually reviews/fills the workbook
4. analyst optionally gets manager review
5. analyst uploads the filled workbook back into Step 2
6. Agency OS returns a cleaned/export-oriented workbook for the negatives flow

### Why it matters

This tool is deeply tied to how the team actually works today.

Important point:

1. the value is not just the gram math
2. the workbook itself is a process artifact used for review, collaboration,
   and publishing preparation

### How customized it is

Legacy N-Gram is **highly customized** to agency operations.

Examples:

1. workbook shape and formulas
2. campaign-by-campaign review behavior
3. naming-convention-driven exclusions
4. compatibility with downstream manual publishing habits

This is why N-Gram 2.0 is being built as a compatibility-first replacement,
not as a totally new analyst experience.

## N-PAT: what it is and how it fits

### What N-PAT is

N-PAT is an ASIN-focused companion/inverse workflow to N-Gram.

Where N-Gram is query/negative-oriented, N-PAT is more ASIN-focused and is
used for a different review logic around unwanted ASIN-level traffic.

### Why it matters

It shows that Agency OS already has multiple tightly tailored Amazon ops tools,
not just generic reporting pages.

### How customized it is

N-PAT is also **highly customized** to agency workflow.

Examples:

1. it is built around a very specific operational review pattern
2. it complements N-Gram rather than replacing it
3. enrichment assumptions and output expectations are tuned to internal ad
   management work

So if another LLM is evaluating the project, it should understand that N-Gram
and N-PAT are operator tools, not generic analytics widgets.

## Scribe: what it is and how customized it is

### What Scribe is

Scribe is the listing-copy workflow in Agency OS.

It is used to generate and refine Amazon listing content, with staged flows
for:

1. SKU/project setup
2. topic generation/selection
3. copy generation
4. CSV export

### How customized it is

Scribe is **moderately to highly customized**.

Customized areas:

1. the staged workflow reflects how the team wants to create listing content
2. title/copy structure can be constrained by internal rules
3. exports are shaped for downstream operational use
4. dirty-state/regeneration behavior reflects real content workflow needs

Less customized / more reusable parts:

1. generic LLM content generation scaffolding
2. SKU/project storage model
3. CSV import/export mechanics

### Bottom line

Scribe is more productized and workflow-driven than a generic “ask AI for copy”
tool, but it is less deeply tied to Amazon account operations than WBR or
N-Gram.

## Search term automation and N-Gram context

This is the current major active product thread.

### What is already true

1. Sponsored Products (`SP`) native search-term ingestion is validated
2. native SP data can now generate a workbook from `/ngram-2`
3. that workbook has been uploaded into Step 2 of the **existing** `/ngram`
   flow and was accepted successfully

This means:

1. the Pacvue export is no longer required for Step 1 of the current SP
   N-Gram workflow
2. the downstream team process can stay familiar for now

### SB and SD

1. Sponsored Brands (`SB`) support exists in progress but is **not yet
   validated**
2. Sponsored Display (`SD`) is not implemented as a native N-Gram data source
   yet

### Current SB issue

SB has two distinct concerns:

1. persistence/finalization behavior had a stale-worker confusion earlier in
   the day
2. more importantly, there is still a likely Amazon-side parity gap:
   - native `sbSearchTerm` API output is missing at least one campaign that
     appears in the Amazon console/export surface

Known missing campaign family:

1. `Screen Shine - Pro | Brand | SB | PC-Store | MKW | Br.M | Mix. | Def`

Current best interpretation:

1. native SB storage is now behaving again after `worker-sync` redeploy
2. but native SB API/export parity is still not proven

## N-Gram 2.0 product framing

The main product idea is **not** “build a better search-term dashboard.”

The current strategy is:

1. keep the old N-Gram workflow recognizable
2. replace manual Pacvue export/upload with native Agency OS data selection
3. keep workbook generation first-class
4. later add optional AI assistance beside the manual path

So the intended value proposition is:

1. less manual prep
2. same familiar workbook flow
3. side-by-side trust-building rather than forcing a new workflow

## Current live status snapshot

As of March 27, 2026:

1. Claude/MCP reporting surface is live
2. WBR is live and heavily customized
3. Monthly P&L is live and reasonably mature
4. SP native search-term ingestion is validated
5. N-Gram 2.0 Step 1 replacement is proven for SP
6. SB is still under validation and not yet trustworthy enough to treat as
   complete

## What is most custom to the agency

If someone asks “what here is really bespoke vs generic?”, the answer is:

### Most bespoke

1. WBR row-tree + mapping model
2. reporting section semantics
3. Claude tool selection and outputs
4. N-Gram workflow assumptions and workbook compatibility needs
5. campaign naming conventions / exclusions / review habits
6. N-PAT review assumptions and outputs

### Mixed bespoke + reusable

1. Monthly P&L
2. search-term ingestion foundation
3. analyst query tooling
4. command-center/client-brand-team model
5. Scribe
6. ClickUp operator layer

### More reusable platform infrastructure

1. auth
2. sync-run logging
3. fact-table patterns
4. report snapshots
5. MCP/OAuth connector architecture

## Suggested prompt to another LLM

Use something like this:

```text
I’m working on an internal Amazon agency platform called Agency OS.

It has:
- a Next.js frontend
- a FastAPI backend
- Supabase auth/db
- Render deploys
- a Claude remote connector with curated MCP-style tools

The project combines:
- WBR reporting
- Monthly P&L
- N-Gram / search-term workflows
- ClickUp task tooling

Important context:
- WBR is highly customized to how the agency reviews Amazon accounts
- Monthly P&L is also tailored, but structurally more reusable than WBR
- SP native search-term ingestion is validated
- SB is partially working but still not fully validated because the native
  API appears to miss at least one campaign that Amazon exports show
- N-Gram 2.0 now works as a native Step 1 replacement for SP and can produce
  a workbook compatible with the existing downstream N-Gram workflow

I want advice on:
[insert your real question here]
```

## Best companion files

If you want to send a small file bundle with this brief, use:

1. [AGENTS.md](/Users/jeff/code/agency-os/AGENTS.md)
2. [PROJECT_STATUS.md](/Users/jeff/code/agency-os/PROJECT_STATUS.md)
3. [current_handoffs.md](/Users/jeff/code/agency-os/docs/current_handoffs.md)
4. [ngram_native_replacement_plan.md](/Users/jeff/code/agency-os/docs/ngram_native_replacement_plan.md)
5. [search_term_automation_plan.md](/Users/jeff/code/agency-os/docs/search_term_automation_plan.md)
6. [claude_project/README.md](/Users/jeff/code/agency-os/docs/claude_project/README.md)
7. [monthly_pnl_handoff.md](/Users/jeff/code/agency-os/docs/monthly_pnl_handoff.md)
8. [wbr_v2_schema_plan.md](/Users/jeff/code/agency-os/docs/wbr_v2_schema_plan.md)
