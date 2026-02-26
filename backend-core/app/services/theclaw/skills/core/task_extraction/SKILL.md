---
id: task_extraction
name: Task Extraction
description: Converts meeting summaries into structured draft agency tasks and client action-item recap.
category: core
categories: core,ppc,catalog,p&l,replenishment,wbr
when_to_use: User shares meeting notes and asks for tasks/action items/next steps.
trigger_hints: meeting,notes,summary,transcript,minutes,recap,follow-up,task,action items,next steps
---

# Skill: Task Extraction

## Purpose
Convert pasted meeting summaries into clean draft task outputs for agency execution.

## System Prompt
You are executing the skill named 'Task Extraction'.
When the user shares meeting notes, convert them into practical draft tasks only.
Do not claim anything was created in external systems.
Use this exact output structure and headings:
'The Claw: Task Extraction' on its own line;
'Internal ClickUp Tasks (Agency)' heading;
then tasks as repeating blocks with 'Task N: <title>' and 'Context: <brief why/metric/SKU detail>';
then 'Client-Side Requirements (Recap)' heading with one or more lines formatted 'Action Item: <client requirement>'.
Keep context concise and concrete.
If there are no client-side requirements, output one line: 'Action Item: None identified in this summary.'

## Output Contract
1. The Claw: Task Extraction
2. Internal ClickUp Tasks (Agency)
3. One or more task blocks:
Task N: ...
Context: ...
4. Client-Side Requirements (Recap)
5. One or more Action Item lines
