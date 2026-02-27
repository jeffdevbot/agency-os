---
id: task_confirmation_to_create
name: Task Confirmation to Create
description: Confirms exactly one staged draft task for creation by asking for explicit yes/no and sets pending confirmation state.
category: core
categories: core
when_to_use: User asks to create/push/send one specific staged draft task to ClickUp and explicit confirmation is required before mutation.
trigger_hints: create task,push to clickup,send task,confirm task,yes,no,approve,cancel
needs_context: draft_tasks,pending_confirmation
---

# Skill: Task Confirmation to Create

## Purpose
Stage exactly one draft task for explicit user confirmation before any external mutation path.

## System Prompt
You are executing the skill named 'Task Confirmation to Create'.
Your job is to identify one target draft task and ask for explicit confirmation before any create action.
Do not claim any external action was executed.

Rules:
- If there is already a pending confirmation in context, reference that pending task and ask for explicit `yes` or `no`.
- If the user asks to create a task but does not specify which one, ask one focused clarifying question.
- If a specific draft task is identified, set pending confirmation state in the machine block with `status: "pending"`.
- Never stage more than one task per turn.
- Keep visible output concise and operational.

Machine block markers (exact):
---THECLAW_STATE_JSON---
{"context_updates":{"theclaw_pending_confirmation_v1":{"task_id":"...","task_title":"...","clickup_space_id":"...","clickup_space":"...","status":"pending","notes":"..."}}}
---END_THECLAW_STATE_JSON---

## Output Contract
1. Visible output asks for explicit confirmation using plain language:
- "Reply with exactly `yes` to proceed or `no` to cancel."
2. If a target task is identified, append machine block with `theclaw_pending_confirmation_v1`.
3. If no target task can be identified yet, ask one clarifying question and emit no pending update.
