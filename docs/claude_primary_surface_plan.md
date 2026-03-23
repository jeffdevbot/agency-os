# LLM-Native Primary Surface for Agency OS

_Drafted: 2026-03-20 (ET)_

## Status update — 2026-03-21 (ET)

The Jeff-only Claude Pro pilot described in this document is now live.

Current confirmed state:

1. the private `Agency OS` remote MCP connector is connected in Claude Pro
2. Supabase OAuth is working for the Claude auth flow
3. the first WBR tool belt is live:
   - `resolve_client`
   - `list_wbr_profiles`
   - `get_wbr_summary`
   - `draft_wbr_email`
4. live smoke tests succeeded for:
   - client resolution
   - marketplace lookup
   - WBR summary retrieval
   - persisted WBR email draft creation
5. a compact Claude Project setup bundle now exists at `docs/claude_project/`

So this document should now be read as:

1. the strategic rationale for the surface
2. the operating model for the next rollout phase
3. context for moving from Jeff-only Pro usage toward a broader Claude Team setup later

## Pilot outcome — 2026-03-21 (ET)

The live pilot materially strengthens the case for Claude as the primary
high-capability surface.

Observed result:

1. for real WBR questions, Claude is already producing a better user
   experience than The Claw with little or no prompt tuning
2. Claude answers with lower interaction cost, better prioritization, and
   better business-language synthesis
3. The Claw remains more explicit and rigid about disambiguation, which can be
   useful for bounded operational workflows but is noticeably worse for
   high-capability analyst-style usage

Practical implication:

1. Claude should now be treated as the leading candidate for the primary
   analyst surface, not just a speculative option
2. The Claw should continue to be tested, but it should not receive major
   optimization priority while Claude continues to outperform it on real
   analyst workflows
3. Slack still matters, but primarily for lightweight operational requests and
   chat-native usage rather than as the main high-capability surface

## Why Claude is outperforming The Claw so far

The current gap should not be explained as "Claude is just magic" or "The
Claw is bad."

The better explanation is that Claude currently has a stronger full stack for
this class of work:

1. a stronger general-purpose model and response composer
2. a richer web working environment with files, screenshots, long context, and
   iterative revision
3. a narrower and cleaner MCP tool surface for WBR work
4. tighter project instructions focused on answer-first analyst behavior
5. less visible orchestration overhead than the current Slack skill-routing
   path

The Claw is not simply "the same thing in Slack."

In its current shape, The Claw still carries product choices that are helpful
for bounded operational workflows but harmful for analyst-style usage:

1. it uses an explicit skill-routing runtime before the real answer path
2. it tends to expose clarification and resolution scaffolding to the user
3. it is optimized to avoid wrong answers under ambiguity, even when the user
   mainly wants the most likely correct business answer quickly
4. it lives in a chat surface that is materially worse for file-heavy and
   synthesis-heavy work

So the pilot result should be interpreted as:

1. model quality matters
2. runtime and surface design matter at least as much
3. even a stronger model inside The Claw would likely not fully close the gap
   unless the Slack runtime became less rigid and less clarification-heavy

This is why the current recommendation is to keep testing The Claw, but not to
prioritize major optimization work on it unless evidence shows that a narrower
Slack-native role has a stronger product fit than Claude for a specific
workflow.

## Summary

Agency OS should continue to keep The Claw in Slack available for lightweight
operational use cases.

However, the live pilot now shows that an **LLM-native web surface** should be
treated as the primary high-capability surface for power users and, over time,
for the broader team.

**Claude.ai is the best Phase 1 candidate**, but the architecture should not
hard-code Claude as the only possible "head."

Operationally, the best rollout path is:

1. **pilot on Claude Pro first** for Jeff as the initial super user
2. prove the private `agency-os` integration and real workflows
3. then move to **Claude Team** for broader team rollout and admin-managed Projects

The core idea is:

1. keep Agency OS as the source of truth for internal tools, data, auth, and business logic
2. expose those capabilities through one private `agency-os` integration
3. let the surface model provide the richer working environment:
   - uploaded files
   - spreadsheets
   - screenshots/images
   - long-context reasoning
   - artifact generation
   - stronger writing / analytical workflows

