# Claude Tool Budget Plan

_Created: 2026-03-26 (ET)_

## Purpose

Estimate how much prompt/context budget the current Agency OS Claude surface is
using, and define a sane expansion budget so we do not bloat the tool belt
while chasing Jarvis-like workflows.

## Current official context reference

Current official Anthropic references as of 2026-03-26:

1. paid Claude plans in `claude.ai` support `200K` context
2. Claude Enterprise with Sonnet 4 can support `500K`
3. tool definitions and schemas count toward the usable context window

Sources:

1. `https://support.anthropic.com/en/articles/8606394-how-large-is-the-context-window-on-paid-claude-ai-plans`
2. `https://docs.anthropic.com/en/docs/build-with-claude/context-windows`

## Measurement method

These estimates are intentionally rough.

Method used:

1. extract each registered MCP tool’s:
   - tool name
   - description
   - input schema JSON
2. measure total character length
3. estimate tokens as `chars / 4`

This is not Anthropic’s exact tokenizer, but it is a practical sizing method
for prompt-budget planning.

## Current live MCP surface

Current live tool count: `14`

Estimated current tool-config size:

1. total chars: `9,484`
2. estimated total tokens: `2,371`

### Current tools

| Tool | Domain | Est. tokens | Notes |
|---|---|---:|---|
| `resolve_client` | shared context | 115 | dense payload, but small schema |
| `list_wbr_profiles` | WBR | 78 | compact |
| `get_wbr_summary` | WBR | 91 | compact |
| `draft_wbr_email` | WBR | 73 | compact mutation |
| `list_monthly_pnl_profiles` | Monthly P&L | 80 | compact |
| `get_monthly_pnl_report` | Monthly P&L | 151 | moderate due to month filters |
| `get_monthly_pnl_email_brief` | Monthly P&L | 164 | moderate |
| `draft_monthly_pnl_email` | Monthly P&L | 257 | one of the larger current tools |
| `list_clickup_tasks` | ClickUp | 179 | moderate |
| `get_clickup_task` | ClickUp | 134 | compact |
| `update_clickup_task` | ClickUp | 327 | largest current tool |
| `resolve_team_member` | ClickUp | 190 | moderate |
| `prepare_clickup_task` | ClickUp | 253 | large but acceptable |
| `create_clickup_task` | ClickUp | 286 | large but acceptable |

### What this means

The current live tool surface is **not** bloated.

At roughly `2.4K` estimated tokens, the current MCP tool configuration is
small relative to a `200K` context window.

## Current Claude Project file bundle

The uploaded Claude Project instructions/playbooks are currently larger than
the MCP tool metadata itself.

### Current project-file estimates

| File | Lines | Est. tokens |
|---|---:|---:|
| `project_instructions.md` | 108 | 1,506 |
| `wbr_mcp_playbook.md` | 159 | 840 |
| `monthly_pnl_mcp_playbook.md` | 276 | 1,757 |
| `clickup_mcp_playbook.md` | 296 | 1,908 |

Estimated current Claude Project file total: `6,011` tokens

## Combined baseline

Approximate baseline before chat history and tool outputs:

1. current tool surface: `2,371`
2. current project file bundle: `6,011`
3. combined baseline: `8,382`

That is still very manageable against `200K`.

## Real bottleneck

The likely failure mode is **not** current tool count.

The real budget pressure will usually come from:

1. long chat history
2. large tool outputs
3. overly long project instructions
4. overlapping tools with verbose descriptions
5. broad generic tools that encourage Claude to inspect too much data

So the main design rule is:

1. keep tools few
2. keep descriptions sharp
3. keep schemas compact
4. keep outputs shaped and bounded

## Recommended Agency OS tool budget

### Target ranges

Recommended steady-state budget:

1. top-level tools: `18–24`
2. total tool-config size: under `5K` estimated tokens
3. Claude Project file bundle: under `10K` estimated tokens
4. any single tool schema+description: ideally under `350` estimated tokens

### Red-flag thresholds

Start refactoring or merging when:

1. top-level tools exceed `30`
2. tool-config size approaches `8K+` estimated tokens
3. there are multiple tools whose names/descriptions overlap materially
4. Claude has to “choose between near-duplicates” too often

## One-table planning view

