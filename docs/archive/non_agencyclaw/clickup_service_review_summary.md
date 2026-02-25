# ClickUp Service PRD v0.1 Review Summary

**Date:** 2025-11-21
**Reviewers:** Red Team Agent, Supabase Consultant
**Document Reviewed:** [docs/08_clickup_service_prd.md](08_clickup_service_prd.md)

---

## Executive Summary

The ClickUp Service PRD is **conceptually sound** but has **critical gaps** in database schema design, caching strategy, and integration details. Most critically, the PRD **completely omits the database schema** required for caching and sync tracking.

**Status:** ⚠️ MAJOR REVISIONS REQUIRED

---

## Critical Issues (BLOCKERS)

### 1. Missing Database Schema for Caching ⚠️ CRITICAL (95% confidence)

**Issue (Supabase Consultant):** The PRD describes caching but defines **zero database tables**.

**What's missing:**
- `clickup_spaces_cache` - Cache ClickUp Spaces
- `clickup_users_cache` - Cache ClickUp Users
- `clickup_tasks_cache` - Cache ClickUp Tasks
- `clickup_sync_status` - Track sync state and errors
- `clickup_api_credentials` - Store API keys securely

**Impact:**
- Cannot implement as specified
- No way to cache data between API calls
- No sync tracking or error recovery
- Service will hit rate limits constantly

**Required addition:** Complete database schema section with tables, indexes, and RLS policies. See Supabase Consultant's proposed schema in review output.

---

### 2. Rate Limit Strategy Contradiction ⚠️ CRITICAL (90% confidence)

**Issue (Red Team):** PRD claims "100 requests per minute per workspace" but ClickUp's actual limit is **100 requests per minute per API key globally**.

**From PRD:**
> Rate limits: 100 req/min per workspace

**Actual ClickUp API limit:**
> 100 req/min per API key (across all workspaces)

**Impact:**
- Multi-workspace organizations will hit rate limits immediately
- Service will fail unpredictably
- Incorrect capacity planning

**Required fix:** Rewrite rate limiting strategy to account for global API key limits, not per-workspace.

---

### 3. Missing Webhook Recovery Mechanism ⚠️ CRITICAL (85% confidence)

**Issue (Red Team):** No strategy for handling deleted/disabled webhooks.

**Section 6.2 mentions webhook verification but missing:**
- Webhook health monitoring
- Automatic re-registration on failure
- Fallback to polling when webhooks fail
- Detection of stale webhooks

**Impact:**
- After webhook deletion, service silently stops receiving updates
- Data becomes stale indefinitely
- No automated recovery

**Required additions:**
- Webhook health check endpoint
- Re-registration logic
- Fallback polling strategy
- Alert when webhooks are inactive

---

### 4. Schema Mismatch with Team Central ⚠️ HIGH (85% confidence)

**Issue (Red Team):** PRD Section 8.2 schema doesn't align with Team Central PRD.

**ClickUp Service PRD uses:**
- `workspace_id`
- `list_id`

**Team Central PRD uses:**
- `team_id`
- `project_id`

**Impact:** Cannot integrate as specified. Unclear which naming convention to follow.

**Required fix:** Align schema naming with Team Central or document the mapping explicitly.

---

## High Priority Warnings

### 5. API Key Storage Security Gap ⚠️ HIGH (85% confidence)

**Issue (Red Team):** PRD stores API keys in plaintext.

**From PRD Section 8.1:**
```sql
clickup_api_key TEXT
```

**Security risks:**
- Keys exposed if database compromised
- No encryption at rest
- No key rotation mechanism

**Required fix:**
```sql
CREATE TABLE clickup_api_credentials (
  id UUID PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id),
  api_token_encrypted TEXT NOT NULL, -- Use Supabase Vault or pgcrypto
  workspace_id TEXT,
  key_rotated_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

### 6. Team Central Integration Gap ⚠️ MEDIUM (80% confidence)

**Issue (Supabase Consultant):** Team Central stores `clickup_space_id` and `clickup_user_id` but relationship to cache is undefined.

**Missing:**
- Foreign key constraints (or lack thereof)
- Data flow for populating these fields
- Validation that IDs exist in ClickUp
- Sync strategy between cache and Team Central tables

**Required clarification:** Document how Team Central's ClickUp IDs relate to the cache and whether referential integrity is enforced.

---

### 7. Cache Invalidation Strategy Incomplete ⚠️ MEDIUM (75% confidence)

**Issue (Red Team):** PRD specifies cache TTL but not invalidation on updates.

**Missing:**
- Invalidation on webhook events
- Cache warming strategy
- Handling of stale data during rate limits

**Impact:** Stale data served after ClickUp updates.

**Required addition:** Document cache invalidation triggers and strategy.

---

### 8. No Bulk Operation Limits ⚠️ MEDIUM (75% confidence)

**Issue (Red Team):** Endpoints like `POST /tasks/bulk-sync` have no specified limits.

**Risk:** Single request syncs 10,000 tasks, exhausts rate limits, or times out.

**Required addition:**
```yaml
Bulk operation limits:
  max_items_per_request: 100
  pagination_required: true
  max_concurrent_syncs: 3