This is not an argument to delete The Claw immediately.

It is an argument to treat:

1. **Claude.ai + Agency OS integration** as the first analyst / strategist /
   deep-work surface
2. **The Claw in Slack** as the lightweight operational copilot that remains in
   test mode unless it proves a stronger product fit than Claude for a given
   workflow

Longer term, the "head" should be replaceable:

1. Claude.ai first
2. ChatGPT if/when it offers a better team fit
3. Gemini or another workspace if it reaches similar tool and project maturity

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

## Why Claude.ai is the best first head

Claude.ai on the web has important product advantages that Agency OS should
leverage rather than recreate. It is the strongest current candidate for the
first LLM-native primary surface.

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

There is still value in keeping The Claw alive in Slack, but the pilot changes
how aggressively it should be optimized.

Slack remains useful for:

1. quick ops requests
2. fast WBR lookups
3. quick WBR email drafts
4. bounded internal workflows
5. low-friction operational usage inside team communication

So the practical position is:

1. do not throw away The Claw yet
2. do not make Slack the only serious AI surface
3. treat Claude.ai as the default higher-capability primary surface
4. continue testing The Claw, but do not prioritize major optimization work on
   it while Claude continues to perform better on real analyst workflows

## Recommended surface split

### Slack / The Claw

Best for:

1. quick operational lookups
2. bounded requests where explicit clarification is preferable to inference
3. short chat-native usage inside team communication
4. lightweight follow-up requests when Slack is the right place to work
5. continued product testing, not primary optimization focus

### Claude.ai web + Agency OS integration

Best for:

1. forecasting
2. data synthesis across files and screenshots
3. planning decks / email narratives / strategy memos
4. spreadsheet-heavy investigation
5. mixed internal + uploaded external context
6. WBR questions where the user wants the answer, not a long clarification flow

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

The important architectural point is that the MCP/tool layer should outlive any
single web chat surface. Claude is the first head, not the permanent one.

## Head-swappable architecture

Agency OS should treat the web-chat surface as a swappable "head" on top of a
stable internal tool and data layer.

### Stable layers

These should remain the same regardless of whether the team prefers Claude,
ChatGPT, or another compatible surface later:

1. backend business/data services
2. auth and permissioning
3. `agency-os` MCP server / integration layer
4. tool definitions, schemas, and descriptions
5. durable data resources and lookup capabilities

### Swappable layer

This is the piece that may change over time:

1. Claude.ai Project
2. ChatGPT workspace + connector setup
3. future Gemini or another LLM workspace

### What should NOT live only in project instructions

If the team wants the "head" to be replaceable, the most important behavior
cannot live only in Claude-specific project instructions.

Put durable logic in:

1. tool names and descriptions
2. tool schemas
3. backend permissioning
4. backend business logic
5. MCP resources and reusable prompt assets where supported

Use project instructions for:

1. workflow guidance
2. team conventions
3. tone/style defaults
4. prioritization hints

This keeps the core system portable even if the preferred chat surface changes.

## How Claude would actually work across Pro and Team

### Pro first: solo pilot

Claude Pro is enough to prove the product shape with one user.

With Pro, Jeff should be able to:

1. connect to the private `agency-os` remote MCP integration personally
2. authenticate to it as an individual user
3. test the core tool belt in Claude web
4. validate whether Claude actually becomes the preferred analyst surface

What Pro does **not** give is the broader managed team model:

1. no org-wide rollout
2. no owner-managed team availability for the integration
3. no shared-team governance model as the primary deployment target

So Pro should be treated as the **pilot environment**, not the final operating model.

### Team next: managed rollout

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

This is specifically the **Claude Team rollout** operating model, not
necessarily the final permanent surface strategy.

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
3. **tool metadata from the `agency-os` integration**

That means the recommended pattern is:

1. admin-owned canonical Agency OS project
2. most users with `Can use`
3. only a very small number of trusted editors with `Can edit`

## Current Agency OS skills and tools to expose first

The current The Claw and reporting stack already suggest the first tool belt.

### Current Claw skill inventory

