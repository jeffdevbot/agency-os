# Claude.ai as a Primary Surface for Agency OS

_Drafted: 2026-03-20 (ET)_

## Summary

Agency OS should continue to use The Claw in Slack because it already exists,
works, and fits lightweight operational use cases well.

However, there is now a strong argument for making **Claude.ai on the Team
plan the primary high-capability surface** for power users and, over time, for
the broader team.

The core idea is:

1. keep Agency OS as the source of truth for internal tools, data, auth, and business logic
2. expose those capabilities through one private `agency-os` integration
3. let Claude.ai provide the richer working environment:
   - uploaded files
   - spreadsheets
   - screenshots/images
   - long-context reasoning
   - artifact generation
   - stronger writing / analytical workflows

This is not an argument to replace The Claw immediately.

It is an argument to treat:

1. **The Claw in Slack** as the operational copilot
2. **Claude.ai + Agency OS integration** as the analyst / strategist / deep-work surface

## Why this idea is compelling now

The recent forecasting workflow is the clearest proof point.

In one Claude.ai web session, it was possible to combine:

1. Business Reports CSV exports from Seller Central
2. WBR Excel export
3. a screenshot from a client email describing Hot Sale timing in Mexico
4. a child ASIN / SKU Excel file
5. general reasoning, synthesis, and deliverable creation

Claude handled:

1. mixed file types
2. image understanding / OCR-like extraction from screenshots
3. spreadsheet and CSV reasoning
4. context synthesis across structured and unstructured inputs
5. creation of a polished client-ready Excel output

This is a different class of work than a Slack chatbot is naturally suited for.

Trying to force all of this into Slack would be the wrong product shape.

## Why Claude.ai may be the better primary surface for many high-value workflows

Claude.ai on the web has important product advantages that Agency OS should
leverage rather than recreate.

### 1. Rich multimodal workspace

Claude web is already good at working with:

1. CSV files
2. Excel files
3. PDFs
4. screenshots / images
5. long running sessions with lots of context

That makes it a better fit for:

1. forecasting
2. strategic analysis
3. financial investigation
4. report synthesis
5. client-ready artifact generation

### 2. Long context is materially more useful now

Anthropic announced that **1M context is generally available** for Opus 4.6 and
Sonnet 4.6, with standard pricing across the full window and expanded media
limits up to 600 images or PDF pages.

Source:

1. https://claude.com/blog/1m-context-ga

Relevant implications for Agency OS:

1. very large forecasting / planning sessions become more realistic
2. fewer context resets / compactions
3. more source material can stay in one working session
4. cross-file reasoning becomes much easier

This is especially relevant for:

1. large spreadsheets
2. long email threads
3. client strategy documents
4. multi-marketplace history
5. long iterative analysis sessions

### 3. Better fit for analyst-style work than Slack

Slack is good for quick operational requests.

Claude web is better for:

1. exploratory analysis
2. multi-step document-centric work
3. revising deliverables over many turns
4. writing polished client-facing outputs
5. combining internal tools with uploaded external context

## Why keep The Claw in Slack anyway

There is still value in keeping The Claw alive in Slack.

Slack remains useful for:

1. quick ops requests
2. fast WBR lookups
3. quick WBR email drafts
4. bounded internal workflows
5. low-friction operational usage inside team communication

So the practical position is:

1. do not throw away The Claw
2. do not make Slack the only serious AI surface
3. add Claude.ai as the higher-capability primary surface for super users

## Recommended surface split

### Slack / The Claw

Best for:

1. `How did Basari do?`
2. `Draft the weekly email for Whoosh`
3. quick follow-up revisions
4. short operational lookups
5. team chat-native usage

### Claude.ai web + Agency OS integration

Best for:

1. forecasting
2. data synthesis across files and screenshots
3. planning decks / email narratives / strategy memos
4. spreadsheet-heavy investigation
5. mixed internal + uploaded external context

## What the integration should look like

The right shape is **one private Agency OS integration** with many tools inside
it.

Not:

1. one connector per tool
2. one bot per workflow
3. a public marketplace app

Instead:

1. one private `agency-os` integration
2. many internal tools exposed inside it
3. org-controlled access
4. per-user authentication where required

This should likely be implemented as an **Agency OS MCP server** or equivalent
private integration layer that wraps existing backend capabilities.

## How Claude Team would actually work

Based on Anthropic's current documentation, the practical operating model is:

1. Ecomlabs would use **Claude Team** (or Enterprise)
2. an owner or primary owner would enable the private integration at the org level
3. the integration would point at the hosted `agency-os` remote MCP server
4. individual team members would still authenticate themselves to the integration
5. Claude Projects would carry the standing instructions / knowledge for how to use the tools

This is important because the setup is not "one hidden global system prompt and all users automatically inherit everything."

The working model is closer to:

1. **org-level integration availability**
2. **user-level authentication**
3. **project-level instructions and knowledge**

### Relevant Anthropic docs

1. Custom integrations via remote MCP:
   - https://support.anthropic.com/en/articles/11175166-about-custom-integrations-using-remote-mcp
   - https://support.anthropic.com/en/articles/11503834-building-custom-integrations-via-remote-mcp-servers
2. Setting up Claude integrations:
   - https://support.anthropic.com/en/articles/10168395-setting-up-claude-integrations
3. Projects and project instructions:
   - https://support.anthropic.com/en/articles/9519177-how-can-i-create-and-manage-projects
   - https://support.anthropic.com/en/articles/9519189-project-visibility-and-sharing
   - https://support.anthropic.com/en/articles/10185728-understanding-claude-s-personalization-features

## Team-plan mechanics and implications

### Org-level enablement

On Claude Team / Enterprise, an owner can enable organization integrations and
add a custom remote MCP integration URL.

That means:

1. the integration can be made available to the team centrally
2. users do not each need to manually create their own custom integration definition from scratch
3. Ecomlabs can treat `agency-os` as one managed internal integration

### Individual user authentication

Even when the integration is configured at the org level, users still
authenticate individually to it.

That is actually desirable for Agency OS because it means:

1. Claude should only see tools/data the specific user is allowed to access
2. permissions can remain user-scoped
3. auditing can remain user-scoped
4. sensitive client access can be enforced server-side by Agency OS

This is the key answer to the common question:

**Will every user have to add the integration manually?**

Not exactly.

More accurately:

1. the org owner can make the integration available
2. each user still needs to connect/authenticate to it personally

So the labor is mostly:

1. one-time org setup by an owner
2. per-user connection/auth flow

not:

1. every user hand-defining their own entire connector config

### Projects are the closest thing to a "team system prompt"

Claude.ai does not give the same kind of fully hidden, app-controlled global
system prompt that an internally owned product surface can enforce.

The closest practical equivalent is:

1. **Project instructions**
2. **Project knowledge**
3. **tool descriptions and schemas**

So the expected setup is:

1. create one or more shared Claude Projects for internal workflows
2. put strong Agency OS usage instructions into the Project instructions
3. include relevant knowledge docs and runbooks in the Project
4. rely on MCP tool metadata to teach Claude what tools exist and when to use them

### Shared Project permissions

Projects can be shared with different permission levels.

The practical model for Ecomlabs would likely be:

1. a small number of admin-owned canonical projects
2. most users get **Can use**
3. a smaller number of trusted builders get **Can edit**

This matters because it gives you a real way to preserve:

1. standard instructions
2. standard knowledge context
3. standard workflow expectations

without letting everyone casually rewrite them.

## How to think about the "system prompt" question

### What Claude.ai likely can support well

Use a layered instruction model:

1. **tool descriptions** define what each Agency OS capability does
2. **Project instructions** define how Claude should behave for agency workflows
3. **Project knowledge** provides background docs, vocabulary, client/reporting conventions, and working rules

That is likely enough for strong behavior if the tools are designed well.

### What Claude.ai likely cannot support as cleanly as an owned app

Do not assume there is one perfect global hidden instruction layer that:

1. all users inherit automatically
2. admins fully control across every chat
3. behaves exactly like an internal app-owned system prompt

So the realistic position is:

1. yes, strong guidance is possible
2. no, it is not identical to owning the full runtime

## Recommended instruction strategy for Agency OS in Claude

The right approach is probably:

### 1. Build one admin-owned canonical project first

For example:

1. `Agency OS Analyst Workspace`

Use it to encode:

1. who Claude is for the team
2. what Agency OS tools exist
3. when to use internal data vs uploaded files
4. what guardrails matter
5. how to present outputs

### 2. Put durable operating guidance in Project instructions

For example:

1. resolve client/entity names before using report tools
2. prefer Agency OS internal data when available over manually re-deriving it
3. use WBR and P&L tools as source-of-truth inputs
4. do not invent metrics or claim data access you do not have
5. when users upload files, combine them with Agency OS tools rather than ignoring either source