```

---

### 9. Webhook Signature Verification Underspecified ⚠️ MEDIUM (75% confidence)

**Issue (Red Team):** Section 6.2 mentions signature verification but lacks implementation details.

**Missing:**
- Signature header name (e.g., `X-Signature`)
- HMAC algorithm (likely SHA-256)
- Verification pseudocode
- Signature secret storage location

**Impact:** Cannot implement webhook security without these details.

---

### 10. Missing Sync Strategy Details ⚠️ MEDIUM (75% confidence)

**Issue (Supabase Consultant):** PRD doesn't specify:
- Refresh intervals
- Stale data thresholds
- Conflict resolution
- Webhook vs polling strategy
- Initial sync batch size

**Required addition:**
```yaml
Sync Strategy:
  refresh_intervals:
    spaces: 24 hours
    users: 12 hours
    tasks: 5 minutes (active) / 1 hour (archived)
  stale_threshold: 2x refresh_interval
  conflict_resolution: "ClickUp is source of truth"
  initial_sync:
    batch_size: 100
    parallelism: 3
```

---

## Notes & Recommendations

### 11. RLS and Permission Concerns

**Issue (Supabase Consultant):** Missing specifications for:
- Service account permissions (needs INSERT/UPDATE on cache tables)
- Cross-tenant isolation enforcement
- Admin-only access to API credential management

**Recommendation:** Add RLS policies section with service role permissions and user access controls.

---

### 12. Error Tracking Schema Incomplete

**Issue (Supabase Consultant):** Need to specify:
- Maximum retry attempts
- Error categorization (transient vs permanent)
- Alerting thresholds
- Quarantine strategy for failed entities

**Recommendation:** Expand `clickup_sync_status` table design with error handling fields.

---

## Summary Table

| Issue | Severity | Confidence | Status |
|-------|----------|------------|--------|
| Missing database schema | CRITICAL | 95% | Must add |
| Rate limit contradiction | CRITICAL | 90% | Must fix |
| Missing webhook recovery | CRITICAL | 85% | Must add |
| Schema mismatch with Team Central | HIGH | 85% | Must fix |
| API key security | HIGH | 85% | Must fix |
| Team Central integration gap | MEDIUM | 80% | Must clarify |
| Cache invalidation incomplete | MEDIUM | 75% | Must specify |
| No bulk operation limits | MEDIUM | 75% | Must add |
| Webhook signature verification | MEDIUM | 75% | Must specify |
| Missing sync strategy | MEDIUM | 75% | Must add |
| RLS policies missing | MEDIUM | 70% | Should add |
| Error tracking incomplete | MEDIUM | 70% | Should expand |

---

## Required Actions

1. **Add Section 8** (Database Schema) with complete table definitions
   - Include Supabase Consultant's proposed tables
   - Add indexes for performance
   - Define RLS policies

2. **Update Section 5** (Rate Limiting) with correct global API key limits

3. **Add Section 6.3** (Webhook Health & Recovery) with:
   - Health monitoring strategy
   - Automatic re-registration
   - Fallback polling logic

4. **Add Section 9** (Integration with Team Central) explaining:
   - Relationship between cache and Team Central's ClickUp IDs
   - Data flow and sync strategy
   - Validation approach

5. **Update Section 8.1** (if exists) with encrypted API key storage

6. **Add Section 5.4** (Cache Invalidation Strategy)

7. **Add Section 4.x** (Bulk Operation Limits and Pagination)

8. **Expand Section 6.2** (Webhook Security) with implementation details

9. **Add Section 7** (Data Synchronization Strategy) with:
   - Refresh intervals
   - Conflict resolution
   - Batch sizes

10. **Add Section 8.x** (RLS Policies and Permissions)

---

## Proposed Database Schema

The Supabase Consultant provided complete schema proposals including:
- ✅ Cache tables for spaces, users, and tasks
- ✅ Sync status tracking table
- ✅ API credentials table with encryption
- ✅ Performance indexes with `organization_id`
- ✅ RLS policies for multi-tenant isolation
- ✅ Service role permissions

**Location:** See full schema in Supabase Consultant's review output.

---

## Conclusion

The ClickUp Service PRD has **solid API design** but is **missing critical implementation details**:
- No database schema (!)
- Incorrect rate limiting assumptions
- Incomplete webhook recovery
- Security gaps

**Cannot proceed to implementation** without adding the database schema and addressing the blockers.

**Recommended next steps:**
1. Add complete database schema section using Supabase Consultant's template
2. Correct rate limiting strategy for global API key limits
3. Add webhook health monitoring and recovery mechanisms
4. Clarify integration with Team Central
5. Add security specifications for API keys and webhooks
6. Re-review with both agents after updates