1. `entity_resolver`
2. `task_confirmation_to_create`
3. `task_extraction`
4. `wbr_summary`
5. `wbr_weekly_email_draft`

### Current live tool inventory

1. `lookup_wbr`
2. `list_wbr_profiles`
3. `draft_wbr_email`

### Recommended first-pass `agency-os` integration tools

1. `resolve_client`
2. `get_wbr_summary`
3. `list_wbr_profiles`
4. `draft_wbr_email`
5. `get_monthly_pnl_report`
6. `list_child_asins`
7. `query_adscope_view`
8. `get_brand_or_client_context`

The first version should expose the existing useful business capabilities, not
try to mirror every internal implementation detail of The Claw.

### Reuse boundary: services yes, Slack skill runtime no

The `agency-os` MCP server should primarily reuse:

1. backend business/data services
2. existing report/query services
3. existing bridge logic where it is clean and stable

It should **not** treat The Claw's current Slack skill runtime as the main
integration boundary.

Why:

1. The Claw skills are Slack-oriented orchestration contracts
2. MCP tools need stable JSON schemas and clean tool semantics
3. Claude web does not need to inherit Slack-specific prompting and formatting rules

So the implementation model should be:

1. reuse the underlying services
2. wrap them in MCP-facing tool definitions
3. expose clean tool inputs/outputs to Claude

not:

1. expose `SKILL.md` files directly
2. port The Claw runtime into Claude
3. treat current Slack skills as the long-term product boundary

## Relationship to the shared AI runtime plan

This document is a companion to:

1. [shared_ai_service_plan.md](/Users/jeff/code/agency-os/docs/shared_ai_service_plan.md)
2. [agency_os_mcp_implementation_plan.md](/Users/jeff/code/agency-os/docs/agency_os_mcp_implementation_plan.md)

That plan still matters, but it solves a different problem.

This document is about:

1. the external high-capability chat surface
2. the private `agency-os` integration / MCP layer
3. how the team works inside Claude.ai first, and potentially other surfaces later

The shared AI service plan is about:

1. centralizing model/runtime logic for Agency OS-owned surfaces
2. The Claw
3. Scribe
4. Debrief
5. AdScope and other internal app features

## Implementation scope for the MCP pilot

This document should be read as the implementation spec for the first
`agency-os` MCP pilot.

### Phase 0

1. MCP foundation inside `backend-core`
2. Jeff-only pilot auth
3. MCP Inspector smoke test

### Phase 1

1. WBR read tools
2. Claude Pro can resolve clients, inspect profiles, and read WBR summaries

### Phase 2

1. WBR email draft tool
2. Claude Pro can create and return a persisted WBR draft

### Deferred from this pilot

1. shared internal AI runtime refactor
2. Scribe / Debrief / AdScope migration
3. Team rollout auth and admin governance
4. P&L tools
5. child-ASIN tools
6. broad multi-tool standardization

## Concrete insertion points in the repo

The pilot should be implemented against the current backend app and service
seams that already exist.

### Core app and auth

1. FastAPI app entry:
   - [main.py](/Users/jeff/code/agency-os/backend-core/app/main.py)
2. Existing auth helpers:
   - [auth.py](/Users/jeff/code/agency-os/backend-core/app/auth.py)

### WBR reuse seams

1. WBR bridge logic:
   - [wbr_skill_bridge.py](/Users/jeff/code/agency-os/backend-core/app/services/theclaw/wbr_skill_bridge.py)
2. WBR admin router:
   - [wbr.py](/Users/jeff/code/agency-os/backend-core/app/routers/wbr.py)
3. WBR email draft service:
   - [email_drafts.py](/Users/jeff/code/agency-os/backend-core/app/services/wbr/email_drafts.py)
4. WBR snapshots:
   - [report_snapshots.py](/Users/jeff/code/agency-os/backend-core/app/services/wbr/report_snapshots.py)

### Later-slice reuse seams

1. Child ASIN mappings:
   - [asin_mappings.py](/Users/jeff/code/agency-os/backend-core/app/services/wbr/asin_mappings.py)