### 3. Put reference materials in Project knowledge

Candidates:

1. WBR data model overview
2. Monthly P&L row and bucket definitions
3. client/brand naming conventions
4. internal glossary
5. Agency OS usage notes

### 4. Keep tool descriptions extremely explicit

Claude will use the MCP tool metadata directly, so each tool should clearly say:

1. what it does
2. when to use it
3. what inputs it expects
4. what it returns
5. whether it is read-only or mutating

## Admin control model that likely makes sense

For Ecomlabs, the practical admin model is:

1. owner enables the `agency-os` integration for the Team org
2. owner creates one or more canonical shared Projects
3. super users test first
4. users authenticate individually to the integration
5. Agency OS enforces user/client permissions server-side
6. the shared Project carries the standard instructions

This gives meaningful control without pretending Claude Team behaves exactly
like a fully custom internal chat app.

## Private, not public

This should be treated as an internal connector:

1. private to Ecomlabs
2. not published in a public Claude directory
3. authenticated for internal team members
4. scoped to internal data and client permissions

That matches the actual nature of the capabilities:

1. client reporting data
2. internal workflows
3. proprietary logic
4. private operational context

## Team rollout model

Recommended rollout:

### Phase 1: super users

Start with:

1. Jeff
2. partner / second power user

Goal:

1. validate the real workflows
2. determine which internal tools matter most
3. refine guardrails and permissions
4. learn which tasks should remain Slack-first

### Phase 2: selected internal team members

Expand to a limited set of:

1. account managers
2. analysts
3. operators who already use WBR / P&L heavily

Goal:

1. prove broad internal usability
2. find permission and UX gaps
3. test whether Claude web really becomes the preferred surface

### Phase 3: wider team usage

If the model works:

1. make Claude Team + `agency-os` integration available more broadly
2. keep high-risk tools gated
3. preserve operational / auditing controls in Agency OS

## Recommended Team seat strategy

The likely practical setup is:

1. Jeff on a **premium Team seat**
2. possibly one additional premium seat for the second power user
3. most of the broader team on **standard Team seats**

Why this split makes sense:

1. the admin / builder / heaviest user is the one most likely to need:
   - Claude Code
   - more generous usage
   - longer coding and architecture sessions
2. most other team members will likely use Claude mainly for:
   - web chat
   - shared Projects
   - Agency OS integration usage
   - analysis and writing workflows
3. that broader group probably does not need premium seats on day one

Recommended default:

1. premium for the admin / builder
2. standard seats for the wider team
3. add more premium seats later only if real usage justifies it

## What Claude would be good at natively, and what Agency OS should add

Claude web should continue to do the things it is already excellent at:

1. handling uploaded files
2. reading screenshots/images
3. long-context reasoning
4. artifact creation
5. strong drafting and synthesis

Agency OS should provide:

1. internal data access
2. client resolution
3. structured report retrieval
4. internal business logic
5. safe access control
6. organization-specific skills and tools

In other words:

1. Claude provides the **workspace intelligence**
2. Agency OS provides the **business-specific capabilities**

## Current The Claw skill inventory

The current The Claw skill set in the repo is:

1. `entity_resolver`
2. `task_confirmation_to_create`
3. `task_extraction`
4. `wbr_summary`
5. `wbr_weekly_email_draft`

Current skill contracts live under:

1. `backend-core/app/services/theclaw/skills/core/entity_resolver/SKILL.md`
2. `backend-core/app/services/theclaw/skills/core/task_confirmation_to_create/SKILL.md`
3. `backend-core/app/services/theclaw/skills/core/task_extraction/SKILL.md`
4. `backend-core/app/services/theclaw/skills/wbr/wbr_summary/SKILL.md`
5. `backend-core/app/services/theclaw/skills/wbr/wbr_weekly_email_draft/SKILL.md`

Important reality:

1. all five skill contracts exist
2. the currently implemented tool-backed, production-useful Slack skills are the two WBR skills
3. the core skills are useful behavioral contracts, but not all of them are yet backed by a mature Claude-web-ready tool layer

## Current The Claw tool inventory

Today, the live tool registry in
`backend-core/app/services/theclaw/skill_tools.py` exposes:

1. `lookup_wbr`
2. `list_wbr_profiles`
3. `draft_wbr_email`

### Tool: `lookup_wbr`

Purpose:

1. retrieve a WBR digest for a concrete client + marketplace

Current usage:

1. powers `wbr_summary`

How Claude would use it:

1. user asks for a WBR summary
2. Claude resolves the client and marketplace
3. Claude calls `lookup_wbr`
4. Claude summarizes the returned digest in its own preferred style

### Tool: `list_wbr_profiles`

Purpose:

1. list available WBR client / marketplace combinations

Current usage:

1. discovery step for fuzzy matching like `Basari` -> `Basari World MX`

How Claude would use it:

1. user gives a partial or ambiguous client name
2. Claude calls `list_wbr_profiles`
3. Claude chooses the best canonical match
4. Claude continues with `lookup_wbr` or `draft_wbr_email`

### Tool: `draft_wbr_email`

Purpose:

1. generate one multi-marketplace weekly email draft for a client

Current usage:

1. powers `wbr_weekly_email_draft`

How Claude would use it:

1. user asks for a client update email
2. Claude calls `draft_wbr_email`
3. Claude presents or revises the returned draft
4. Claude can optionally blend in additional uploaded context if the workflow allows it

## Example of future Agency OS integration tools

A realistic first-pass internal tool belt could include:

1. `resolve_client`
2. `list_wbr_profiles`
3. `get_wbr_summary`
4. `draft_wbr_email`
5. `get_monthly_pnl_report`
6. `get_monthly_pnl_import_status`
7. `list_child_asins`
8. `get_client_brand_catalog`
9. `query_adscope_view`
10. `get_reporting_connections`

Possible later tools:

1. `get_historical_business_report_data`
2. `get_forecast_seed_dataset`
3. `export_forecast_workbook_seed`
4. `get_wbr_snapshot_history`
5. `compare_monthly_pnl_vs_windsor`

## How Claude would use Agency OS skills and tools

Claude would not need to replicate The Claw’s current Slack runtime exactly.

Instead, the likely model would be:

1. Claude receives user request + uploaded context
2. Claude decides when to call Agency OS tools
3. Agency OS tools return structured data
4. Claude does the synthesis, reasoning, drafting, and artifact generation

That means Claude would absorb much of the current router / formatter work.

The most important thing Agency OS needs to provide is:

1. accurate tool contracts
2. safe auth
3. good data shaping
4. clear permission boundaries

## Why this could be better than making Slack more sophisticated

Building a richer Slack bot to match Claude web would likely mean recreating:

1. robust file upload handling
2. spreadsheet-aware workflows
3. screenshot/image reasoning workflows
4. richer artifact creation paths
5. a much more complex conversational workbench

That is a lot of product work to rebuild capabilities Claude web already has.

The smarter approach is probably:

1. let Claude web stay the rich multimodal workspace
2. let Agency OS provide the internal intelligence and data access layer

## Main risks and constraints

### 1. Governance and permissions

Need clear answers for:

1. which users can access which clients
2. which tools are read-only vs mutating
3. how access is logged and audited

### 2. Prompt / instruction control is weaker than in an app you fully own

Claude Projects and tool descriptions can provide strong guidance, but this is
not the same as fully owning the end-user runtime and hidden system prompt.

### 3. Tool/result shaping matters a lot

If internal tools return giant raw payloads, Claude will still perform worse.

The integration should expose:

1. compact
2. structured
3. analyst-friendly
4. high-signal

responses.

### 4. Not every workflow belongs in Claude web

Some tasks may still be better as:

1. Slack requests
2. internal admin UI workflows
3. deterministic background jobs

## Recommended path

### Recommendation

Agency OS should explore **Claude.ai Team as the primary high-capability
surface**, while retaining The Claw in Slack as the lightweight operational
surface.

### Practical next step

Build a plan for a private `agency-os` integration that starts with a small,
high-value tool set.

Recommended first tool set:

1. `list_wbr_profiles`
2. `get_wbr_summary`
3. `draft_wbr_email`
4. `get_monthly_pnl_report`
5. `list_child_asins`
6. `query_adscope_view`

### Suggested rollout order

1. private super-user pilot
2. validate real workflows like forecasting, WBR drafting, P&L diagnosis
3. add access controls and logging hardening
4. expand to the broader team

## Bottom line

The key insight is not that The Claw was a mistake.

The key insight is:

1. The Claw proved the value of Agency OS tools and internal data access
2. Claude web may be the better surface for higher-value analytical work
3. the right long-term move may be to connect Claude to Agency OS, not to make Slack do everything