| Category | Tools | Count | Est. tokens | Notes |
|---|---|---:|---:|---|
| Current live: shared context | `resolve_client` | 1 | 115 | canonical client resolver |
| Current live: WBR | `list_wbr_profiles`, `get_wbr_summary`, `draft_wbr_email` | 3 | 242 | compact current WBR surface |
| Current live: Monthly P&L | `list_monthly_pnl_profiles`, `get_monthly_pnl_report`, `get_monthly_pnl_email_brief`, `draft_monthly_pnl_email` | 4 | 652 | healthy current finance surface |
| Current live: ClickUp | `list_clickup_tasks`, `get_clickup_task`, `update_clickup_task`, `resolve_team_member`, `prepare_clickup_task`, `create_clickup_task` | 6 | 1,369 | largest current domain, still reasonable |
| **Current live total** | all current MCP tools | **14** | **2,371** | current production/pilot reality |
| Proposed analyst tools | `get_asin_sales_window`, `get_campaign_performance_window`, `list_child_asins_for_row`, `get_sync_freshness_status`, `query_business_facts`, `query_ads_facts`, `query_catalog_context`, `query_monthly_pnl_detail` | 8 | 1,440 | recommended next-wave analyst layer |
| Proposed STR tools | `query_search_term_facts`, `rank_search_terms` | 2 | 420 | add after STR ingestion exists |
| **Projected total after analyst wave** | current + analyst | **22** | **3,811** | still comfortably inside target range |
| **Projected total after analyst + STR wave** | current + analyst + STR | **24** | **4,231** | still comfortably inside target range |
| Headroom target | recommended steady-state top-level tools | 18–24 | under 5,000 | preferred operating zone |
| Headroom caution | start watching closely | 25–30 | 5,000–8,000 | merge/refactor if overlap grows |
| Headroom red flag | likely too much surface overlap | 30+ | 8,000+ | strong signal to consolidate |
| Current Claude Project files | `project_instructions.md`, `wbr_mcp_playbook.md`, `monthly_pnl_mcp_playbook.md`, `clickup_mcp_playbook.md` | 4 files | 6,011 | currently larger than tool metadata itself |
| Current baseline incl. project files | current live tools + current project bundle | — | 8,382 | still very manageable vs 200K |

## Recommended expansion model

Do **not** add one tool per question type.

Prefer:

1. compact domain tools for common questions
2. a few guarded analyst-query tools for ad hoc analysis
3. backend services doing the heavy lifting

## Proposed next-wave expansion

The right next expansion is **not** 15 new one-off tools.

It is a compact analyst layer made of a few high-value tools.

### Proposed next-wave tools

| Proposed tool | Purpose | Est. tokens | Why it belongs |
|---|---|---:|---|
| `get_asin_sales_window` | answer “how did these ASINs do in X window?” | 150 | very common strategist question |
| `get_campaign_performance_window` | answer “how did these campaigns do in X window?” | 170 | common ads question |
| `list_child_asins_for_row` | answer “what products make up this row?” | 120 | useful, narrow, low risk |
| `get_sync_freshness_status` | answer “is this data current?” | 120 | avoids confusion on source lag |
| `query_business_facts` | guarded flexible WBR business queries | 220 | one overflow tool instead of many |
| `query_ads_facts` | guarded flexible ads queries | 230 | one overflow tool instead of many |
| `query_catalog_context` | look up product/title/catalog context | 200 | needed for analyst and AI review |
| `query_monthly_pnl_detail` | guarded finance drill-down | 230 | lets Claude answer ad hoc P&L questions |

Estimated added budget for that wave: about `1,440` tokens

Estimated resulting totals:

1. tool count: `22`
2. total tool-config size: about `3,811` tokens

That is still comfortably within the recommended range.

## STR-era expansion

Once search-term data is ingested, add **one** STR analyst tool first, not a
large family.

### Suggested STR-first additions

| Proposed tool | Purpose | Est. tokens | Notes |
|---|---|---:|---|
| `query_search_term_facts` | answer ad hoc search-term questions | 240 | flexible first tool |
| `rank_search_terms` | optional later ranking helper | 180 | add only if repeatedly useful |

This is preferable to adding many specialized tools like:

1. `best_keyword_last_week`
2. `worst_keyword_last_week`
3. `zero_order_terms`
4. `asin_target_wasters`
5. `search_term_breakdown_by_campaign`

Those are better handled by one guarded STR query tool plus Claude synthesis.

## Recommended final shape

### Good shape

1. shared context tool(s)
2. WBR summary tools
3. Monthly P&L tools
4. ClickUp tools
5. a few analyst-query tools
6. later one STR query tool

### Bad shape

1. dozens of tiny semi-duplicate tools
2. one raw unrestricted SQL tool
3. long narrative descriptions on every tool
4. huge schemas that encode business logic in parameters

## Recommendation

The current surface is healthy.

Best next move:

1. keep the current tool belt as-is
2. add at most `6–8` analyst tools in the next wave
3. avoid a broad raw-SQL tool at the top level
4. revisit the budget only when we cross about `20+` tools or `4–5K` estimated
   tool-config tokens

## Bottom line

Agency OS is **not close** to overloading Claude with tool metadata today.

Current rough baseline:

1. tools: `2,371` estimated tokens
2. project files: `6,011` estimated tokens
3. combined: `8,382` estimated tokens

That means the tool-bloat risk is currently secondary to:

1. keeping tools well named
2. keeping schemas compact
3. keeping outputs bounded
4. avoiding too many overlapping analyst tools