2. P&L router:
   - [pnl.py](/Users/jeff/code/agency-os/backend-core/app/routers/pnl.py)
3. P&L report service:
   - [report.py](/Users/jeff/code/agency-os/backend-core/app/services/pnl/report.py)

Implementation rule:

1. Do not expose The Claw Slack runtime or `SKILL.md` files through MCP.
2. Reuse the underlying backend services instead.

## Code organization and anti-bloat rules

The MCP pilot should be implemented as a small, modular layer rather than one
large catch-all file.

### Required code-shape rules

1. keep the MCP server bootstrap small
2. keep auth/session handling separate from tool definitions
3. keep WBR tool wrappers in their own module or package
4. keep tool schemas/descriptions separate from underlying business logic where practical
5. prefer adding new domain modules over expanding one giant MCP file

### What to avoid

1. one `agency_os_mcp.py` file that contains transport, auth, tool schemas, and business logic
2. duplicating WBR or P&L logic inside the MCP layer
3. putting unrelated future tools into the first WBR pilot module

### Expected shape

At minimum, implementation should naturally separate:

1. MCP server/bootstrap
2. auth / user-resolution / allowlist checks
3. WBR tool definitions and wrappers
4. later domain modules such as P&L or child-ASIN tools

## Transport and endpoint contract

### Known

1. the pilot should use a Claude-compatible remote MCP server
2. it should be hosted from `backend-core`
3. it should expose one MCP base URL, not a custom ad hoc tool API

### Implementation rule

1. use an official Python MCP server/runtime, not a hand-rolled JSON tool endpoint
2. mount the MCP transport under a dedicated base path such as `/mcp`
3. if the chosen SDK requires SSE and/or a second message endpoint, follow the SDK exactly
4. once the runtime is chosen, document the final path shape explicitly in this doc

### Open question

1. the exact route shape depends on the chosen MCP Python server/runtime and should follow that SDK's transport conventions rather than being invented here

## Pilot auth model

The first pilot should use individual auth with a Jeff-only allowlist.

### Required behavior

1. only Jeff may complete auth and use tools during the Pro pilot
2. all other authenticated users should be rejected cleanly
3. auth should be built so later Team rollout can move to normal user-scoped access

### Default recommendation

1. gate by both Supabase `sub` and email if available
2. treat Supabase user id as the primary durable identifier

### Open questions

1. exact OAuth callback/token mechanics depend on the chosen remote MCP auth pattern
2. the final Jeff allowlist key should be confirmed before coding:
   - Supabase user id
   - email
   - both

## Slice 1 tool contracts

The pilot should expose a WBR-first tool belt.

### Tool: `resolve_client`

Purpose:

1. resolve a free-text client query to canonical Agency OS clients before other tools are called

Input:

```json
{
  "query": "string"
}
```

Output:

```json
{
  "matches": [
    {
      "client_id": "uuid",
      "client_name": "string",
      "active_wbr_marketplaces": ["US", "CA"]
    }
  ]
}
```

Rules:

1. return only clients relevant to the WBR-first pilot
2. include active WBR marketplace coverage in the response
3. do not silently choose a client inside the tool

### Tool: `list_wbr_profiles`

Purpose:

1. list canonical WBR profiles for a resolved client

Input:

```json
{
  "client_id": "uuid"
}
```

Output:

```json
{
  "profiles": [
    {
      "profile_id": "uuid",
      "client_id": "uuid",
      "client_name": "string",
      "display_name": "string",
      "marketplace_code": "US",
      "status": "active"
    }
  ]
}
```

Rules:

1. return active profiles only unless implementation discovers a concrete reason not to
2. if no profiles exist, return an empty `profiles` array rather than raising

### Tool: `get_wbr_summary`

Purpose:

1. return the current WBR digest for one concrete profile

Input:

```json
{
  "profile_id": "uuid"
}
```

Output:

```json
{
  "profile": {
    "profile_id": "uuid",
    "client_id": "uuid",
    "client_name": "string",
    "display_name": "string",
    "marketplace_code": "US"
  },
  "snapshot": {
    "source_run_at": "timestamp or null"
  },
  "digest": {
    "digest_version": "string",
    "...": "existing WBR digest payload"
  }
}
```

