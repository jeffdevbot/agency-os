# Product Requirement Document: The Operator (Deprecated)

**Status:** Deprecated  
**Last Updated:** 2025-12-16  
**Replaced By:** `docs/debrief_prd.md` (Debrief) + `docs/08_clickup_service_prd.md` (shared ClickUp integration)

## Summary

The Operator was an early concept for an AI-driven ClickUp + SOP “central nervous system”. In practice, this scope evolved into **Debrief**:
- ingest meeting notes
- extract actionable tasks
- review/edit/remove tasks
- send tasks to ClickUp (using the shared ClickUp service)

This document is kept only as historical context (and to match existing DB migrations like `20250122000002_operator_tables.sql`). If we ever revive Operator-like functionality (SOP canonization, SOP search, task orchestration), we should write a fresh spec based on Debrief’s shipped workflow and the current ClickUp Service contract.
