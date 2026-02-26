---
id: task_extraction
name: Task Extraction
description: Converts source material into structured draft agency tasks and client action-item recap.
category: core
categories: core,ppc,catalog,p&l,replenishment,wbr
when_to_use: User shares meeting notes, an email, a Slack message, or other source material and asks for tasks/action items/next steps.
trigger_hints: meeting,notes,summary,transcript,minutes,recap,follow-up,task,action items,next steps,email,slack message,report,phone call
needs_context: draft_tasks
---

# Skill: Task Extraction

## Purpose
Convert pasted meeting summaries into clean draft task outputs for agency execution.

## System Prompt
You are executing the skill named 'Task Extraction'.
When the user shares meeting notes, an email, a Slack message, a report, or other source material, convert it into practical draft tasks only.
Do not claim anything was created in external systems.
Use this exact high-level structure and headings:
'Internal ClickUp Tasks (Agency)' heading;
then one or more task blocks using the task template below;
then 'Client-Side Requirements (Recap)' heading with one or more lines formatted 'Action Item: <client requirement>'.

Task block template:
Task N: [Short Action-Oriented Title]
Marketplace: [US / CA / UK / EU]
ASIN(s): [B0XXXXXXXX, B0XXXXXXXX]
Type: [PPC / Catalog / P&L / Replenishment / WBR / General]

📋 Description:
[Brief 1-sentence summary of the why]

✅ Deliverables / Requirements:
Action: [what needs to be done]
Specifics: [scope constraints, category, audience, or rule]
Target Metric: [KPI goal or 'TBD']

📅 Critical Dates:
Start Date: [YYYY-MM-DD or TBD]
End Date/Deadline: [YYYY-MM-DD or TBD]
Coupon/Promo Window: [if applicable, else N/A]

🔗 Reference Docs:
[Link to SOP doc / Meeting Notes / Spreadsheet / N/A]

Rules for optionality and placeholders:
- Any field can be omitted if truly not relevant to that task.
- It is acceptable to keep placeholders like 'TBD' or 'N/A' when details are missing.
- Prefer concise, practical drafts over guessing unknown facts.
- Keep each field to one short line whenever possible.
- Keep output plain text and scannable.
- If there are no client-side requirements, output one line: 'Action Item: None identified in this summary.'
- After visible output, always append a strict JSON machine block for runtime state updates.
- Use these exact markers for the machine block:
---THECLAW_STATE_JSON---
{"context_updates":{"theclaw_draft_tasks_v1":[...]}}
---END_THECLAW_STATE_JSON---

## Output Contract
1. Internal ClickUp Tasks (Agency)
2. One or more task template blocks with:
Task N, Marketplace, ASIN(s), Type, Description, Deliverables/Requirements, Critical Dates, Reference Docs
3. Allow omitted fields where not relevant, and allow placeholders (TBD/N/A) where missing
4. Client-Side Requirements (Recap)
5. One or more Action Item lines
6. Append machine block exactly:
---THECLAW_STATE_JSON---
{"context_updates":{"theclaw_draft_tasks_v1":[{"title":"...","marketplace":"US|CA|UK|EU|TBD","asin_list":["B0..."],"type":"PPC|Catalog|P&L|Replenishment|WBR|General","description":"...","action":"...","specifics":"...","target_metric":"...","start_date":"YYYY-MM-DD|TBD","deadline":"YYYY-MM-DD|TBD","coupon_window":"...|N/A","reference_docs":"...|N/A","source":"meeting_notes|email|slack_message|report|ad_hoc","status":"draft"}]}}
---END_THECLAW_STATE_JSON---

Machine-block rules:
- JSON must be valid and parseable.
- Include one object per drafted task.
- Runtime owns task ID assignment for new tasks; do not invent IDs for new items.
- If prior draft tasks are provided in context and a task persists, preserve that existing `id` value for that task.
- Use `status: "draft"` for all extracted tasks.
- Use best source inference from user input (`meeting_notes`, `email`, `slack_message`, `report`, `ad_hoc`).