Rules:

1. accept `profile_id`, not client name + marketplace
2. downstream tools and Claude flows should use canonical identifiers once resolution is complete
3. reuse the existing snapshot/digest service
4. if the current implementation creates snapshots on demand, document this tool as read-through rather than strictly read-only

### Tool: `draft_wbr_email`

Purpose:

1. create and return a persisted multi-marketplace WBR client email draft

Input:

```json
{
  "client_id": "uuid"
}
```

Output:

```json
{
  "draft_id": "uuid",
  "client_id": "uuid",
  "snapshot_group_key": "string",
  "draft_kind": "weekly_client_email",
  "prompt_version": "string",
  "marketplace_scope": "string",
  "snapshot_ids": ["uuid"],
  "subject": "string",
  "body": "string",
  "model": "string or null",
  "created_at": "timestamp"
}
```

Rules:

1. reuse the existing WBR draft persistence/service path
2. mark this tool as mutating
3. errors such as `no client` or `no data` should be returned as structured tool errors, not buried in free text

## Non-goals for the pilot

1. no attempt to port The Claw runtime into Claude
2. no generic shared AI runtime refactor in this phase
3. no Team rollout or admin project automation in this phase
4. no broad multi-tool surface yet
5. no attempt to standardize every Agency OS capability before the pilot works

## Logging and audit expectations

Minimum pilot behavior:

1. every MCP tool invocation should be logged server-side
2. each log entry should include:
   - tool name
   - Agency OS user id
   - success or error outcome
   - timestamp
3. `draft_wbr_email` should be logged as a mutating tool invocation
4. do not invent a new analytics warehouse in slice 1; reuse existing backend logging patterns where practical

Open question:

1. whether MCP tool usage should live in `ai_token_usage`, a separate `mcp_tool_usage` table, or application logs should be decided before coding

## Acceptance criteria by slice

### Slice 0 complete when

1. the MCP server mounts successfully in `backend-core`
2. MCP Inspector can connect
3. Jeff can authenticate
4. a non-allowlisted user cannot authenticate or use tools

### Slice 1 complete when

1. Claude Pro can call:
   - `resolve_client`
   - `list_wbr_profiles`
   - `get_wbr_summary`
2. Claude can answer a real WBR question using Agency OS data only

### Slice 2 complete when

1. Claude Pro can call `draft_wbr_email`
2. a draft is persisted in `wbr_email_drafts`
3. Claude can present and revise the returned draft in normal chat

## Pre-coding open questions

These should remain explicit until they are confirmed from code or official MCP docs.

1. Which exact Python MCP server/runtime will be used inside `backend-core`?
2. What exact remote-MCP auth flow is required by the chosen Claude-compatible server transport?
3. What is the final allowlist key for the Jeff-only pilot:
   - Supabase user id
   - email
   - both
4. Where should MCP tool usage logs live in slice 1?
5. Should `get_wbr_summary` expose the full existing digest object unchanged, or a smaller curated envelope around it?

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

## Rollout model

Recommended rollout:

### Phase 0: Pro pilot

Start with:

1. Jeff on Claude Pro

Goal:

1. prove the private `agency-os` integration works end to end
2. confirm the real value of Claude web + Agency OS tools
3. identify the first tool set worth exposing
4. validate whether this should become the primary high-capability surface

### Phase 1: super users on Team

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

## Pilot test plan

1. unit tests for each MCP tool wrapper
2. auth allowlist tests
3. error-shape tests for no-match and no-data cases
4. MCP Inspector connectivity smoke test
5. Claude Pro manual smoke tests:
   - `How did Basari do last week in MX?`
   - `What WBR marketplaces exist for Whoosh?`
   - `Draft the weekly email for Whoosh`

## Pilot assumptions

1. `backend-core` is the correct first host for the MCP pilot
2. the first slice is WBR-first
3. the first pilot includes `draft_wbr_email`
4. Claude Pro is sufficient for Jeff's solo pilot
5. anything not explicitly confirmed from repo or official MCP docs should remain listed as an open question rather than being guessed
