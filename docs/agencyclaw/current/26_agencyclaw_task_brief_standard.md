# AgencyClaw Task Brief Standard

Last updated: 2026-02-19

## 1. Purpose
Define a consistent task brief format for AgencyClaw task creation so work is:
- source-grounded,
- easy to execute,
- easy to QA,
- and resilient to SOP updates.

This standard intentionally avoids full SOP copy-paste into every task.

## 2. Operating Model
For recurring operational work:
- Keep one canonical SOP document.
- Create tasks with a concise Task Brief that captures only client-specific variables and execution intent.
- Link the canonical SOP and include SOP version/last-reviewed metadata in the task.

Recommended pattern:
1. Task Brief (short, specific, execution-ready)
2. SOP Link + SOP version tag
3. Definition of Done
4. Any approved deviation from SOP

## 3. Task Types
Primary task-type buckets:
- `ppc_optimization`
- `promotions`
- `catalog_account_health`
- `generic_operations` (fallback when no bucket cleanly matches)

Mapping examples:
- PPC optimization: `ngram`, `npat`, `hv_kw`, `hv_pat`, `placement_bid`, `campaign_target`, `pacvue_rules`, `portfolio_budgets`
- Promotions: `coupons`, `price_discounts`
- Catalog/account health: `policy_violations`, `product_compliance`, `search_suppressed`, `stranded_inventory`, `fba_restock`

## 4. Canonical Brief Fields
Fields required for all task types:
- `task_type`
- `objective`
- `client_name`
- `brand_name`
- `marketplace`
- `owner`
- `due_date`
- `sop_reference` (title/url/version)
- `client_variables` (key/value details)
- `definition_of_done`
- `deviations_from_sop`

## 5. JSON Contracts

## 5.1 Common Base
```json
{
  "task_type": "ppc_optimization | promotions | catalog_account_health | generic_operations",
  "objective": "string",
  "client_name": "string",
  "brand_name": "string",
  "marketplace": "string",
  "owner": "string",
  "due_date": "YYYY-MM-DD",
  "sop_reference": {
    "title": "string",
    "url": "string",
    "version": "string"
  },
  "client_variables": {
    "key": "value"
  },
  "definition_of_done": [
    "string"
  ],
  "deviations_from_sop": [
    "string"
  ]
}
```

## 5.2 PPC Optimization Extension
```json
{
  "campaign_scope": [
    "string"
  ],
  "date_window": {
    "lookback_days": 14,
    "execution_window": "string"
  },
  "target_kpis": {
    "acos_target": "string",
    "tacos_target": "string",
    "roas_target": "string",
    "spend_guardrail": "string"
  },
  "bid_budget_constraints": {
    "min_bid": "string",
    "max_bid": "string",
    "daily_budget_cap": "string"
  },
  "harvest_negative_rules": [
    "string"
  ],
  "qa_checks": [
    "string"
  ]
}
```

## 5.3 Promotions Extension
```json
{
  "promotion_type": "coupon | price_discount | other",
  "eligible_asins_or_skus": [
    "string"
  ],
  "discount_settings": {
    "discount_percent": "string",
    "budget_cap": "string",
    "redemption_limit": "string"
  },
  "schedule": {
    "start_at": "ISO-8601",
    "end_at": "ISO-8601",
    "timezone": "string"
  },
  "combinability_rules": [
    "string"
  ],
  "post_launch_checks": [
    "string"
  ]
}
```

## 5.4 Catalog/Account Health Extension
```json
{
  "issue_type": "string",
  "severity": "low | medium | high",
  "affected_asins_or_skus": [
    "string"
  ],
  "required_evidence": [
    "string"
  ],
  "fix_path": [
    "string"
  ],
  "sla_target": "string",
  "escalation_path": "string",
  "closure_proof": [
    "string"
  ]
}
```

## 5.5 Generic Operations Fallback Extension
Use this when the task does not fit PPC/Promotions/Catalog buckets.

```json
{
  "workstream": "string",
  "inputs_required": [
    "string"
  ],
  "constraints": [
    "string"
  ],
  "deliverables": [
    "string"
  ],
  "approval_requirements": [
    "string"
  ],
  "risk_notes": [
    "string"
  ]
}
```

## 5.6 Generic Unclassified Super-Fallback
Use this when the request is valid but classification confidence is still low after clarification.
This is intentionally minimal and should trigger one focused follow-up before execution when possible.

```json
{
  "request_summary": "string",
  "business_outcome": "string",
  "known_facts": [
    "string"
  ],
  "open_questions": [
    "string"
  ],
  "proposed_first_step": "string",
  "approval_needed": "boolean"
}
```

## 6. Markdown Templates

## 6.1 Universal Header
```md
## Task Brief
- Task Type:
- Objective:
- Client:
- Brand:
- Marketplace:
- Owner:
- Due Date:

## Client Variables
- 

## SOP Reference
- SOP:
- Version:
- Link:

## Definition of Done
- [ ]

## Deviations from SOP
- None
```

## 6.2 PPC Template Add-on
```md
## PPC Scope
- Campaign Scope:
- Date Window:
- KPI Targets (ACOS/TACOS/ROAS):
- Bid/Budget Constraints:
- Harvest/Negative Rules:

## QA Checks
- [ ]
```

## 6.3 Promotions Template Add-on
```md
## Promotion Setup
- Promotion Type:
- Eligible ASINs/SKUs:
- Discount % / Budget Cap:
- Start/End + Timezone:
- Combinability Rules:

## Post-Launch Checks
- [ ]
```

## 6.4 Catalog/Account Health Template Add-on
```md
## Issue Context
- Issue Type:
- Severity:
- Affected ASINs/SKUs:
- Required Evidence:
- Fix Path:
- SLA Target:
- Escalation:

## Closure Proof
- [ ]
```

## 6.5 Generic Operations Template Add-on
```md
## Workstream Context
- Workstream:
- Inputs Required:
- Constraints:
- Deliverables:
- Approval Requirements:
- Risk Notes:
```

## 6.6 Generic Unclassified Template (Last-Resort)
```md
## Task Brief (Unclassified)
- Request Summary:
- Business Outcome:
- Known Facts:
- Open Questions:
- Proposed First Step:
- Approval Needed: yes/no

## SOP Reference
- SOP: (if found)
- Link:
- Version:
```

## 7. Runtime Rules For AgencyClaw
- If high-confidence SOP/internal evidence exists:
  - produce confirmation-ready brief using the matching bucket template.
- If only similar historical tasks exist:
  - produce a partial brief and ask targeted clarification.
- If evidence is weak/none:
  - do not fabricate details; ask for missing context using the generic fallback template.
- Always include `SOP Reference` in final task description when a canonical SOP exists.

## 8. Why This Standard
- Keeps SOPs maintainable (single source of truth).
- Reduces stale copy-paste instruction drift.
- Improves employee scan speed and handoff quality.
- Preserves flexibility for non-standard tasks via the generic fallback contract.

## 9. Team UX Defaults
- Default pattern: short task brief + canonical SOP link (not full SOP body copy-paste).
- Include full SOP excerpt only when execution is high-risk and the assignee would otherwise need to leave the task context.
- Keep task body operator-first: what to do for this specific client now, why, by when, and how success is measured.
