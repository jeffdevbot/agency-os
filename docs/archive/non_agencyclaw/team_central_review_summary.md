# Team Central PRD Review Summary

**Date:** 2025-11-21
**Reviewers:** Red Team Agent, Supabase Consultant
**Document Reviewed:** [docs/07_team_central_prd.md](07_team_central_prd.md)

---

## Executive Summary

The Team Central PRD is **largely sound** with a few critical issues that must be addressed before implementation. The schema design is safe and avoids conflicts with existing tables, but the RLS policies need refinement.

**Status:** ✅ Approved with required changes

---

## Critical Issues (Must Fix)

### 1. RLS Policy Authentication Method ⚠️ CRITICAL

**Issue:** The PRD uses `auth.jwt() ->> 'role' = 'admin'` which hasn't been verified to exist in JWT claims.

**Current PRD:**
```sql
CREATE POLICY "agency_clients_insert" ON public.agency_clients
  FOR INSERT TO authenticated
  WITH CHECK (auth.jwt() ->> 'role' = 'admin');
```

**Required Fix:**
```sql
CREATE POLICY "agency_clients_insert" ON public.agency_clients
  FOR INSERT TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.profiles
      WHERE id = auth.uid()
      AND is_admin = true
    )
  );
```

**Action:** Update all RLS policies in the PRD to use the `profiles.is_admin` pattern instead of JWT role checks.

---

### 2. Missing Performance Indexes ⚠️ MEDIUM

**Issue:** Common query patterns are missing optimized indexes.

**Required Additions:**
```sql
-- For "show me all primary contacts for a client"
CREATE INDEX idx_client_assignments_client_primary
  ON public.client_assignments(client_id, is_primary_contact)
  WHERE is_primary_contact = true;

-- For "show me all active assignments by role"
CREATE INDEX idx_client_assignments_role
  ON public.client_assignments(role);

-- For profiles admin lookup (used by RLS)
CREATE INDEX idx_profiles_is_admin
  ON public.profiles(is_admin)
  WHERE is_admin = true;
```

**Action:** Add these indexes to the migration script.

---

### 3. Foreign Key Cascade Behavior ⚠️ MEDIUM

**Issue:** Using `ON DELETE CASCADE` for `client_id` might cause unintended data loss when clients are deleted.

**Current:**
```sql
client_id uuid NOT NULL REFERENCES public.agency_clients(id) ON DELETE CASCADE
```

**Recommendation:**
```sql
client_id uuid NOT NULL REFERENCES public.agency_clients(id) ON DELETE RESTRICT
-- Or implement soft-delete pattern with archived_at column
```

**Action:** Decide on delete strategy and update schema accordingly.

---

## Documentation Gaps (Should Address)

### 4. Semantic Clarification Needed

**Issue:** Need to clearly document the difference between:
- `agency_clients` = Team Central's client list (Ecomlabs' agency clients)
- `client_profiles` = Composer's multi-tenant client data (end-users' clients)

**Action:** Add a section to the PRD or create `docs/team_central/schema_single_tenant.md` explaining the single-tenant architecture and why `organization_id` is absent from Team Central tables.

---

## Good News ✅

1. **No table name conflicts** - `agency_clients` doesn't conflict with existing tables
2. **Safe profiles enhancements** - All additive changes with proper defaults
3. **No migration conflicts** - Can use migration timestamp `20250114000005_add_team_central_tables.sql`
4. **Sound foreign key relationships** - All references are valid
5. **Single-tenant architecture is appropriate** - No need for `organization_id`

---

## Red Team Findings (Context)

The Red Team agent initially flagged several issues based on reviewing against a multi-tenant schema pattern. After Supabase Consultant review, we determined:

- Most Red Team concerns were based on incorrect assumptions about the architecture
- The single-tenant design is intentional and appropriate for Team Central
- The real issues are the RLS policy implementation and missing indexes (flagged above)

---

## Required Actions Before Implementation

1. ✅ **Archive old Admin Settings PRD** - Completed, moved to `docs/archive/`
2. ⚠️ **Update RLS policies in PRD** - Use `profiles.is_admin` instead of JWT role
3. ⚠️ **Add missing indexes to migration**
4. ⚠️ **Decide on delete strategy** - CASCADE vs RESTRICT vs soft-delete
5. ⚠️ **Document single-tenant architecture** - Create schema documentation
6. ⚠️ **Verify JWT structure** - Confirm `auth.uid()` works as expected
7. ⚠️ **Test RLS policies** - Create test script before deploying

---

## Supabase Consultant's Safe Migration

The Supabase Consultant provided a production-ready migration script that addresses all issues. Key improvements:

- Uses `profiles.is_admin` for all admin checks
- Includes all required indexes
- Uses `ON DELETE RESTRICT` for client FK
- Adds helpful SQL comments
- Includes rollback script

**Location:** See Supabase Consultant's output in the review session

---

## Next Steps

1. **Update the PRD** with the safer RLS policy pattern
2. **Create the migration file** using Supabase Consultant's template
3. **Write tests** for RLS policies
4. **Document** the single-tenant architecture
5. **Review** with team before implementation
6. **Deploy** to staging first

---

## Conclusion

Team Central is well-designed and ready for implementation after addressing the RLS policy issues and adding the missing indexes. The schema is safe, the architecture is sound, and there are no conflicts with existing tables.

**Confidence Level:** 90% ready for implementation after required fixes
